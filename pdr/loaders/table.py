from functools import partial
from operator import contains

import pdr.loaders.queries
from pdr.loaders._helpers import get_target


def read_array(self, object_name="ARRAY"):
    """
    Read an array object from this product and return it as a numpy array.
    """
    # TODO: Maybe add block[AXES] as names? Might have to switch to pandas
    #  or a flattened structured array or something weirder
    fn = self.file_mapping[object_name]
    block = self.metablock_(object_name)
    # 'obj' will be equal to 'block' if no subobject is found
    obj = check_array_for_subobject(block)
    if block.get('INTERCHANGE_FORMAT') == "BINARY":
        with decompress(fn) as f:
            binary = np_from_buffered_io(
                f,
                dtype=sample_types(obj["DATA_TYPE"], obj["BYTES"], True),
                count=get_array_num_items(block),
                offset=pdr.loaders.queries.data_start_byte(pointerize(object_name))
            )
        return binary.reshape(block['AXIS_ITEMS'])
    # assume objects without the optional interchange_format key are ascii
    with open(fn) as stream:
        text = stream.read()
    try:
        text = tuple(map(float, re.findall(r'[+-]?\d+\.?\d*', text)))
    except (TypeError, IndexError, ValueError):
        text = re.split(r'\s+', text)
    array = np.asarray(text).reshape(block['AXIS_ITEMS'])
    if "DATA_TYPE" in obj.keys():
        array = array.astype(
            sample_types(obj["DATA_TYPE"], obj["BYTES"], True)
        )
    return array


def read_table_structure(self, pointer):
    """
    Try to turn the TABLE definition into a column name / data type
    array. Requires renaming some columns to maintain uniqueness. Also
    requires unpacking columns that contain multiple entries. Also
    requires adding "placeholder" entries for undefined data (e.g.
    commas in cases where the allocated bytes is larger than given by
    BYTES, so we need to read in the "placeholder" space and then
    discard it later).

    If the table format is defined in an external FMT file, then this
    will attempt to locate it in the same directory as the data / label,
    and throw an error if it's not there.
    TODO, maybe: Grab external format files as needed.
    """
    block = self.metablock_(depointerize(pointer))
    fields = self.read_format_block(block, pointer)
    # give columns unique names so that none of our table handling explodes
    fmtdef = pd.DataFrame.from_records(fields)
    fmtdef = reindex_df_values(fmtdef)
    return fmtdef


def load_format_file(self, format_file, object_name):
    label_fns = self.get_absolute_paths(format_file)
    try:
        repo_paths = [
            Path(find_repository_root(Path(self.filename)), label_path)
            for label_path in ("label", "LABEL")
        ]
        label_fns += [Path(path, format_file) for path in repo_paths]
    except (ValueError, IndexError):
        pass
    try:
        fmtpath = check_cases(label_fns)
        aggregations, _ = read_pvl(fmtpath)
        return literalize_pvl(aggregations)
    except FileNotFoundError:
        warnings.warn(
            f"Unable to locate external table format file:\n\t"
            f"{format_file}. Try retrieving this file and "
            f"placing it in the same path as the {object_name} "
            f"file."
        )
        raise FileNotFoundError


def read_format_block(self, block, object_name):
    # load external structure specifications
    format_block = list(block.items())
    block_name = block.get('NAME')
    while "^STRUCTURE" in [obj[0] for obj in format_block]:
        format_block = self.inject_format_files(format_block, object_name)
    fields = []
    for item_type, definition in format_block:
        if item_type in ("COLUMN", "FIELD"):
            obj = dict(definition) | {'BLOCK_NAME': block_name}
            repeat_count = definition.get("ITEMS")
            obj = bit_handling.add_bit_column_info(obj, definition, self)
        elif item_type == "CONTAINER":
            obj = self.read_format_block(definition, object_name)
            repeat_count = definition.get("REPETITIONS")
        else:
            continue
        # containers can have REPETITIONS,
        # and some "columns" contain a lot of columns (ITEMS)
        # repeat the definition, renaming duplicates, for these cases
        if repeat_count is not None:
            fields = append_repeated_object(obj, fields, repeat_count)
        else:
            fields.append(obj)
    # semi-legal top-level containers not wrapped in other objects
    if object_name == "CONTAINER":
        repeat_count = block.get("REPETITIONS")
        if repeat_count is not None:
            fields = list(
                chain.from_iterable([fields for _ in range(repeat_count)])
            )
    return fields

