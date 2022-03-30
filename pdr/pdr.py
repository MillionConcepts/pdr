import os
import warnings
from ast import literal_eval
from functools import partial, cache
from io import StringIO
from itertools import chain
from operator import contains
from pathlib import Path
from typing import Mapping, Optional, Union, Sequence

import Levenshtein as lev
import numpy as np
import pandas as pd
import pds4_tools as pds4
import pvl
from cytoolz import groupby
from dustgoggles.structures import dig_for_value
from pandas.errors import ParserError
from pvl.exceptions import ParseError

from pdr.badpvl import read_pvl_label
from pdr.datatypes import (
    PDS3_CONSTANT_NAMES,
    IMPLICIT_PDS3_CONSTANTS,
    generic_image_constants,
)
from pdr.formats import (
    LABEL_EXTENSIONS,
    pointer_to_loader,
    generic_image_properties,
    looks_like_this_kind_of_file,
    FITS_EXTENSIONS,
    check_special_offset,
    check_special_fn,
    OBJECTS_IGNORED_BY_DEFAULT,
)
from pdr.utils import (
    depointerize,
    get_pds3_pointers,
    pointerize,
    casting_to_float,
    check_cases,
    TimelessOmniDecoder,
    append_repeated_object,
    head_file, decompress,
    literalize_pvl_block, literalize_pvl,
)
from pdr.parse_components import (
    enforce_order_and_object,
    booleanize_booleans,
    filter_duplicate_pointers,
    reindex_df_values,
    insert_sample_types_into_df,
)


cached_pvl_load = cache(partial(pvl.load, decoder=TimelessOmniDecoder()))


def make_format_specifications(props):
    endian, ctype = props["sample_type"][0], props["sample_type"][-1]
    struct_fmt = f"{endian}{props['pixels']}{ctype}"
    dtype = np.dtype(f"{endian}{ctype}")
    return struct_fmt, dtype


def process_single_band_image(f, props):
    _, numpy_dtype = make_format_specifications(props)
    image = np.fromfile(f, dtype=numpy_dtype)
    image = image.reshape(
        (props["nrows"], props["ncols"] + props["prefix_cols"])
    )
    if props["prefix_cols"] > 0:
        prefix = image[:, :props["prefix_cols"]]
        image = image[:, props["prefix_cols"]:]
    else:
        prefix = None
    return image, prefix


def process_band_sequential_image(f, props):
    _, numpy_dtype = make_format_specifications(props)
    image = np.fromfile(f, dtype=numpy_dtype)
    image = image.reshape(
        (props["BANDS"], props["nrows"], props["ncols"] + props["prefix_cols"])
    )
    if props["prefix_cols"] > 0:
        prefix = image[:, :props["prefix_cols"]]
        image = image[:, props["prefix_cols"]:]
    else:
        prefix = None
    return image, prefix


def process_line_interleaved_image(f, props):
    # pixels per frame
    props["pixels"] = props["BANDS"] * props["ncols"]
    _, numpy_dtype = make_format_specifications(props)
    image, prefix = [], []
    for _ in np.arange(props["nrows"]):
        prefix.append(f.read(props["prefix_bytes"]))
        frame = np.fromfile(f, numpy_dtype, count=props["pixels"]).reshape(
            props["BANDS"], props["ncols"]
        )
        image.append(frame)
        del frame
    image = np.ascontiguousarray(np.array(image).swapaxes(0, 1))
    return image, prefix


def skeptically_load_header(
    path, object_name="header", start=0, length=None, as_rows=False
):
    try:
        try:
            return cached_pvl_load(check_cases(path))
        except ValueError:
            file = open(check_cases(path))
            if as_rows is True:
                if start > 0:
                    file.readlines(start)
                text = "\r\n".join(file.readlines(length))
            else:
                file.seek(start)
                text = file.read(length)
            file.close()
            return text
    except (ParseError, ValueError, OSError) as ex:
        warnings.warn(f"unable to parse {object_name}: {ex}")


