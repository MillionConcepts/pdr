from __future__ import annotations
import re
import warnings
from _operator import mul
from functools import reduce
from itertools import product, chain
from pathlib import Path
from types import MappingProxyType
from typing import Sequence, Mapping, TYPE_CHECKING

import numpy as np
import pandas as pd
from multidict import MultiDict

from pdr import bit_handling
from pdr.datatypes import sample_types
from pdr.formats import check_special_offset, check_special_block
from pdr.func import specialize
from pdr.loaders._helpers import quantity_start_byte, \
    _count_from_bottom_of_file, looks_like_ascii, _check_delimiter_stream
from pdr.parselabel.pds3 import pointerize, read_pvl, literalize_pvl
from pdr.pd_utils import insert_sample_types_into_df, reindex_df_values
from pdr.utils import append_repeated_object, find_repository_root, check_cases

if TYPE_CHECKING:
    from pdr.pdrtypes import PDRLike


def generic_qube_properties(block: MultiDict, band_storage_type) -> dict:
    props = {}
    use_block = block if "CORE" not in block.keys() else block["CORE"]
    props["BYTES_PER_PIXEL"] = int(use_block["CORE_ITEM_BYTES"])  # / 8)
    # TODO: this should probably have for_numpy set to True
    props["sample_type"] = sample_types(
        use_block["CORE_ITEM_TYPE"], props["BYTES_PER_PIXEL"]
    )
    if "AXIS_NAME" in set(block.keys()).union(use_block.keys()):
        # TODO: if we end up handling this at higher level in the PVL parser,
        #  remove this splitting stuff
        axnames = block.get("AXIS_NAME")
        if axnames is None:
            axnames = use_block.get("AXIS_NAME")
        props["axnames"] = tuple(re.sub(r"[)( ]", "", axnames).split(","))
        ax_map = {"LINE": "nrows", "SAMPLE": "ncols", "BAND": "nbands"}
        for ax, count in zip(props["axnames"], use_block["CORE_ITEMS"]):
            props[ax_map[ax]] = count
    else:
        props["nrows"] = use_block["CORE_ITEMS"][2]
        props["ncols"] = use_block["CORE_ITEMS"][0]
    props["band_storage_type"] = band_storage_type
    if props["band_storage_type"] is None:
        if props.get("axnames") is not None:
            # noinspection PyTypeChecker
            # writing keys in last-axis-fastest for clarity. however,
            # ISIS always (?) uses first-axis-fastest, hence `reversed` below.
            props["band_storage_type"] = {
                ("BAND", "LINE", "SAMPLE"): "BAND_SEQUENTIAL",
                ("LINE", "SAMPLE", "BAND"): "SAMPLE_INTERLEAVED",
                ("LINE", "BAND", "SAMPLE"): "LINE_INTERLEAVED",
            }[tuple(reversed(props["axnames"]))]
        else:
            props["band_storage_type"] = "ISIS2_QUBE"
    # noinspection PyTypeChecker
    props |= extract_axplane_metadata(block, props)
    # noinspection PyTypeChecker
    props |= extract_linefix_metadata(block, props)
    # TODO: unclear whether lower-level linefixes ever appear on qubes
    return props


def extract_axplane_metadata(block: MultiDict, props: dict) -> dict:
    """extract metadata for ISIS-style side/back/bottomplanes"""
    # shorthand relating side/backplane "direction" to row/column axes.
    rowcol = {"SAMPLE": "col", "LINE": "row", "BAND": "band"}
    axplane_metadata = {"rowpad": 0, "colpad": 0, "bandpad": 0}
    for ax, side in product(("BAND", "LINE", "SAMPLE"), ("PREFIX", "SUFFIX")):
        if (itembytes := block.get(f"{ax}_{side}_ITEM_BYTES")) is None:
            continue
        if (itemcount := block.get(f"{side}_ITEMS")) is None:
            raise ValueError(
                f"Specified {ax} {side} item bytes with no specified "
                f"number of items; can't interpret."
            )
        if props.get("axnames") is None:
            raise ValueError(
                f"Specified {ax} {side} items with no specified axis "
                f"order; can't interpret."
            )
        # TODO: handle variable-length axplanes
        fixbytes = itemcount[props["axnames"].index(ax)] * itembytes
        fix_pix = fixbytes / props["BYTES_PER_PIXEL"]
        if int(fix_pix) != fix_pix:
            raise NotImplementedError(
                "Pre/suffix itemsize < array itemsize is not supported."
            )
        axplane_metadata[f"{side.lower()}_{rowcol[ax]}s"] = int(fix_pix)
        axplane_metadata[f"{rowcol[ax]}pad"] += int(fix_pix)
    return axplane_metadata