def inject_format_files(self, block, object_name):
    format_filenames = {
        ix: kv[1] for ix, kv in enumerate(block) if kv[0] == "^STRUCTURE"
    }
    # make sure to insert the structure blocks in the correct order --
    # and remember that keys are not unique, so we have to use the index
    assembled_structure = []
    last_ix = 0
    for ix, filename in format_filenames.items():
        fmt = list(self.load_format_file(filename, object_name).items())
        assembled_structure += block[last_ix:ix] + fmt
        last_ix = ix + 1
    assembled_structure += block[last_ix:]
    return assembled_structure


def parse_table_structure(self, pointer):
    """
    Read a table's format specification and generate a DataFrame
    and -- if it's binary -- a numpy dtype object. These are later passed
    to np.fromfile or one of several ASCII table readers.
    """
    fmtdef = self.read_table_structure(pointer)
    if (
        fmtdef["DATA_TYPE"].str.contains("ASCII").any()
        or looks_like_ascii(self, pointer)
    ):
        # don't try to load it as a binary file
        return fmtdef, None
    if fmtdef is None:
        return fmtdef, np.dtype([])
    for end in ('_PREFIX', '_SUFFIX', ''):
        length = self.metaget(pointer).get(f'ROW{end}_BYTES')
        if length is not None:
            fmtdef[f'ROW{end}_BYTES'] = length
    return insert_sample_types_into_df(fmtdef, self)


# noinspection PyTypeChecker
def _interpret_as_ascii(self, fn, fmtdef, object_name):
    """
    read an ASCII table. first assume it's delimiter-separated; attempt to
    parse it as a fixed-width table if that fails.
    """
    # TODO, maybe: add better delimiter detection & dispatch
    start, length, as_rows = self.table_position(object_name)
    sep = check_explicit_delimiter(self.metablock_(object_name))
    with decompress(fn) as f:
        if as_rows is False:
            bytes_buffer = head_file(f, nbytes=length, offset=start)
            string_buffer = StringIO(bytes_buffer.read().decode())
            bytes_buffer.close()
        else:
            if start > 0:
                [next(f) for _ in range(start)]
            if length is None:
                lines = f.readlines()
            else:
                lines = [next(f) for _ in range(length)]
            string_buffer = StringIO("\r\n".join(map(bytes.decode, lines)))
        string_buffer.seek(0)
    try:
        table = pd.read_csv(string_buffer, sep=sep, header=None)
    # TODO: I'm not sure this is a good idea
    # TODO: hacky, untangle this tree
    # TODO: this won't work for compressed files, but I'm not even
    #  sure what we're using it for right now
    except (UnicodeError, AttributeError, ParserError):
        table = None
    if table is None:
        try:
            table = pd.DataFrame(
                np.loadtxt(
                    fn,
                    delimiter=",",
                    # TODO, maybe: this currently fails -- perhaps
                    #  correctly -- when there is no LABEL_RECORDS key.
                    #  but perhaps it is better to set a default of 0
                    #  and avoid use of read_fwf
                    skiprows=self.metaget_("LABEL_RECORDS"),
                )
                .copy()
                .newbyteorder("=")
            )
        except (TypeError, KeyError, ValueError):
            pass
    if table is not None:
        try:
            assert len(table.columns) == len(fmtdef.NAME.tolist())
            string_buffer.close()
            return table
        except AssertionError:
            pass
    # TODO: handle this better
    string_buffer.seek(0)
    if "BYTES" in fmtdef.columns:
        try:
            from pdr.pd_utils import compute_offsets

            colspecs = []
            position_records = compute_offsets(fmtdef).to_dict('records')
            for record in position_records:
                if np.isnan(record.get('ITEM_BYTES', np.nan)):
                    col_length = record['BYTES']
                else:
                    col_length = int(record['ITEM_BYTES'])
                colspecs.append(
                    (record['OFFSET'], record['OFFSET'] + col_length)
                )
            table = pd.read_fwf(
                string_buffer, header=None, colspecs=colspecs
            )
            string_buffer.close()
            return table
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            string_buffer.seek(0)
    table = pd.read_fwf(string_buffer, header=None)
    string_buffer.close()
    return table

