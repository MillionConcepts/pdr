import os
import warnings
from functools import partial, cache
from io import StringIO
from itertools import chain
from operator import contains
from pathlib import Path
from typing import Mapping, Optional, Union, Sequence, Collection

import Levenshtein as lev
import numpy as np
import pandas as pd
from cytoolz import countby, identity
from dustgoggles.structures import dig_for_value, listify
from multidict import MultiDict
from pandas.errors import ParserError

from pdr import bit_handling
from pdr.datatypes import (
    PDS3_CONSTANT_NAMES,
    IMPLICIT_PDS3_CONSTANTS,
)
from pdr.formats import (
    LABEL_EXTENSIONS,
    pointer_to_loader,
    is_trivial,
    generic_image_properties,
    looks_like_this_kind_of_file,
    FITS_EXTENSIONS,
    check_special_offset,
    check_special_fn,
    OBJECTS_IGNORED_BY_DEFAULT,
    special_image_constants,
    ignore_if_pdf,
)
from pdr.np_utils import enforce_order_and_object, casting_to_float, \
    np_from_buffered_io
from pdr.parselabel.pds3 import (
    get_pds3_pointers,
    pointerize,
    depointerize,
    read_pvl_label,
    literalize_pvl,
)
from pdr.parselabel.pds4 import reformat_pds4_tools_label
from pdr.parselabel.utils import trim_label
from pdr.pd_utils import (
    insert_sample_types_into_df,
    reindex_df_values,
    booleanize_booleans,
)
from pdr.utils import (
    check_cases,
    append_repeated_object,
    head_file,
    decompress,
    with_extension, find_repository_root, prettify_multidict,
)


def make_format_specifications(props):
    endian, ctype = props["sample_type"][0], props["sample_type"][-1]
    struct_fmt = f"{endian}{props['pixels']}{ctype}"
    np_type = props["sample_type"][1:]
    dtype = np.dtype(f"{endian}{np_type}")
    return struct_fmt, dtype


def process_single_band_image(f, props):
    _, numpy_dtype = make_format_specifications(props)
    # TODO: added this 'count' parameter to handle a case in which the image
    #  was not the last object in the file. We might want to add it to
    #  the multiband loaders too.
    image = np_from_buffered_io(f, dtype=numpy_dtype, count=props['pixels'])
    image = image.reshape(
        (props["nrows"], props["ncols"] + props["prefix_cols"])
    )
    if props["prefix_cols"] > 0:
        prefix = image[:, : props["prefix_cols"]]
        image = image[:, props["prefix_cols"] :]
    else:
        prefix = None
    return image, prefix


def process_band_sequential_image(f, props):
    _, numpy_dtype = make_format_specifications(props)
    image = np_from_buffered_io(f, numpy_dtype, count=props["pixels"])
    image = image.reshape(
        (props["BANDS"], props["nrows"], props["ncols"] + props["prefix_cols"])
    )
    if props["prefix_cols"] > 0:
        prefix = image[:, : props["prefix_cols"]]
        image = image[:, props["prefix_cols"] :]
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
        frame = np_from_buffered_io(
            f, numpy_dtype, count=props["pixels"]).reshape(
                props["BANDS"], props["ncols"]
            )
        image.append(frame)
        del frame
    image = np.ascontiguousarray(np.array(image).swapaxes(0, 1))
    return image, prefix


def skeptically_load_header(
    path,
    object_name="header",
    start=0,
    length=None,
    as_rows=False,
    as_pvl=False,
):
    try:
        if as_pvl is True:
            try:
                from pdr.pvl_utils import cached_pvl_load

                return cached_pvl_load(check_cases(path))
            except ValueError:
                pass
        if as_rows is True:
            with open(check_cases(path)) as file:
                if start > 0:
                    file.readlines(start)
                text = "\r\n".join(file.readlines(length))
        else:
            with open(check_cases(path), 'rb') as file:
                file.seek(start)
                text = file.read(length).decode()
        return text
    except (ValueError, OSError) as ex:
        warnings.warn(f"unable to parse {object_name}: {ex}")