def extract_linefix_metadata(block: MultiDict, props: dict) -> dict:
    """extract metadata for line prefix/suffix 'tables'"""
    linefix_metadata = {"linepad": 0}
    for side in ("PREFIX", "SUFFIX"):
        if (fixbytes := block.get(f"LINE_{side}_BYTES")) in (0, None):
            continue
        fix_pix = fixbytes / props["BYTES_PER_PIXEL"]
        if fix_pix != int(fix_pix):
            raise NotImplementedError(
                "Line pre/suffixes not aligned with array element size are "
                "not supported."
            )
        linefix_metadata[f"line_{side.lower()}_pix"] = int(fix_pix)
        linefix_metadata["linepad"] += int(fix_pix)
    return linefix_metadata


def gt0f(seq):
    return tuple(filter(lambda x: x > 0, seq))


def check_fix_validity(props):
    if (props["linepad"] > 0) and (
        (props["rowpad"] + props["colpad"] + props["bandpad"]) > 0
    ):
        raise NotImplementedError(
            "Objects that contain both 'conventional' line pre/suffixes and "
            "ISIS-style side/back/bottomplanes are not supported."
        )
    if len(gt0f((props["rowpad"], props["colpad"], props["bandpad"]))) > 1:
        raise NotImplementedError(
            "ISIS-style axplanes along multiple axes are not supported."
        )
    if (props["linepad"] > 0) and props["band_storage_type"] not in (
        None,
        "LINE_INTERLEAVED",
    ):
        raise NotImplementedError(
            "'Conventional' line pre/suffixes are not supported for non-BIL "
            "multiband images."
        )


def check_if_qube(name, block, band_storage_type):
    if "QUBE" in name:  # ISIS2 QUBE format
        return True, generic_qube_properties(block, band_storage_type)
    else:
        return False, None


def get_image_properties(gen_props) -> dict:
    props = gen_props
    check_fix_validity(props)
    props["pixels"] = (
        (props["nrows"] + props["rowpad"])
        * (props["ncols"] + props["colpad"] + props["linepad"])
        * (props["nbands"] + props["bandpad"])
    )
    return props


def im_sample_type(base_samp_info):
    if base_samp_info["SAMPLE_TYPE"] != "":
        return sample_types(
            base_samp_info["SAMPLE_TYPE"],
            base_samp_info["BYTES_PER_PIXEL"],
            for_numpy=True
        )


def base_sample_info(block):
    return {
        'BYTES_PER_PIXEL': int(block.get('SAMPLE_BITS', 0) / 8),
        'SAMPLE_TYPE': block.get("SAMPLE_TYPE", "")
    }


def generic_image_properties(block, sample_type):
    props = {"BYTES_PER_PIXEL": int(block["SAMPLE_BITS"] / 8), "sample_type": sample_type,
             "nrows": block["LINES"], "ncols": block["LINE_SAMPLES"]}
    if "BANDS" in block:
        props["nbands"] = block["BANDS"]
        props["band_storage_type"] = block.get("BAND_STORAGE_TYPE", None)
        # TODO: assess whether this is always ok
        if props["band_storage_type"] is None and props["nbands"] > 1:
            raise ValueError(
                "Cannot read 3D image with no specified band storage type."
            )
    else:
        props["nbands"] = 1
        props["band_storage_type"] = None
    props |= extract_axplane_metadata(block, props)
    props |= extract_linefix_metadata(block, props)
    return props