def read_table(self, pointer="TABLE"):
    """
    Read a table. Parse the label format definition and then decide
    whether to parse it as text or binary.
    """
    fn = self.file_mapping[pointer]
    try:
        is_special, special_format, special_dt = check_special_structure(pointer, self)
        if is_special:
            fmtdef, dt = special_format, special_dt
        else:
            fmtdef, dt = self.parse_table_structure(pointer)
    except KeyError as ex:
        warnings.warn(f"Unable to find or parse {pointer}")
        return self._catch_return_default(pointer, ex)
    if dt is None:  # we believe object is an ascii file
        table = self._interpret_as_ascii(fn, fmtdef, pointer)
        table.columns = fmtdef.NAME.tolist()
    else:
        # TODO: this works poorly (from a usability and performance
        #  perspective; it's perfectly stable) for tables defined as
        #  a single row with tens or hundreds of thousands of columns
        table = self._interpret_as_binary(fmtdef, dt, fn, pointer)
    try:
        # If there were any cruft "placeholder" columns, discard them
        table = table.drop(
            [k for k in table.keys() if "PLACEHOLDER" in k], axis=1
        )
    except TypeError as ex:  # Failed to read the table
        return self._catch_return_default(pointer, ex)
    return table


def read_histogram(self, object_name):
    # TODO: build this out for text examples
    block = self.metablock_(object_name)
    if block.get("INTERCHANGE_FORMAT") == "ASCII":
        raise NotImplementedError(
            "ASCII histograms are not currently supported."
        )
    # TODO: this is currently a special-case version of the read_table
    #  flow. maybe: find a way to sideload definitions like this into
    #  the read_table flow after further refactoring.
    fields = []
    if (repeats := block.get("ITEMS")) is not None:
        fields = append_repeated_object(dict(block), fields, repeats)
    else:
        fields = [dict(block)]
    fmtdef = pd.DataFrame.from_records(fields)
    if "NAME" not in fmtdef.columns:
        fmtdef["NAME"] = object_name
    fmtdef = reindex_df_values(fmtdef)
    fmtdef, dt = insert_sample_types_into_df(fmtdef, self)
    return self._interpret_as_binary(
        fmtdef, dt, self.file_mapping[object_name], object_name
    )


def _interpret_as_binary(self, fmtdef, dt, fn, pointer):
    count = self.metablock_(pointer).get("ROWS")
    count = count if count is not None else 1
    with decompress(fn) as f:
        array = np_from_buffered_io(
            f, dtype=dt, offset=pdr.loaders.queries.data_start_byte(pointer), count=count
        )
    swapped = enforce_order_and_object(array, inplace=False)
    # TODO: I believe the following commented-out block is deprecated
    #  but I am leaving it in as a dead breadcrumb for now just in case
    #  something bizarre happens -michael
    # # note that pandas treats complex and simple dtypes differently when
    # # initializing single-valued dataframes
    # if (swapped.size == 1) and (len(swapped.dtype) == 0):
    #     swapped = swapped[0]
    table = pd.DataFrame(swapped)
    table.columns = fmtdef.NAME.tolist()
    table = booleanize_booleans(table, fmtdef)
    table = bit_handling.expand_bit_strings(table, fmtdef)
    return table


def _check_delimiter_stream(meta, object_name):
    """
    do I appear to point to a delimiter-separated file without
    explicit record byte length
    """
    # TODO: this may be deprecated. assess against notionally-supported
    #  products.
    if isinstance(target := get_target(meta, object_name), dict):
        if target.get("units") == "BYTES":
            return False
    # TODO: untangle this, everywhere
    if isinstance(target := get_target(meta, object_name), (list, tuple)):
        if isinstance(target[-1], dict):
            if target[-1].get("units") == "BYTES":
                return False
    # TODO: not sure this is a good assumption -- it is a bad assumption
    #  for the CHEMIN RDRs, but those labels are just wrong
    if meta.metaget_("RECORD_BYTES") is not None:
        return False
    # TODO: not sure this is a good assumption
    if not meta.metaget_("RECORD_TYPE") == "STREAM":
        return False
    textish = map(
        partial(contains, object_name), ("ASCII", "SPREADSHEET", "HEADER")
    )
    if any(textish):
        return True
    return False

def check_explicit_delimiter(block):
    if "FIELD_DELIMITER" in block.keys():
        return {
            "COMMA": ",",
            "VERTICAL_BAR": "|",
            "SEMICOLON": ";",
            "TAB": "\t",
        }[block["FIELD_DELIMITER"]]
    return ","