def pointer_to_fits_key(pointer, hdulist):
    """
    In some data sets with FITS, the PDS3 object names and FITS object
    names are not identical. This function attempts to use Levenshtein
    "fuzzy matching" to identify the correlation between the two. It is not
    guaranteed to be correct! And special case handling might be required in
    the future.
    """
    if pointer in ("IMAGE", "TABLE", None, ""):
        # TODO: sometimes the primary HDU contains _just_ a header.
        #  (e.g., GALEX raw6, which is not in scope, but I'm sure something in
        #  the PDS does this awful thing too.) it might be a good idea to have
        #  a heuristic for, when we are implicitly looking for data, walking
        #  forward until we find a HDU that actually has something in it...
        #  or maybe just populating multiple keys from the HDU names.
        return 0
    levratio = [
        lev.ratio(i[1].lower(), pointer.lower())
        for i in hdulist.info(output=False)
    ]
    return levratio.index(max(levratio))


def check_explicit_delimiter(block):
    if "FIELD_DELIMITER" in block.keys():
        return {
            "COMMA": ",",
            "VERTICAL_BAR": "|",
            "SEMICOLON": ";",
            "TAB": "\t",
        }[block["FIELD_DELIMITER"]]
    return ","


def expand_bit_strings(table, fmtdef):
    if "start_bit_list" not in fmtdef.columns:
        return table
    table = convert_to_full_bit_string(table, fmtdef)
    return splice_bit_string(table, fmtdef)


def convert_to_full_bit_string(table, fmtdef):
    for column in fmtdef.index:
        if isinstance(fmtdef.start_bit_list[column], list):
            byte_column = table[fmtdef.NAME[column]]
            byte_order = determine_bit_column_byte_order(fmtdef, column)
            bit_str_column = convert_byte_column_to_bits(
                byte_column, byte_order
            )
            table[fmtdef.NAME[column]] = bit_str_column
    return table


def determine_bit_column_byte_order(fmtdef, column):
    # TODO, maybe: should this reference pdr.datatypes?
    if any(order in fmtdef.DATA_TYPE[column] for order in ['LSB', 'VAX']):
        byte_order = 'little'
    else:
        byte_order = 'big'
    return byte_order


def convert_to_bits(byte):
    return bin(byte).replace("0b", "").zfill(8)


def convert_byte_str_to_bits(byte_str, byte_order):
    return "".join(
        map(convert_to_bits, conditionally_reverse(byte_str, byte_order))
    )


def convert_byte_column_to_bits(byte_column, byte_order):
    return byte_column.map(
        partial(convert_byte_str_to_bits, byte_order=byte_order)
    )


def conditionally_reverse(iterable, byteorder):
    if byteorder == 'little':
        return reversed(iterable)
    return iter(iterable)


def splice_bit_string(table, fmtdef):
    if "start_bit_list" not in fmtdef.columns:
        return
    for column in fmtdef.index:
        if isinstance(fmtdef.start_bit_list[column], list):
            bit_column = table[fmtdef.NAME[column]]
            start_bit_list = [
                val - 1 for val in fmtdef.start_bit_list[column]
            ]  # python zero indexing
            bit_list_column = bit_column.map(
                partial(split_bits, start_bit_list=start_bit_list)
            )
            table[fmtdef.NAME[column]] = bit_list_column
    return table


def split_bits(bit_string, start_bit_list):
    return [
        bit_string[start:end]
        for start, end
        in zip(start_bit_list, start_bit_list[1:]+[None])
    ]


def add_bit_column_info(obj, definition):
    if 'BIT_STRING' in obj['DATA_TYPE']:
        start_bit_list = []
        list_of_pvl_objects_for_bit_columns = definition.getall("BIT_COLUMN")
        for pvl_obj in list_of_pvl_objects_for_bit_columns:
            start_bit = pvl_obj.get("START_BIT")
            start_bit_list.append(start_bit)
        obj['start_bit_list'] = start_bit_list
    return obj