def get_qube_band_storage_type(block):
    band_storage_type = block.get("BAND_STORAGE_TYPE")
    return band_storage_type


def check_array_for_subobject(block):
    valid_subobjects = ["ARRAY", "BIT_ELEMENT", "COLLECTION", "ELEMENT"]
    subobj = [sub for sub in valid_subobjects if sub in block]
    if len(subobj) > 1:
        raise ValueError(
            f"ARRAY objects may only have one subobject (this has "
            f"{len(subobj)})"
        )
    if len(subobj) < 1:
        return block
    return block[subobj[0]]


def get_array_num_items(block):
    items = block["AXIS_ITEMS"]
    if isinstance(items, int):
        return items
    if isinstance(items, Sequence):
        return reduce(mul, items)
    raise TypeError("can't interpret this item number specification")


def get_block(data: PDRLike, name: str) -> MultiDict:
    return data.metablock_(name)


def check_file_mapping(data: PDRLike, name: str):
    return data.file_mapping[name]


def get_target(data: PDRLike, name: str):
    target = data.metaget_(name)
    if isinstance(target, Mapping) or target is None:
        target = data.metaget_(pointerize(name))
    return target


def data_start_byte(identifiers: dict, block: Mapping, target, filename) -> int:
    """
    Determine the first byte of the data in a file from its pointer.
    """
    if "RECORD_BYTES" in block.keys():
        record_bytes = block["RECORD_BYTES"]
    else:
        record_bytes = identifiers["RECORD_BYTES"]
    start_byte = None
    if isinstance(target, (list, tuple)):
        target = target[-1]
    if isinstance(target, int):
        if record_bytes not in [None, ""]:
            start_byte = record_bytes * max(target - 1, 0)
        else:
            rows = identifiers["ROWS"]
            row_bytes = identifiers["ROW_BYTES"]
            return _count_from_bottom_of_file(filename, rows, row_bytes)
    elif isinstance(target, dict):
        start_byte = quantity_start_byte(target, record_bytes)
    elif isinstance(target, str):
        start_byte = 0
    if start_byte is not None:
        return start_byte
    raise ValueError(f"Unknown data pointer format: {target}")


def table_position(identifiers: dict, block, target, name, start_byte):
    try:
        if 'RECORDS' in block.keys():
            n_records = block['RECORDS']
        elif 'ROWS' in block.keys():
            n_records = block['ROWS']
        else:
            n_records = None
    except AttributeError:
        n_records = None
    length = None
    if (as_rows := _check_delimiter_stream(identifiers, name, target)) is True:
        if isinstance(target[1], dict):
            start = target[1]['value'] - 1
        else:
            try:
                start = target[1] - 1
            except TypeError:  # string types cannot have integers subtracted
                # (string implies there is one object)
                start = 0
        if n_records is not None:
            length = n_records
    else:
        start = start_byte
        try:
            if "BYTES" in block.keys():
                length = block["BYTES"]
            elif n_records is not None:
                if "RECORD_BYTES" in block.keys():
                    record_length = block['RECORD_BYTES']
                elif "ROW_BYTES" in block.keys():
                    record_length = block['ROW_BYTES']
                    record_length += block.get("ROW_SUFFIX_BYTES", 0)
                elif identifiers["RECORD_BYTES"] is not None:
                    record_length = identifiers["RECORD_BYTES"]
                else:
                    record_length = None
                if record_length is not None:
                    length = record_length * n_records
        except AttributeError:
            length = None
    table_props = {'start': start, 'length': length, 'as_rows': as_rows}
    return table_props


# TODO: How to add error handling inside of softquery for specific functions?
# def get_table_structure(name: str, debug: bool, return_default):
#     try:
#         fmtdef_dt = specialize(parse_table_structure, check_special_structure)
#     except KeyError as ex:
#         warnings.warn(f"Unable to find or parse {name}")
#         return catch_return_default(debug, return_default, ex)
#     return fmtdef_dt


