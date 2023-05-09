from __future__ import annotations
import re
from _operator import mul
from functools import reduce
from itertools import product
from types import MappingProxyType
from typing import Sequence, Mapping, TYPE_CHECKING

from multidict import MultiDict

from pdr.datatypes import sample_types
from pdr.formats import check_special_offset, check_special_position, check_special_block
from pdr.func import specialize
from pdr.loaders._helpers import quantity_start_byte, \
    _count_from_bottom_of_file
from pdr.parselabel.pds3 import pointerize

if TYPE_CHECKING:
    from pdr.pdrtypes import PDRLike


def generic_qube_properties(block: MultiDict, band_storage_type) -> tuple:
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
    return props, use_block


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


def check_if_qube(name):
    if "QUBE" in name:  # ISIS2 QUBE format
        return True, generic_qube_properties
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
    return sample_types(
        base_samp_info["SAMPLE_TYPE"],
        base_samp_info["BYTES_PER_PIXEL"],
        for_numpy=True
    )


def base_sample_info(block):
    return {
        'BYTES_PER_PIXEL': int(block['SAMPLE_BITS'] / 8),
        'SAMPLE_TYPE': block["SAMPLE_TYPE"]
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
    if isinstance(target, Mapping):
        target = data.metaget_(pointerize(name))
    return target


def data_start_byte(data: PDRLike, block: Mapping, target, filename) -> int:
    """
    Determine the first byte of the data in a file from its pointer.
    """
    if "RECORD_BYTES" in block.keys():
        record_bytes = block["RECORD_BYTES"]
    else:
        record_bytes = data.metaget_("RECORD_BYTES")
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
        if isinstance(target, int):
            rows = data.metaget_("ROWS")
            row_bytes = data.metaget_("ROW_BYTES")
            return _count_from_bottom_of_file(filename, rows, row_bytes)
    raise ValueError(f"Unknown data pointer format: {target}")


def table_position(data, block, target, name, filename):
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
    if (as_rows := self._check_delimiter_stream(name)) is True:
        if isinstance(target[1], dict):
            start = target[1]['value'] - 1
        else:
            try:
                start = target[1] - 1
            except TypeError:  # string types cannot have integers subtracted (string implies there is one object)
                start = 0
        if n_records is not None:
            length = n_records
    else:
        start = data_start_byte(data, block, target, filename)
        try:
            if "BYTES" in block.keys():
                length = block["BYTES"]
            elif n_records is not None:
                if "RECORD_BYTES" in block.keys():
                    record_length = block['RECORD_BYTES']
                elif "ROW_BYTES" in block.keys():
                    record_length = block['ROW_BYTES']
                    record_length += block.get("ROW_SUFFIX_BYTES", 0)
                elif data.metaget_("RECORD_BYTES") is not None:
                    record_length = data.metaget_("RECORD_BYTES")
                else:
                    record_length = None
                if record_length is not None:
                    length = record_length * n_records
        except AttributeError:
            length = None
    is_special, spec_start, spec_length, spec_as_rows = check_special_position(
        start, length, as_rows, data, name)
    if is_special:
        return spec_start, spec_length, spec_as_rows
    return start, length, as_rows


DEFAULT_DATA_QUERIES = MappingProxyType(
    {
        'block': specialize(get_block, check_special_block),
        'filename': check_file_mapping,
        'target': get_target,
        'start_byte': specialize(data_start_byte, check_special_offset)
    }
)