class Data:
    def __init__(
        self,
        fn: Union[Path, str],
        *,
        debug: bool = False,
        lazy: Optional[bool] = None,
        label_fn: Optional[Union[Path, str]] = None,
    ):
        self.debug = debug
        self.filename = str(Path(fn).absolute())
        fn = self.filename
        self.file_mapping = {}
        self.labelname = None
        # index of all of the pointers to data
        self.index = []
        # known special constants per pointer
        self.specials = {}
        implicit_lazy_exception = None
        # Attempt to identify and assign a label file
        if label_fn is not None:
            self.labelname = str(Path(label_fn).absolute())
            label_fn = self.labelname
            lazy = False if lazy is None else lazy
        elif fn.endswith(LABEL_EXTENSIONS):
            self.labelname = fn
            lazy = False if lazy is None else lazy
        else:
            implicit_lazy_exception = fn
            lazy = True if lazy is None else lazy
        while self.labelname is None:
            for lext in LABEL_EXTENSIONS:
                try:
                    self.labelname = check_cases(
                        fn.replace(Path(fn).suffix, lext)
                    )
                except FileNotFoundError:
                    continue
            break
        label = self.read_label()
        setattr(self, "LABEL", label)
        self.index += ["LABEL"]
        if self.labelname.endswith(".xml"):
            # Just use pds4_tools if this is a PDS4 file
            # TODO: do this better, including lazy
            data = pds4.read(self.labelname, quiet=True)
            for structure in data.structures:
                setattr(self, structure.id.replace(" ", "_"), structure.data)
                self.index += [structure.id.replace(" ", "_")]
            return

        pt_groups = groupby(lambda pt: pt[0], get_pds3_pointers(label))
        pointers = []
        # noinspection PyArgumentList
        pointers = filter_duplicate_pointers(pointers, pt_groups)
        setattr(self, "pointers", pointers)
        self._handle_initial_load(lazy, implicit_lazy_exception)
        if (lazy is False) or (implicit_lazy_exception == fn):
            self._handle_fallback_load()

    def _handle_initial_load(self, lazy, implicit_lazy_exception):
        for pointer in self.pointers:
            object_name = depointerize(pointer)
            if pointer_to_loader(object_name, self) == self.trivial:
                continue
            self.index.append(object_name)
            self.file_mapping[object_name] = self._target_path(object_name)
            if object_name in OBJECTS_IGNORED_BY_DEFAULT:
                continue
            loaded = False
            if lazy is False:
                self.load(object_name)
                loaded = True
            elif lazy is True:
                if isinstance(implicit_lazy_exception, str):
                    if (
                        self.file_mapping[object_name].lower()
                        == implicit_lazy_exception.lower()
                    ):
                        self.load(object_name)
                        loaded = True
            if loaded is False:
                setattr(self, object_name, None)

    def _object_to_filename(self, object_name):
        is_special, special_target = check_special_fn(self, object_name)
        if is_special is True:
            return self.get_absolute_path(special_target)
        target = self.labelget(pointerize(object_name))
        if isinstance(target, Sequence) and not (isinstance(target, str)):
            if isinstance(target[0], str):
                target = target[0]
        if isinstance(target, str):
            return self.get_absolute_path(target)
        else:
            return self.filename

    def _target_path(self, object_name, raise_missing=False):
        target = self._object_to_filename(object_name)
        try:
            if isinstance(target, str):
                return check_cases(self.get_absolute_path(target))
            else:
                return check_cases(self.filename)
        except FileNotFoundError:
            if raise_missing is True:
                raise
            return None

    def _handle_fallback_load(self):
        """
        attempt to handle cases in which objects don't have explicit pointers
        but we want to get them anyway
        """
        non_labels = [
            i for i in self.index if (i != "LABEL") and hasattr(self, i)
        ]
        if all((self[i] is None for i in non_labels)):
            try:
                self._fallback_image_load()
            except KeyboardInterrupt:
                raise
            except Exception as ex:
                pass

    def _fallback_image_load(self):
        """
        sometimes images do not have explicit pointers, so we may want to
        try to read an image out of the file anyway.
        """
        if looks_like_this_kind_of_file(self.filename, FITS_EXTENSIONS):
            image = self.handle_fits_file(self.filename)
        else:
            # TODO: this will presently break if passed an unlabeled
            #  image file. read_image() should probably be made more
            #  permissive in some way to handle this, or we should at
            #  least give a useful error message.
            image = self.read_image()
        if image is not None:
            setattr(self, "IMAGE", image)
            self.index += ["IMAGE"]

    def load(self, object_name, reload=False, **load_kwargs):
        if object_name not in self.index:
            raise KeyError(f"{object_name} not found in index: {self.index}.")
        if self.file_mapping.get(object_name) is None:
            warnings.warn(
                f"{object_name} file {self._object_to_filename(object_name)} "
                f"not found in path."
            )
            setattr(
                self,
                object_name,
                self._catch_return_default(object_name, FileNotFoundError()),
            )
            return
        if hasattr(self, object_name):
            if (self[object_name] is not None) and (reload is False):
                raise ValueError(
                    f"{object_name} is already loaded; pass reload=True to "
                    f"force reload."
                )
        try:
            setattr(
                self,
                object_name,
                self.load_from_pointer(object_name, **load_kwargs),
            )
            return
        except KeyboardInterrupt:
            raise
        except Exception as ex:
            if isinstance(ex, NotImplementedError):
                warnings.warn(
                    f"This product's {object_name} is not yet supported: {ex}."
                )
            elif isinstance(ex, FileNotFoundError):
                warnings.warn(
                    f"Unable to find files required by {object_name}."
                )
            else:
                warnings.warn(f"Unable to load {object_name}: {ex}")
            setattr(
                self, object_name, self._catch_return_default(object_name, ex)
            )

    def read_label(self):
        """
        Attempts to read the data label, checking first whether this is a
        PDS4 file, then whether it has a detached label, then whether it
        has an attached label. Returns None if all of these attempts are
        unsuccessful.
        """
        if self.labelname:  # a detached label exists
            if Path(self.labelname).suffix.lower() == ".xml":
                label = pds4.read(self.labelname, quiet=True).label.to_dict()
            else:
                label = read_pvl_label(self.labelname)
                # label = cached_pvl_load(self.labelname)
            self.file_mapping["LABEL"] = self.labelname
            return label
        # look for attached label
        # label = pvl.loads(
        #     trim_label(decompress(self.filename)),
        #     decoder=TimelessOmniDecoder(),
        # )
        label = read_pvl_label(self.filename)
        self.file_mapping["LABEL"] = self.filename
        self.labelname = self.filename
        return label

    def load_from_pointer(self, pointer, **load_kwargs):
        return pointer_to_loader(pointer, self)(pointer, **load_kwargs)

    def open_with_rasterio(self, object_name):
        import rasterio
        from rasterio.errors import NotGeoreferencedWarning, RasterioIOError

        # we do not want rasterio to shout about data not being
        # georeferenced; most rasters are not _supposed_ to be georeferenced.
        warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
        if object_name in self.file_mapping.keys():
            fn = self.file_mapping[object_name]
        else:
            fn = check_cases(self.filename)
        try:
            dataset = rasterio.open(fn)
        # some rasterio drivers can only make sense of a label, attached
        # or otherwise
        except RasterioIOError:
            dataset = rasterio.open(self.file_mapping["LABEL"])
        if len(dataset.indexes) == 1:
            # Make 2D images actually 2D
            return dataset.read()[0, :, :]
        else:
            return dataset.read()

    def read_image(
        self, object_name="IMAGE", userasterio=True, special_properties=None
    ):
        """
        Read an image file as a numpy array. Defaults to using `rasterio`,
        and then tries to parse the file directly.
        """
        # TODO: Check for and apply BIT_MASK.
        object_name = depointerize(object_name)
        if object_name == "IMAGE" or self.filename.lower().endswith("qub"):
            # TODO: we could generalize this more by trying to find filenames.
            if userasterio is True:
                from rasterio.errors import RasterioIOError

                try:
                    return self.open_with_rasterio(object_name)
                except RasterioIOError:
                    pass
        if special_properties is not None:
            props = special_properties
        else:
            block = self.labelblock(object_name)
            if block is None:
                return None  # not much we can do with this!
            props = generic_image_properties(object_name, block, self)
        # a little decision tree to seamlessly deal with compression
        fn = self.file_mapping[object_name]
        f = decompress(fn)
        f.seek(props["start_byte"])
        try:
            # Make sure that single-band images are 2-dim arrays.
            if props["BANDS"] == 1:
                image, prefix = process_single_band_image(f, props)
            elif props["band_storage_type"] == "BAND_SEQUENTIAL":
                image, prefix = process_band_sequential_image(f, props)
            elif props["band_storage_type"] == "LINE_INTERLEAVED":
                image, prefix = process_line_interleaved_image(f, props)
            else:
                warnings.warn(
                    f"Unknown BAND_STORAGE_TYPE={props['band_storage_type']}. "
                    f"Guessing BAND_SEQUENTIAL."
                )
                image, prefix = process_band_sequential_image(f, props)
        except Exception as ex:
            raise ex
        finally:
            f.close()
        if "PREFIX" in object_name:
            return prefix
        return image

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
        block = self.labelblock(depointerize(pointer))
        fields = self.read_format_block(block, pointer)
        # give columns unique names so that none of our table handling explodes
        fmtdef = pd.DataFrame.from_records(fields)
        fmtdef = reindex_df_values(fmtdef)
        return fmtdef

    def load_format_file(self, format_file, object_name):
        try:
            fmtpath = check_cases(self.get_absolute_path(format_file))
            return cached_pvl_load(fmtpath)
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
        while "^STRUCTURE" in [obj[0] for obj in format_block]:
            format_block = self.inject_format_files(format_block, object_name)
        fields = []
        for item_type, definition in format_block:
            if item_type in ("COLUMN", "FIELD"):
                obj = dict(definition)
                print("*******NAME:  ", obj["NAME"], "*****")
                repeat_count = definition.get("ITEMS")
                obj = add_bit_column_info(obj, definition)
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
        Generate a dtype array to later pass to numpy.fromfile
        to unpack the table data according to the format given in the
        label.
        """
        fmtdef = self.read_table_structure(pointer)
        if fmtdef["DATA_TYPE"].str.contains("ASCII").any():
            # don't try to load it as a binary file
            return fmtdef, None
        if fmtdef is None:
            return fmtdef, np.dtype([])
        return insert_sample_types_into_df(fmtdef, self)

    def _interpret_as_dsv(self, fn, fmtdef, object_name):
        # TODO, maybe: add better delimiter detection & dispatch
        start, length, as_rows = self.table_position(object_name)
        sep = check_explicit_delimiter(self.labelblock(object_name))
        if as_rows is False:
            bytes_buffer = head_file(fn, nbytes=length, offset=start)
            string_buffer = StringIO(bytes_buffer.read().decode())
            bytes_buffer.close()
        else:
            with open(fn) as file:
                if start > 0:
                    file.readlines(start)
                string_buffer = StringIO("\r\n".join(file.readlines(length)))
            string_buffer.seek(0)
        try:
            table = pd.read_csv(string_buffer, sep=sep, header=None)
        # TODO: I'm not sure this is a good idea
        # TODO: hacky, untangle this tree
        except (UnicodeError, AttributeError, ParserError):
            table = None
        if table is None:
            try:
                table = pd.DataFrame(
                    np.loadtxt(
                        fn,
                        delimiter=",",
                        skiprows=self.labelget("LABEL_RECORDS"),
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
                table = pd.read_fwf(
                    string_buffer, header=None, widths=fmtdef.BYTES.values
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
        target = self.labelget(pointerize(pointer))
        if isinstance(target, Sequence) and not (isinstance(target, str)):
            if isinstance(target[0], str):
                target = target[0]
        if isinstance(target, str):
            fn = check_cases(self.get_absolute_path(target))
        else:
            fn = check_cases(self.filename)
        try:
            fmtdef, dt = self.parse_table_structure(pointer)
        except KeyError as ex:
            warnings.warn(f"Unable to find or parse {pointer}")
            return self._catch_return_default(pointer, ex)
        if (dt is None) or ("SPREADSHEET" in pointer) or ("ASCII" in pointer):
            table = self._interpret_as_dsv(fn, fmtdef, pointer)
            table.columns = fmtdef.NAME.tolist()
        else:
            # TODO: this will always throw an exception for text files
            #  because offset is only a legal argument for binary files
            #  --but arguably text files should never get here
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
        block = self.labelblock(object_name)
        if block.get("INTERCHANGE_FORMAT") != "BINARY":
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
        count = self.labelblock(pointer).get("ROWS")
        count = count if count is not None else 1
        array = np.fromfile(
            fn, dtype=dt, offset=self.data_start_byte(pointer), count=count
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
        table = expand_bit_strings(table, fmtdef)
        return table

    def read_text(self, object_name):
        target = self.labelget(pointerize(object_name))
        local_path = self.get_absolute_path(
            self.labelget(pointerize(object_name))
        )
        try:
            return open(check_cases(local_path)).read()
        except FileNotFoundError as ex:
            exception = ex
            warnings.warn(f"couldn't find {target}")
        except UnicodeDecodeError as ex:
            exception = ex
            warnings.warn(f"couldn't parse {target}")
        return self._catch_return_default(object_name, exception)

    def read_header(self, object_name="HEADER"):
        """Attempt to read a file header."""
        start, length, as_rows = self.table_position(object_name)
        return skeptically_load_header(
            self.file_mapping[object_name], object_name, start, length, as_rows
        )

    def table_position(self, object_name):
        target = self._get_target(object_name)
        block = self.labelblock(object_name)
        length = None
        if (as_rows := self._check_delimiter_stream(object_name)) is True:
            start = target[1] - 1
            if "RECORDS" in block.keys():
                length = block["RECORDS"]
        else:
            start = self.data_start_byte(object_name)
            if "BYTES" in block.keys():
                length = block["BYTES"]
            elif ("RECORDS" in block.keys()) and (
                "RECORD_BYTES" in self.LABEL.keys()
            ):
                length = block["RECORDS"] * self.LABEL["RECORD_BYTES"]
        return start, length, as_rows

    def handle_fits_file(self, pointer=""):
        """
        This function attempts to read all FITS files, compressed or
        uncompressed, with astropy.io.fits. Files with 'HEADER' pointer
        return the header, all others return data.
        TODO, maybe: dispatch to decompress() for weirdo compression
          formats, but possibly not right here? hopefully we shouldn't need
          to handle compressed FITS files too often anyway.
        """
        from astropy.io import fits

        try:
            hdulist = fits.open(check_cases(self.file_mapping[pointer]))
            if "HEADER" in pointer:
                return hdulist[pointer_to_fits_key(pointer, hdulist)].header
            return hdulist[pointer_to_fits_key(pointer, hdulist)].data
        except Exception as ex:
            # TODO: assuming this does not need to be specified as f-string
            #  (like in read_header/tbd) -- maybe! must determine and specify
            #  what cases this exception was needed to handle
            self._catch_return_default(self.labelget(pointer), ex)

    def _catch_return_default(self, pointer: str, exception: Exception):
        """
        if we are in debug mode, reraise an exception. otherwise, return
        the label block only.
        """
        if self.debug is True:
            raise exception
        return self.labelget(pointer)

    def find_special_constants(self, key):
        """
        attempts to find special constants in the associated object
        by referencing the label and "standard" implicit special constant
        values, then populates self.special_constants as appropriate.
        TODO: doesn't do anything for PDS4 products at present. Also, we
         need an attribute for distinguishing PDS3 from PDS4 products.
        """
        obj, block = self._init_array_method(key)
        # check for explicitly-defined special constants
        specials = {
            name: block[name]
            for name in PDS3_CONSTANT_NAMES
            if (name in block.keys()) and not (block[name] == "N/A")
        }
        # ignore uint8 implicit constants (0, 255) for now -- too problematic
        # TODO: maybe add an override
        if obj.dtype.name == "uint8":
            self.specials[key] = specials
            return
        # check for implicit constants appropriate to the sample type
        implicit_possibilities = IMPLICIT_PDS3_CONSTANTS[obj.dtype.name]
        specials |= {
            possibility: constant
            for possibility, constant in implicit_possibilities.items()
            if constant in obj
        }
        self.specials[key] = specials

    def get_scaled(self, key: str, inplace=False) -> np.ndarray:
        """
        fetches copy of data object corresponding to key, masks special
        constants, then applies any scale and offset specified in the label.
        only relevant to arrays.

        if inplace is True, does calculations in-place on original array,
        with attendant memory savings and destructiveness.

        TODO: as above, does nothing for PDS4.
        """
        obj, block = self._init_array_method(key)
        if key not in self.specials:
            consts = generic_image_constants(self)
            self.specials[key] = consts
            if not consts:
                self.find_special_constants(key)
        if self.specials[key] != {}:
            obj = np.ma.MaskedArray(obj)
            obj.mask = np.isin(obj.data, list(self.specials[key].values()))
        scale = 1
        offset = 0
        if "SCALING_FACTOR" in block.keys():
            scale = block["SCALING_FACTOR"]
        if "OFFSET" in block.keys():
            offset = block["OFFSET"]
        # meaningfully better for enormous unscaled arrays
        if (scale == 1) and (offset == 0):
            return obj
        # try to perform the operation in-place if requested, although if
        # we're casting to float, we can't
        # TODO: detect rollover cases, etc.
        if (inplace is True) and not casting_to_float(obj, scale, offset):
            obj *= scale
            obj += offset
            return obj
        return obj * scale + offset

    def _init_array_method(
        self, object_name: str
    ) -> tuple[np.ndarray, Mapping]:
        """
        helper function -- grab an array-type object and its label "block".
        specifying a generic return type because eventually we would like this
        to work with XML trees as well as PVL
        """
        obj = self[object_name]
        if not isinstance(obj, np.ndarray):
            raise TypeError("this method is only applicable to arrays.")
        return obj, self.labelblock(object_name)

    def tbd(self, pointer=""):
        """
        This is a placeholder function for pointers that are
        not explicitly supported elsewhere. It throws a warning and
        passes just the value of the pointer.
        """
        warnings.warn(f"The {pointer} pointer is not yet fully supported.")
        return self.labelget(pointer)

    def trivial(self, pointer=""):
        """
        This is a trivial loader. It does not load. The purpose is to use
        for any pointers we don't want to load and instead simply want ignored.
        """
        pass

    @cache
    def labelget(self, text, evaluate=True):
        """
        get the first value from this object's label whose key exactly matches
        `text`. TODO: very crude. needs to work with XML.
        """
        value = dig_for_value(self.LABEL, text)
        if value is None:
            return None
        return literalize_pvl(value) if evaluate is True else value

    @cache
    def labelblock(self, text, make_literal = True):
        """
        get the first value from this object's label whose key
        exactly matches `text` iff it is a mapping (e.g. nested PVL block);
        otherwise, returns the label as a whole.
        TODO: very crude. needs to work with XML.
        """
        what_got_dug = dig_for_value(self.LABEL, text)
        if not isinstance(what_got_dug, Mapping):
            what_got_dug = self.LABEL
        if make_literal is True:
            print(f"*****{text}*****")
            return literalize_pvl_block(what_got_dug)
        return what_got_dug

    def _check_delimiter_stream(self, object_name):
        """
        do I appear to point to a delimiter-separated file without
        explicit record byte length?
        """
        if isinstance(target := self._get_target(object_name), pvl.Quantity):
            if target.units == "BYTES":
                return False
        # TODO: untangle this, everywhere
        if isinstance(target := self._get_target(object_name), list):
            if isinstance(target[-1], pvl.Quantity):
                if target[-1].units == "BYTES":
                    return False
        # TODO: not sure this is a good assumption -- it is a bad assumption
        #  for the CHEMIN RDRs, but those labels are just wrong
        if self.LABEL.get("RECORD_BYTES") is not None:
            return False
        # TODO: not sure this is a good assumption
        if not self.LABEL.get("RECORD_TYPE") == "STREAM":
            return False
        textish = map(
            partial(contains, object_name), ("ASCII", "SPREADSHEET", "HEADER")
        )
        if any(textish):
            return True
        return False

    def _count_from_bottom_of_file(self, target):
        if isinstance(target, int):
            # Counts up from the bottom of the file
            rows = self.labelget("ROWS")
            row_bytes = self.labelget("ROW_BYTES")
            tab_size = rows * row_bytes
            # TODO: should be the filename of the target
            file_size = os.path.getsize(self.filename)
            return file_size - tab_size
        if isinstance(target, (list, tuple)):
            if isinstance(target[0], int):
                return target[0]
        raise ValueError(f"unknown data pointer format: {target}")

    def data_start_byte(self, object_name):
        """
        Determine the first byte of the data in a file from its pointer.
        """
        # TODO: like similar functions, this will currently break with PDS4

        # hook for defining internally-consistent-but-nonstandard special cases
        is_special, special_byte = check_special_offset(object_name, self)
        if is_special:
            return special_byte
        target = self._get_target(object_name)
        labelblock = self.labelblock(object_name)
        if "RECORD_BYTES" in labelblock.keys():
            record_bytes = labelblock["RECORD_BYTES"]
        else:
            record_bytes = self.labelget("RECORD_BYTES")
        if record_bytes is None:
            return self._count_from_bottom_of_file(target)
        if isinstance(target, int):
            return record_bytes * max(target - 1, 0)
        if isinstance(target, (list, tuple)) and (record_bytes is not None):
            if isinstance(target[-1], int):
                return record_bytes * max(target[-1] - 1, 0)
            if isinstance(target[-1], pvl.Quantity):
                if target[-1].units == "BYTES":
                    # TODO: are there cases in which _these_ aren't 1-indexed?
                    return target[-1].value - 1
                return record_bytes * max(target[-1].value - 1, 0)
            return 0
        elif isinstance(target, (list, tuple)) and isinstance(target[-1], pvl.Quantity):
            if target[-1].units == "BYTES":  # TODO: untangle this
                return target[-1].value - 1
        elif isinstance(target, pvl.Quantity):
            if target.units == "BYTES":
                return target.value - 1
            return record_bytes * max(target.value - 1, 0)
        if isinstance(target, str):
            return 0
        else:
            raise ParseError(f"Unknown data pointer format: {target}")

    def _get_target(self, object_name):
        target = self.labelget(object_name)
        if isinstance(target, Mapping):
            target = self.labelget(pointerize(object_name))
        return target

    # The following two functions make this object act sort of dict-like
    #  in useful ways for data exploration.
    def keys(self):
        # Returns the keys for observational data and metadata objects
        return self.index

    def get_absolute_path(self, file):
        if self.labelname:
            return str(
                Path(Path(self.labelname).absolute().parent, Path(file).name)
            )
        elif self.filename:
            return str(
                Path(Path(self.filename).absolute().parent, Path(file).name)
            )
        else:
            return file

    # TODO: reorganize this -- common dispatch funnel with dump_browse,
    #  split up the image-gen part of _browsify_array, something like that
    def show(self, object_name=None, scaled=True, **browse_kwargs):
        if object_name is None:
            object_name = [obj for obj in self.index if "IMAGE" in obj]
            if object_name is None:
                raise ValueError("please specify the name of an image object.")
            object_name = object_name[0]
        if not isinstance(self[object_name], np.ndarray):
            raise TypeError("Data.show only works on array data.")
        if scaled is True:
            obj = self.get_scaled(object_name)
        else:
            obj = self[object_name]
        # no need to have all this mpl stuff in the namespace normally
        from pdr.browsify import _browsify_array

        return _browsify_array(obj, save=False, outbase="", **browse_kwargs)

    def dump_browse(
        self,
        prefix: Optional[Union[str, Path]] = None,
        outpath: Optional[Union[str, Path]] = None,
        scaled=True,
        purge=False,
        **browse_kwargs,
    ) -> None:
        """
        attempt to dump all data objects associated with this Data object
        to disk.

        if purge is True, objects are deleted as soon as they are dumped,
        rendering this Data object 'empty' afterwards.

        browse_kwargs are passed directly to pdr.browisfy.dump_browse.
        """
        if prefix is None:
            prefix = Path(self.filename).stem
        if outpath is None:
            outpath = Path(".")
        for obj in self.index:
            if not hasattr(self, obj):
                continue
            outfile = str(Path(outpath, f"{prefix}_{obj}"))
            # no need to have all this mpl stuff in the namespace normally
            from pdr.browsify import browsify

            dump_it = partial(browsify, purge=purge, **browse_kwargs)
            if isinstance(self[obj], np.ndarray):
                if scaled == "both":
                    dump_it(
                        self.get_scaled(obj), outfile + "_scaled", purge=False
                    )
                    dump_it(self[obj], outfile + "_unscaled")
                elif scaled is True:
                    dump_it(self.get_scaled(obj, inplace=purge), outfile)
                elif scaled is False:
                    dump_it(self[obj], outfile)
                else:
                    raise ValueError(f"unknown scaling argument {scaled}")
            else:
                dump_it(self[obj], outfile)
            if (purge is True) and (obj != "LABEL"):
                self.__delattr__(obj)

    # make it possible to get data objects with slice notation, like a dict
    def __getitem__(self, item):
        return getattr(self, item)

    def __repr__(self):
        not_loaded = []
        for k in self.keys():
            if not hasattr(self, k):
                not_loaded.append(k)
            elif self[k] is None:
                not_loaded.append(k)
        rep = f"pdr.Data({self.filename})\nkeys={self.keys()}"
        if len(not_loaded) > 0:
            rep += f"\nnot yet loaded: {not_loaded}"
        return rep

    def __str__(self):
        return self.__repr__()

    def __len__(self):
        return len(self.index)

    def __iter__(self):
        for key in self.keys():
            yield self[key]