def get_return_default(data: PDRLike, name: str):
    return data.metaget_(name)


def check_debug(data: PDRLike):
    return data.debug


def parse_table_structure(name, block, filename, data, identifiers):
    """
    Read a table's format specification and generate a DataFrame
    and -- if it's binary -- a numpy dtype object. These are later passed
    to np.fromfile or one of several ASCII table readers.
    """
    fmtdef = read_table_structure(block, name, filename, data, identifiers)
    if (
        fmtdef["DATA_TYPE"].str.contains("ASCII").any()
        or looks_like_ascii(block, name)
    ):
        # don't try to load it as a binary file
        return fmtdef, None
    if fmtdef is None:
        return fmtdef, np.dtype([])
    for end in ('_PREFIX', '_SUFFIX', ''):
        length = block.get(f'ROW{end}_BYTES')
        if length is not None:
            fmtdef[f'ROW{end}_BYTES'] = length
    return insert_sample_types_into_df(fmtdef, identifiers)


def read_table_structure(block, name, filename, data, identifiers):
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
    if "HISTOGRAM" in name:
        fields = get_histogram_fields(block)
    else:
        fields = read_format_block(block, name, filename, data, identifiers)
    # give columns unique names so that none of our table handling explodes
    fmtdef = pd.DataFrame.from_records(fields)
    if "NAME" not in fmtdef.columns:
        fmtdef["NAME"] = name
    fmtdef = reindex_df_values(fmtdef)
    return fmtdef


def read_format_block(block, object_name, filename, data, identifiers):
    # load external structure specifications
    format_block = list(block.items())
    block_name = block.get('NAME')
    while "^STRUCTURE" in [obj[0] for obj in format_block]:
        format_block = inject_format_files(format_block, object_name, filename, data)
    fields = []
    for item_type, definition in format_block:
        if item_type in ("COLUMN", "FIELD"):
            obj = dict(definition) | {'BLOCK_NAME': block_name}
            repeat_count = definition.get("ITEMS")
            obj = bit_handling.add_bit_column_info(obj, definition, identifiers)
        elif item_type == "CONTAINER":
            obj = read_format_block(definition, object_name, filename, data, identifiers)
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


def get_histogram_fields(block):
    # This error could maybe go somewhere else, but at least we catch it early here
    if block.get("INTERCHANGE_FORMAT") == "ASCII":
        raise NotImplementedError(
            "ASCII histograms are not currently supported."
        )
    fields = []
    if (repeats := block.get("ITEMS")) is not None:
        fields = append_repeated_object(dict(block), fields, repeats)
    else:
        fields = [dict(block)]
    return fields


def inject_format_files(block, name, filename, data):
    format_filenames = {
        ix: kv[1] for ix, kv in enumerate(block) if kv[0] == "^STRUCTURE"
    }
    # make sure to insert the structure blocks in the correct order --
    # and remember that keys are not unique, so we have to use the index
    assembled_structure = []
    last_ix = 0
    for ix, format_filename in format_filenames.items():
        fmt = list(load_format_file(data, format_filename, name, filename).items())
        assembled_structure += block[last_ix:ix] + fmt
        last_ix = ix + 1
    assembled_structure += block[last_ix:]
    return assembled_structure


def load_format_file(data, format_file, name, filename):
    label_fns = data.get_absolute_paths(format_file)
    try:
        repo_paths = [
            Path(find_repository_root(Path(filename)), label_path)
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
            f"placing it in the same path as the {name} "
            f"file."
        )
        raise FileNotFoundError


def get_identifiers(data):
    return data.identifiers


DEFAULT_DATA_QUERIES = MappingProxyType(
    {
        'block': specialize(get_block, check_special_block),
        'filename': check_file_mapping,
        'target': get_target,
        'identifiers': get_identifiers,
        'start_byte': specialize(data_start_byte, check_special_offset),
    }
)