def pointer_to_fits_key(pointer, hdulist):
    """
    In some datasets with FITS, the PDS3 object names and FITS object
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


class Metadata(MultiDict):
    """
    MultiDict subclass intended primarily as a helper class for Data.
    includes various convenience methods for handling metadata syntaxes,
    common access and display interfaces, etc.
    # TODO: implement PDS4-style XML (or XML alias object) formatting.
    """

    def __init__(self, mapping_params, standard="PDS3", **kwargs):
        mapping, params = mapping_params
        super().__init__(mapping, **kwargs)
        self.fieldcounts = countby(identity, params)
        self.standard = standard
        if self.standard == "PDS3":
            self.formatter = literalize_pvl
        elif self.standard == "PDS4":
            # we're trusting that pds4_tools stringified everything correctly.
            # also note that this has no default capacity to describe units --
            # you have to explicitly check the 'attrib' attribute of the
            # XML node, which is not preserved by Label.to_dict().
            # TODO: replace pds4_tools' Label.to_dict() with our own
            #  literalizer function.
            self.formatter = identity
        else:
            raise NotImplementedError(
                "Syntaxes other than PDS3-style PVL and preprocessed PDS4 XML "
                "are not yet implemented."
            )
        # note that 'directly' caching these methods can result in recursive
        # reference chains behind the lru_cache API that can prevent the
        # Metadata object from being garbage-collected, which is why they are
        # hidden behind these wrappers. there may be a cleaner way to do this.
        self._metaget_interior = _metaget_factory(self)
        self._metablock_interior = _metablock_factory(self)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        return self.formatter(value)

    def metaget(self, text, default=None, evaluate=True, warn=True):
        """
        get the first value from this object whose key exactly
        matches `text`, even if it is nested inside a mapping. optionally
        evaluate it using self.formatter. raise a warning if there are
        multiple keys matching this.
        WARNING: this function's return values are memoized for performance.
        updating elements of self that have already been accessed
        with this function will not update future calls to this function.
        """
        count = self.fieldcounts.get(text)
        if count is None:
            return default
        if (count > 1) and (warn is True):
            warnings.warn(
                f"More than one value for {text} exists in the metadata. "
                f"Returning only the first.",
                DuplicateKeyWarning
            )
        return self._metaget_interior(text, default, evaluate)

    def metaget_(self, text, default=None, evaluate=True):
        """quiet-by-default version of metaget"""
        return self.metaget(text, default, evaluate, False)

    def metaget_fuzzy(self, text, evaluate=True):
        levratio = {
            key: lev.ratio(key, text) for key in set(self.fieldcounts.keys())
        }
        if levratio == {}:
            return None
        peak = max(levratio.values())
        for k, v in levratio.items():
            if v == peak:
                return self.metaget(k, None, evaluate)

    def metablock(self, text, evaluate=True, warn=True):
        """
        get the first value from this object whose key exactly
        matches `text`, even if it is nested inside a mapping, iff the value
        itself is a mapping (e.g., nested PVL block, XML 'area', etc.)
        evaluate it using self.formatter. raise a warning if there are
        multiple keys matching this.
        if there is no key matching 'text', will evaluate and return the
        metadata as a whole.
        WARNING: this function's return values are memoized for performance.
        updating elements of self that have already been accessed
        with this function and then calling it again will result in
        unpredictable behavior.
        """
        count = self.fieldcounts.get(text)
        if count is None:
            return None
        if (count > 1) and (warn is True):
            warnings.warn(
                f"More than one block named {text} exists in the metadata. "
                f"Returning only the first.",
                DuplicateKeyWarning
            )
        return self._metablock_interior(text, evaluate)

    def metablock_(self, text, evaluate=True):
        """quiet-by-default version of metablock"""
        return self.metablock(text, evaluate, False)

    def __str__(self):
        return f'Metadata({prettify_multidict(self)})'

    def __repr__(self):
        return f'Metadata({prettify_multidict(self)})'


def associate_label_file(
    data_filename: str,
    label_filename: Optional[str] = None,
    skip_check: bool = False
) -> Optional[str]:
    if label_filename is not None:
        return check_cases(Path(label_filename).absolute(), skip_check)
    elif data_filename.lower().endswith(LABEL_EXTENSIONS):
        return check_cases(data_filename)
    for lext in LABEL_EXTENSIONS:
        try:
            return check_cases(with_extension(data_filename, lext))
        except FileNotFoundError:
            continue
    return None


class Data:
    def __init__(
        self,
        fn: Union[Path, str],
        *,
        debug: bool = False,
        label_fn: Optional[Union[Path, str]] = None,
        search_paths: Union[Collection[str], str] = (),
        skip_existence_check: bool = False
    ):
        # list of the product's associated data objects
        self.index = []
        # do we raise an exception rather than a warning if loading a data
        # object fails?
        self.debug = debug
        self.filename = check_cases(Path(fn).absolute(), skip_existence_check)
        # mappings from data objects to local paths
        self.file_mapping = {}
        # known special constants per data object
        self.specials = {}
        # where can we look for files contaning data objects?
        # not yet fully implemented; only uses first (automatic) one.
        self.search_paths = [self._init_search_paths()] + listify(search_paths)
        self.standard = None
        # Attempt to identify and assign a label file
        self.labelname = associate_label_file(
            self.filename, label_fn, skip_existence_check
        )
        # cache for pds4_tools.reader.general_objects.Structure objects.
        self._pds4_structures = None
        if str(self.labelname).endswith(".xml"):
            self.standard = "PDS4"
            self._pds4_structures = {}
            self._init_pds4()
        else:
            self.standard = "PDS3"
        try:
            self.metadata = self.read_metadata()
        except (UnicodeError, FileNotFoundError) as ex:
            raise ValueError(
                f"Can't load this product's metadata: {ex}, {type(ex)}"
            )
        self._metaget_interior = _metaget_factory(self.metadata)
        self._metablock_interior = _metablock_factory(self.metadata)
        if self.standard == "PDS4":
            return
        self.pointers = get_pds3_pointers(self.metadata)
        # if self.pointers is None, we've probably got a weird edge case where
        # someone directly opened a PVL file that's not a label -- a format
        # file or something -- but there's no reason to not allow it.
        if self.pointers is not None:
            self._find_objects()

    def _init_pds4(self):
        # Just use pds4_tools if this is a PDS4 file
        import pds4_tools as pds4

        structure_list = pds4.read(
            self.labelname, lazy_load=True, quiet=True, no_scale=True
        )
        for structure in structure_list.structures:
            self._pds4_structures[structure.id.replace(" ", "_")] = structure
            self.index.append(structure.id.replace(" ", "_"))
        self._pds4_structures["label"] = structure_list.label
        self.index.append("label")

    def _init_search_paths(self):
        for target in ("labelname", "filename"):
            if (target in dir(self)) and (target is not None):
                return str(Path(self.getattr(target)).absolute().parent)
        raise FileNotFoundError

    def _find_objects(self):
        for pointer in self.pointers:
            object_name = depointerize(pointer)
            if is_trivial(object_name):
                continue
            self.index.append(object_name)

    def _object_to_filename(self, object_name):
        is_special, special_target = check_special_fn(self, object_name)
        if is_special is True:
            return self.get_absolute_paths(special_target)
        target = self.metaget_(pointerize(object_name))
        if isinstance(target, Sequence) and not (isinstance(target, str)):
            if isinstance(target[0], str):
                target = target[0]
        # TODO: should we move every check_cases call here?
        if isinstance(target, str):
            return self.get_absolute_paths(target)
        else:
            return self.filename

    def _target_path(self, object_name, raise_missing=False):
        """
        find the path on the local filesystem to the file containing a named
        data object.
        """
        if isinstance(object_name, set):
            file_list = []
            for obj in object_name:
                file = self._target_path(obj)
                file_list = file_list + [file]
            return file_list
        try:
            return check_cases(self._object_to_filename(object_name))
        except FileNotFoundError:
            if raise_missing is True:
                raise
            return None

    def unloaded(self):
        return tuple(filter(lambda k: k not in dir(self), self.index))

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
        if (object_name != "all") and (object_name not in self.index):
            raise KeyError(f"{object_name} not found in index: {self.index}.")
        if object_name == "all":
            for name in filter(
                lambda k: k not in OBJECTS_IGNORED_BY_DEFAULT, self.keys()
            ):
                try:
                    self.load(name)
                except ValueError as value_error:
                    if "already loaded" in str(value_error):
                        continue
                    raise value_error
            return
        if (object_name in dir(self)) and (reload is False):
            raise ValueError(
                f"{object_name} is already loaded; pass reload=True to "
                f"force reload."
            )
        if self.standard == "PDS4":
            return self._load_pds4(object_name)
        if self.file_mapping.get(object_name) is None:
            target = self._target_path(object_name)
            if target is None:
                warnings.warn(
                    f"{object_name} file "
                    f"{self._object_to_filename(object_name)} "
                    f"not found in path."
                )
                setattr(
                    self,
                    object_name,
                    self._catch_return_default(
                        object_name, FileNotFoundError()
                    ),
                )
                return
            self.file_mapping[object_name] = target
        try:
            obj = self.load_from_pointer(object_name, **load_kwargs)
            if obj is None:  # trivially loaded
                return
            setattr(self, object_name, obj)
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

    def _load_pds4(self, object_name):
        """
        load this object however pds4_tools wants to load this object, then
        reformat to df or expose the array handle in accordance with our type
        conventions.
        """
        structure = self._pds4_structures[object_name]
        from pds4_tools.reader.label_objects import Label
        if isinstance(structure, Label):
            setattr(self, "label", structure)
        elif structure.is_array():
            setattr(self, object_name, structure.data)
        elif structure.is_table():
            from pdr.pd_utils import structured_array_to_df
            df = structured_array_to_df(structure.data)
            df.columns = df.columns.str.replace(r"GROUP_?\d+", "", regex=True)
            setattr(self, object_name, df)
        # TODO: do other important cases exist?
        else:
            setattr(self, object_name, structure.data)

    def read_metadata(self):
        """
        Attempt to ingest a product's metadata. if it is a PDS4 product, its
        XML label will have been ingested by pds4_tools in self._init_pds4().
        in that case, simply preprocess it for Metadata.__init__.
        otherwise, if it has a detached PDS3/PVL label, ingest it with
        pdr.parselabel.pds3.read_pvl_label.
        If we have found no detached label of any kind, attempt to ingest
        attached PVL from the product's nominal path using read_pvl_label.
        """
        if self.standard == "PDS4":
            return Metadata(reformat_pds4_tools_label(self.label))
        if self.labelname is not None:  # a detached label exists
            metadata = Metadata(read_pvl_label(self.labelname))
        else:
            # look for attached label
            metadata = Metadata(read_pvl_label(self.filename))
            self.labelname = self.filename
        self.file_mapping["LABEL"] = self.labelname
        self.index.append("LABEL")
        return metadata

    def load_from_pointer(self, pointer, **load_kwargs):
        return pointer_to_loader(pointer, self)(pointer, **load_kwargs)

    def read_label(self, _pointer, fmt="text"):
        if fmt == "text":
            return trim_label(decompress(self.labelname)).decode("utf-8")
        elif fmt == "pvl":
            import pvl

            return pvl.load(self.labelname)
        raise NotImplementedError(f"The {fmt} format is not yet implemented.")

    def read_image(
        self, object_name="IMAGE", userasterio=False, special_properties=None
    ):
        """
        Read an image object from this product and return it as a numpy array.
        """
        # TODO: Check for and apply BIT_MASK.
        object_name = depointerize(object_name)
        # optional hook for rasterio, for regression/comparison testing, etc.
        if userasterio is True:
            from pdr.rasterio_utils import open_with_rasterio
            try:
                return open_with_rasterio(
                    self.file_mapping, self.filename, object_name
                )
            except IOError:
                pass
        if special_properties is not None:
            props = special_properties
        else:
            block = self.metablock_(object_name)
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
            aggregations, _ = read_pvl_label(fmtpath)
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
        if fmtdef["DATA_TYPE"].str.contains("ASCII").any():
            # don't try to load it as a binary file
            return fmtdef, None
        if fmtdef is None:
            return fmtdef, np.dtype([])
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
            fmtdef, dt = self.parse_table_structure(pointer)
        except KeyError as ex:
            warnings.warn(f"Unable to find or parse {pointer}")
            return self._catch_return_default(pointer, ex)
        if looks_like_ascii(self, dt, pointer):
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
        count = self.metablock_(pointer).get("ROWS")
        count = count if count is not None else 1
        with decompress(fn) as f:
            array = np_from_buffered_io(
                f, dtype=dt, offset=self.data_start_byte(pointer), count=count
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

    def read_text(self, object_name):
        target = self.metaget_(pointerize(object_name))
        local_path = self.file_mapping[object_name]
        try:
            if isinstance(local_path, str):
                return ignore_if_pdf(
                    self, object_name, check_cases(local_path)
                )
            elif isinstance(local_path, list):
                return [
                    ignore_if_pdf(
                        self, object_name, check_cases(each_local_path)
                    )
                    for each_local_path in local_path
                ]
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
        block = self.metablock_(object_name)
        if 'RECORDS' in block.keys():
            n_records = block['RECORDS']
        elif 'ROWS' in block.keys():
            n_records = block['ROWS']
        else:
            n_records = None
        length = None
        if (as_rows := self._check_delimiter_stream(object_name)) is True:
            if isinstance(target[1], dict):
                start = target[1]['value'] - 1
            else:
                start = target[1] - 1
            if n_records is not None:
                length = n_records
        else:
            start = self.data_start_byte(object_name)
            if "BYTES" in block.keys():
                length = block["BYTES"]
            elif n_records is not None:
                if "RECORD_BYTES" in block.keys():
                    record_length = block['RECORD_BYTES']
                elif "ROW_BYTES" in block.keys():
                    record_length = block['ROW_BYTES']
                    record_length += block.get("ROW_SUFFIX_BYTES", 0)
                elif self.metaget_("RECORD_BYTES") is not None:
                    record_length = self.metaget_("RECORD_BYTES")
                else:
                    record_length = None
                if record_length is not None:
                    length = record_length * n_records
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
            hdulist = fits.open(self.file_mapping[pointer])
            if "HEADER" in pointer:
                return hdulist[pointer_to_fits_key(pointer, hdulist)].header
            return hdulist[pointer_to_fits_key(pointer, hdulist)].data
        except Exception as ex:
            # TODO: assuming this does not need to be specified as f-string
            #  (like in read_header/tbd) -- maybe! must determine and specify
            #  what cases this exception was needed to handle
            self._catch_return_default(self.metaget_(pointer), ex)

    def handle_tiff_file(self, pointer: str, userasterio=False):
        # optional hook for rasterio usage for regression tests, etc.
        if userasterio:
            import rasterio

            return rasterio.open(self.file_mapping[pointer]).read()
        # otherwise read with pillow
        from PIL import Image
        # noinspection PyTypeChecker
        image = np.ascontiguousarray(Image.open(self.file_mapping[pointer]))
        # pillow reads images as [x, y, channel] rather than [channel, x, y]
        if len(image.shape) == 3:
            return np.ascontiguousarray(np.rollaxis(image, 2))
        return image

    def _catch_return_default(self, pointer: str, exception: Exception):
        """
        if we are in debug mode, reraise an exception. otherwise, return
        the label block only.
        """
        if self.debug is True:
            raise exception
        return self.metaget_(pointer)

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

    def get_scaled(
        self, key: str, inplace=False, float_dtype=None
    ) -> np.ndarray:
        """
        fetches copy of data object corresponding to key, masks special
        constants, then applies any scale and offset specified in the label.
        only relevant to arrays.

        if inplace is True, does calculations in-place on original array,
        with attendant memory savings and destructiveness.
        """
        # Do whatever pds4_tools would most likely do with these data.
        # TODO: shake this out much more vigorously. perhaps make
        #  the inplace and float_dtype arguments do something.
        #  check and see if implicit special constants ever still exist
        #  stealthily in PDS4 data. etc.
        if self.standard == "PDS4":
            return _scale_pds4_tools_struct(self._pds4_structures[key])
        obj, block = self._init_array_method(key)
        if key not in self.specials:
            consts = special_image_constants(self)
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
        if inplace is True and not casting_to_float(obj, scale, offset):
            if len(obj) == len(scale) == len(offset) > 1:
                for ix, _ in enumerate(scale):
                    obj[ix] = obj[ix] * scale[ix] + offset[ix]
            else:
                obj *= scale
                obj += offset
            return obj
        # if we're casting to float, permit specification of dtype
        # prior to operation (float64 is numpy's default and often excessive)
        if casting_to_float(obj, scale, offset):
            if float_dtype is not None:
                obj = obj.astype(float_dtype)
        try:
            if len(obj) == len(scale) == len(offset) > 1:
                planes = [
                    obj[ix] * scale[ix] + offset[ix]
                    for ix in range(len(scale))
                ]
                stacked = np.rollaxis(np.ma.dstack(planes), 2)
                return stacked
        except TypeError:
            pass  # len() is not usable on a float object
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
        return obj, self.metablock_(object_name)

    def tbd(self, pointer=""):
        """
        This is a placeholder function for pointers that are
        not explicitly supported elsewhere. It throws a warning and
        passes just the value of the pointer.
        """
        warnings.warn(f"The {pointer} pointer is not yet fully supported.")
        return self.metaget_(pointer)

    def trivial(self, pointer=""):
        """
        This is a trivial loader. It does not load. The purpose is to use
        for any pointers we don't want to load and instead simply want ignored.
        """
        pass

    def metaget(self, text, default=None, evaluate=True, warn=True):
        """
        get the first value from this object's metadata whose key exactly
        matches `text`, even if it is nested inside a mapping. evaluate it
        using self.metadata.formatter.
        WARNING: this function's return values are memoized for performance.
        updating elements of self.metadata that have already been accessed
        with this function will not update future calls to this function.
        """
        return self.metadata.metaget(text, default, evaluate, warn)

    def metaget_(self, text, default=None, evaluate=True):
        """quiet-by-default version of metaget"""
        return self.metadata.metaget(text, default, evaluate, False)

    def metablock(self, text, evaluate=True, warn=True):
        """
        get the first value from this object's metadata whose key exactly
        matches `text`, even if it is nested inside a mapping, iff the value
        itself is a mapping (e.g., nested PVL block, XML 'area', etc.)
        evaluate it using self.metadata.formatter. if there is no key matching
        'text', will evaluate and return the metadata as a whole.
        WARNING: this function's return values are memoized for performance.
        updating elements of self.metadata that have already been accessed
        with this function will not update future calls to this function.
        """
        return self.metadata.metablock(text, evaluate, warn)

    def metablock_(self, text, evaluate=True):
        """quiet-by-default version of metablock"""
        return self.metadata.metablock(text, evaluate, False)

    def _check_delimiter_stream(self, object_name):
        """
        do I appear to point to a delimiter-separated file without
        explicit record byte length
        """
        # TODO: this may be deprecated. assess against notionally-supported
        #  products.
        if isinstance(target := self._get_target(object_name), dict):
            if target.get("units") == "BYTES":
                return False
        # TODO: untangle this, everywhere
        if isinstance(target := self._get_target(object_name), (list, tuple)):
            if isinstance(target[-1], dict):
                if target[-1].get("units") == "BYTES":
                    return False
        # TODO: not sure this is a good assumption -- it is a bad assumption
        #  for the CHEMIN RDRs, but those labels are just wrong
        if self.metaget_("RECORD_BYTES") is not None:
            return False
        # TODO: not sure this is a good assumption
        if not self.metaget_("RECORD_TYPE") == "STREAM":
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
            rows = self.metaget_("ROWS")
            row_bytes = self.metaget_("ROW_BYTES")
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
        block = self.metablock_(object_name)
        if "RECORD_BYTES" in block.keys():
            record_bytes = block["RECORD_BYTES"]
        else:
            record_bytes = self.metaget_("RECORD_BYTES")
        start_byte = None
        if isinstance(target, int) and (record_bytes is not None):
            start_byte = record_bytes * max(target - 1, 0)
        if isinstance(target, (list, tuple)):
            if isinstance(target[-1], int) and (record_bytes is not None):
                start_byte = record_bytes * max(target[-1] - 1, 0)
            if isinstance(target[-1], dict):
                start_byte = quantity_start_byte(target[-1], record_bytes)
        elif isinstance(target, dict):
            start_byte = quantity_start_byte(target, record_bytes)
        if isinstance(target, str):
            start_byte = 0
        if start_byte is not None:
            return start_byte
        if record_bytes is None:
            return self._count_from_bottom_of_file(target)
        raise ValueError(f"Unknown data pointer format: {target}")

    def _get_target(self, object_name):
        target = self.metaget_(object_name)
        if isinstance(target, Mapping):
            target = self.metaget_(pointerize(object_name))
        return target

    # TODO: have this iterate through scopes
    def get_absolute_paths(self, filename: Union[str, Path]) -> list[str]:
        return [
            str(Path(search_path, filename).absolute())
            for search_path in self.search_paths
        ]

    # TODO: reorganize this -- common dispatch funnel with dump_browse,
    #  split up the image-gen part of _browsify_array, something like that
    def show(self, object_name=None, scaled=True, **browse_kwargs):
        if object_name is None:
            raise ValueError(
                f"please specify the name of an image object. "
                f"keys include {self.index}"
            )
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
        for obj in filter(lambda i: i in dir(self), self.index):
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
            if purge is True:
                self.__delattr__(obj)

    def __getattribute__(self, attr):
        # provide a way to sidestep special behavior
        if attr == "getattr":
            return super().__getattribute__
        # do not infinitely check if the index is in itself
        if attr == "index":
            return self.getattr("index")
        # do not attempt to lazy-load attributes that are not data objects
        if attr not in self.getattr("index"):
            return self.getattr(attr)
        try:
            return self.getattr(attr)
        except AttributeError:
            # if an attribute name corresponds to the name of a known data
            # object and that attribute hasn't been assigned, load and return
            # the data object
            self.load(attr)
            return self.getattr(attr)

    # this is redundant with __getattribute__. it is repeated here for
    # clarity and to help enable static analysis.
    def getattr(self, attr):
        """
        get an attribute of self without either lazy-loading on failure or
        risking infinite loops inside lazy-load behaviors.
        """
        return super().__getattribute__(attr)

    # The following two functions make this object act sort of dict-like
    #  in useful ways for data exploration.
    def keys(self):
        # Returns the keys for observational data and metadata objects
        return self.index

    # make it possible to get data objects with slice notation, like a dict
    def __getitem__(self, item):
        return self.__getattribute__(item)

    def __repr__(self):
        rep = f"pdr.Data({self.filename})\nkeys={self.keys()}"
        if len(self.unloaded()) > 0:
            rep += f"\nnot yet loaded: {self.unloaded()}"
        return rep

    def __str__(self):
        return self.__repr__()

    def __len__(self):
        return len(self.index)

    def __iter__(self):
        for key in self.keys():
            yield self[key]


def quantity_start_byte(quantity_dict, record_bytes):
    # TODO: are there cases in which _these_ aren't 1-indexed?
    if quantity_dict["units"] == "BYTES":
        return quantity_dict["value"] - 1
    if record_bytes is not None:
        return record_bytes * max(quantity_dict["value"] - 1, 0)


def _metaget_factory(metadata, cached=True):

    def metaget_interior(text, default, evaluate):
        value = dig_for_value(metadata, text, mtypes=(dict, MultiDict))
        if value is not None:
            return metadata.formatter(value) if evaluate is True else value
        return default

    if cached is True:
        return cache(metaget_interior)
    return metaget_interior


def _metablock_factory(metadata, cached=True):

    def metablock_interior(text, evaluate):
        value = dig_for_value(metadata, text, mtypes=(dict, MultiDict))
        if not isinstance(value, Mapping):
            value = metadata
        return metadata.formatter(value) if evaluate is True else value

    if cached is True:
        return cache(metablock_interior)
    return metablock_interior


class DuplicateKeyWarning(UserWarning):
    pass


# TODO: shake this out much more vigorously
def _scale_pds4_tools_struct(struct):
    """see pds4_tools.reader.read_arrays.new_array"""
    # TODO: apply bit_mask
    from pds4_tools.reader.data_types import (
        apply_scaling_and_value_offset
    )
    array = struct.data
    element_array = struct.meta_data['Element_Array']
    scale_kwargs = {
        'scaling_factor': element_array.get('scaling_factor'),
        'value_offset': element_array.get('value_offset')
    }
    # TODO: is this important?
    #     dtype = pds_to_numpy_type(struct.meta_data.data_type(),
    #     data=array, **scale_kwargs)
    special_constants = struct.meta_data.get('Special_Constants')
    array = apply_scaling_and_value_offset(
        array, special_constants=special_constants, **scale_kwargs)
    return array


def looks_like_ascii(data, dtype, pointer):
    return (
        (dtype is None)
        or ("SPREADSHEET" in pointer)
        or ("ASCII" in pointer)
        or (data.metablock(pointer).get('INTERCHANGE_FORMAT') == 'ASCII')
    )