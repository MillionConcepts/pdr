"""
Functions used as part of Loader subclasses' softquery()-backed
metadata-processing workflows.
"""

from __future__ import annotations

from operator import mul
from functools import reduce
from itertools import chain, product
from numbers import Number
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any, Collection, Mapping, Optional, Sequence, TYPE_CHECKING, Union
)
import warnings

from multidict import MultiDict

from pdr.datatypes import sample_types
from pdr.formats import check_special_block, check_special_offset
from pdr.func import specialize
from pdr.loaders._helpers import (
    count_from_bottom_of_file,
    looks_like_ascii,
    quantity_start_byte,
    _check_delimiter_stream,
)
from pdr.loaders.handlers import add_bit_column_info
from pdr.parselabel.pds3 import pointerize, read_pvl
from pdr.utils import append_repeated_object, check_cases, find_repository_root

if TYPE_CHECKING:
    from pdr.loaders.astrowrap.fits import HDUList
    import numpy as np
    import pandas as pd

    from pdr.pdrtypes import (
        BandStorageType, DataIdentifiers, ImageProps, PDRLike, PhysicalTarget
    )


def generic_qube_properties(
    block: MultiDict, band_storage_type: BandStorageType
) -> ImageProps:
    """Parse metadata from an ISIS2-style QUBE definition"""
    props = {}
    use_block = block if "CORE" not in block.keys() else block["CORE"]
    props["BYTES_PER_PIXEL"] = int(use_block["CORE_ITEM_BYTES"])  # / 8)
    # TODO: this should probably have for_numpy set to True
    props["sample_type"] = sample_types(
        use_block["CORE_ITEM_TYPE"], props["BYTES_PER_PIXEL"]
    )
    props["is_vax_real"] = use_block["CORE_ITEM_TYPE"] == "VAX_REAL"
    if "AXIS_NAME" in set(block.keys()).union(use_block.keys()):
        props['axnames'] = block.get("AXIS_NAME")
        if props['axnames'] is None:
            props['axnames'] = use_block.get("AXIS_NAME")
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
    props |= extract_axplane_metadata(block, props)
    # TODO: unclear whether lower-level linefixes ever appear on qubes
    props |= extract_linefix_metadata(block, props)
    return props  # not type-complete, 'pixels' added in get_image_properties()


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
        if isinstance(itembytes, Sequence):
            if len(set(itembytes)) > 1:
                raise NotImplementedError(
                    "Variable-length axplanes are not yet supported. Please"
                    "file an issue on github with this product as an example"
                    "so we can use it to test development and provide support."
                )
            fixbytes = sum(itembytes)
        else:
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


def gt0f(seq: Collection[Number]) -> tuple[Number]:
    """greater-than-0 filter"""
    return tuple(filter(lambda x: x > 0, seq))


def check_fix_validity(props: ImageProps) -> None:
    """"Integrity checker for 'conventional' line pre/suffix definitions."""
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
    if (
        (props["linepad"] > 0)
        and props["band_storage_type"] not in (None, "LINE_INTERLEAVED")
        and props["nbands"] > 1
    ):
        raise NotImplementedError(
            "'Conventional' line pre/suffixes are not supported for non-BIL "
            "multiband images."
        )


def check_if_qube(
    name: str,
    block: MultiDict,
    band_storage_type: BandStorageType
) -> tuple[bool, Optional[dict]]:
    """
    If this is a metadata block associated with a qube-type object, parse its
    properties using the various special rules necessary to read ISIS2
    parameters.
    """
    if "QUBE" in name:  # ISIS2 QUBE format
        return True, generic_qube_properties(block, band_storage_type)
    else:
        return False, None


def get_image_properties(gen_props: ImageProps) -> ImageProps:
    """
    Second-step cleaning/formatting function for an image properties dict,
    typically derived from `generic_image_properties()`,
    `qube_image_properties()`, or a special case.
    """
    props = gen_props  # TODO: what is this variable assignment for?
    check_fix_validity(props)
    props["pixels"] = (
        (props["nrows"] + props["rowpad"])
        * (props["ncols"] + props["colpad"] + props["linepad"])
        * (props["nbands"] + props["bandpad"])
    )
    return props


def im_sample_type(base_samp_info: dict) -> str:
    """Determine appropriate numpy dtype string for an IMAGE object"""
    if base_samp_info["SAMPLE_TYPE"] != "":
        return sample_types(
            base_samp_info["SAMPLE_TYPE"],
            base_samp_info["BYTES_PER_PIXEL"],
            for_numpy=True,
        )


def base_sample_info(block: MultiDict) -> dict:
    """Determine basic sample-level type info for an image object."""
    return {
        "BYTES_PER_PIXEL": int(block.get("SAMPLE_BITS", 0) / 8),
        "SAMPLE_TYPE": block.get("SAMPLE_TYPE", ""),
    }


def generic_image_properties(block: MultiDict, sample_type: str) -> ImageProps:
    """
    Construct a dict of image properties later used in the image-loading
    workflow.
    """
    props = {
        # TODO: BYTES_PER_PIXEL check appears repeated with slight variation
        #  from base_sample_info()
        "BYTES_PER_PIXEL": int(block["SAMPLE_BITS"] / 8),
        "is_vax_real": block.get("SAMPLE_TYPE") == "VAX_REAL",
        "sample_type": sample_type,
        "nrows": block["LINES"],
        "ncols": block["LINE_SAMPLES"],
    }
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
    # noinspection PyTypeChecker
    return props  # not type-complete, 'pixels' added in get_image_properties()


def get_qube_band_storage_type(block: MultiDict) -> Optional[BandStorageType]:
    """Attempt to get band storage type from a QUBE definition."""
    return block.get("BAND_STORAGE_TYPE")


def check_array_for_subobject(block: MultiDict) -> bool:
    """
    Does an ARRAY definition contain a definition for a subobject?
    If it (illegally) contains more than one, raise a ValueError.
    """
    valid_subobjects = ["ARRAY", "BIT_ELEMENT", "COLLECTION", "ELEMENT"]
    subobj = [sub for sub in valid_subobjects if sub in block]
    if len(subobj) > 1:
        raise ValueError(
            f"ARRAY objects may only have one subobject (this has "
            f"{len(subobj)})"
        )
    if len(subobj) < 1:
        return False
    return True


# TODO: this should probably be in loaders.table
def get_array_num_items(block: MultiDict) -> int:
    """How many total array elements does an ARRAY definition imply?"""
    items = block["AXIS_ITEMS"]
    if isinstance(items, int):
        return items
    if isinstance(items, Sequence):
        return reduce(mul, items)
    raise TypeError("can't interpret this item number specification")


def get_block(data: PDRLike, name: str) -> Optional[MultiDict]:
    """query wrapper for `pdr.Data.metablock_()`"""
    return data.metablock_(name)


def get_file_mapping(
    data: PDRLike, name: str
) -> Union[str, Path, list[Union[str, Path]]]:
    """query wrapper for `pdr.Data.file_mapping.__getitem__()`"""
    return data.file_mapping[name]


def get_target(data: PDRLike, name: str) -> PhysicalTarget:
    """
    Attempt to get the 'target' of a PDS3 pointer or other physical data
    location marker for `name`. This typically becomes the `target` argument
    of `data_start_byte()` and/or `table_position()`.
    """
    target = data.metaget_(name)
    if isinstance(target, Mapping) or target is None:
        target = data.metaget_(pointerize(name))
    return target


def _agnostic_fits_index(is_header, target, hdulist):
    from pdr.loaders.handlers import hdu_byte_index

    hix = hdu_byte_index(hdulist)
    # check both byte and FITS record specification, attempting to weed out
    # the ambiguous edge case where data/header are separated by one record.
    # this will not _always_ work.
    for factor in (1, 2880):
        matches = [
            t for t in ((target - 1) * factor, target * factor)
            if t in hix.keys()
            and (hix[t]['part'] == 'header') == is_header
        ]
        if len(matches) == 0:
            continue
        # TODO: we could do more complicated things, but for now, just always
        #  assume that if there are two matches, it's 1-indexed.
        return matches[0]
    raise ValueError("Specified target does not match an HDU.")


def get_fits_start_byte(
    name: str, target: Union[str, list, tuple, dict], fn: str, hdulist: HDUList
):
    # TODO, maybe: this feels a bit redundant with data_start_byte(), but the
    #  logic _is_ legitimately different.
    if isinstance(target, str):
        if target.lower() == Path(fn).name.lower():
            target = 0
        else:
            # this should never happen!
            raise ValueError("This appears to point to the wrong file.")
    elif isinstance(target, (list, tuple)):
        target = target[1]
    if isinstance(target, dict):
        if target['units'] == 'BYTES':
            target = target['value']
        else:
            target = target['value'] * 2880
    return _agnostic_fits_index('HEADER' in name, target, hdulist)


def get_hdulist(fn):
    from astropy.io import fits

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", module="astropy.io.fits.card")
        return fits.open(fn)


def data_start_byte(
    identifiers: DataIdentifiers, block: Mapping, target, fn
) -> int:
    """
    Determine the first byte of the data in a file from its pointer.
    """
    if (block is not None) and ("RECORD_BYTES" in block.keys()):
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
            start_byte = max(0, count_from_bottom_of_file(fn, rows, row_bytes))
    elif isinstance(target, dict):
        start_byte = quantity_start_byte(target, record_bytes)
    elif isinstance(target, str):
        start_byte = 0
    if start_byte is not None:
        if start_byte < 0:
            raise ValueError(f"BUG: start_byte={start_byte} < 0")
        return start_byte
    raise ValueError(f"Unknown data pointer format: {target}")


def _extract_table_records(block):
    """
    Attempt to get the number of 'records', which can mean either row count
    or records defined by byte length in a way that does not necessarily
    correspond to number of rows, from a TABLE/SPREADSHEET definition.
    """
    if "RECORDS" in block.keys():
        return block["RECORDS"]
    elif "ROWS" in block.keys():
        return block["ROWS"]
    return None


def _table_row_position(
    n_records, target: PhysicalTarget
) -> tuple[Optional[int], int]:
    """
    Get physical start row and number of rows for a delimited ASCII table with
    no explicitly-defined row byte length.

    A return value of None for `length` implies that the table occupies the
    entirety of the file including and after `start`.
    """
    if isinstance(target[1], dict):
        # noinspection PyTypeChecker
        start = target[1]["value"] - 1
    else:
        try:
            start = target[1] - 1
        except TypeError:
            # You cannot subtract an integer from a string. If target[1] is a
            # string, it implies that the PhysicalTarget is also a string,
            # meaning that it specifies only a filename, which implies that the
            # table starts at the beginning of the file.
            start = 0
    return n_records, start


def _table_length(block, identifiers, n_records):
    """"""
    length = None
    try:
        if "BYTES" in block.keys():
            length = block["BYTES"]
        elif n_records is not None:
            if "RECORD_BYTES" in block.keys():
                record_length = block["RECORD_BYTES"]
            elif "ROW_BYTES" in block.keys():
                record_length = block["ROW_BYTES"]
                record_length += block.get("ROW_SUFFIX_BYTES", 0)
            elif identifiers["RECORD_BYTES"] is not None:
                # TODO, probably, and applicable many more places than here:
                #  ideally we don't use identifiers for anything but special
                #  case checks.
                record_length = identifiers["RECORD_BYTES"]
            else:
                record_length = None
            if record_length is not None:
                length = record_length * n_records
    except AttributeError:
        pass
    return length


def table_position(
    identifiers: DataIdentifiers,
    block: MultiDict,
    target: PhysicalTarget,
    name: str,
    start_byte: int
) -> dict[str, Union[bool, int, None]]:
    """
    Determine the starting position of a TABLE/SPREADSHEET object from its
    definition and other previously-determined information.

    In the returned `dict`, if as_rows is True, the table is a delimiter-
    separated ASCII table with no explicitly-defined row length, and both
    "start" and "length" should be interpreted as rows; otherwise, both "start"
    and "length" should be interpreted as bytes. If length is None, the table
    occupies the entirety of the file including and after "start".
    """
    if start_byte < 0:
        raise ValueError(f"bad start byte {start_byte}")
    try:
        n_records = _extract_table_records(block)
    except AttributeError:
        n_records = None
    if (as_rows := _check_delimiter_stream(identifiers, name, target, block)):
        length, start = _table_row_position(n_records, target)
    else:
        start = start_byte
        length = _table_length(block, identifiers, n_records)
    if length in (None, "UNK") and "HEADER" in name:
        raise NotImplementedError("header with unknown length")
    return {"start": start, "length": length, "as_rows": as_rows}


def get_return_default(data: PDRLike, name: str) -> MultiDict:
    """
    Wrapper for `data.metaget_` used to return default values for failed loads
    in non-debug mode.
    """
    return data.metaget_(name)


def get_debug(data: PDRLike) -> bool:
    """Are we in debug mode?"""
    return data.debug


def _fill_empty_byte_rows(fmtdef: pd.DataFrame) -> pd.DataFrame:
    """
    Fill any missing byte rows in a format definition. This is typically
    used to fill
    """
    nobytes = fmtdef["BYTES"].isna()
    with warnings.catch_warnings():
        # TODO: although we do not care that .loc will set items inplace later, 
        #  at all, this will hard-fail in pandas 3.x and needs to be changed.
        warnings.simplefilter("ignore", category=FutureWarning)
        fmtdef.loc[nobytes, "BYTES"] = (
            # TODO: I think the subsequent TODO is out of date?
            # TODO, maybe: update with ITEM_OFFSET should we implement that
            fmtdef.loc[nobytes, "ITEMS"]
            * fmtdef.loc[nobytes, "ITEM_BYTES"]
        )
    fmtdef["BYTES"] = fmtdef["BYTES"].astype(int)
    return fmtdef


def _probably_ascii(block: MultiDict, fmtdef: pd.DataFrame, name: str) -> bool:
    """
    Attempt to determine whether a TABLE is ASCII from its label block and
    format definition.
    """
    return (
        fmtdef["DATA_TYPE"].str.contains("ASCII").any()
        or looks_like_ascii(block, name)
    )


def parse_table_structure(
    name: str,
    block: MultiDict,
    fn: str,
    data: PDRLike,
    identifiers: DataIdentifiers
) -> tuple[pd.DataFrame, Optional[np.dtype]]:
    """
    Parse a TABLE or SPREADSHEET's format specification as a pd.DataFrame
    (see `read_table_structure()`. If that specification contains byte-position
    information for columns, further parse them into explicit offsets. If the
    table is binary, also create a numpy dtype object (usually a compound
    dtype). These typically become inputs for np.fromfile (for binary tables)
    or for one of several ASCII parsers.
    """
    fmtdef = read_table_structure(block, name, fn, data, identifiers)
    if "BYTES" not in fmtdef.columns:
        if _probably_ascii(block, fmtdef, name):
            # this is either a nonstandard fixed-width table or a DSV table.
            # don't bother trying to calculate explicit byte offsets.
            return fmtdef, None
        fmtdef["BYTES"] = float('nan')
    if fmtdef['BYTES'].isna().any():
        try:
            fmtdef = _fill_empty_byte_rows(fmtdef)
        except (KeyError, TypeError, IndexError):
            raise ValueError("This table's byte sizes are underspecified.")
    for end in ("_PREFIX", "_SUFFIX", ""):
        length = block.get(f"ROW{end}_BYTES")
        if length is not None:
            fmtdef[f"ROW{end}_BYTES"] = length
    from pdr.pd_utils import compute_offsets, insert_sample_types_into_df
    if "START_BYTE" in fmtdef.columns:
        fmtdef = compute_offsets(fmtdef)
    if _probably_ascii(block, fmtdef, name):
        # don't attempt to compute numpy dtypes for ASCII tables
        return fmtdef, None
    return insert_sample_types_into_df(fmtdef, identifiers)


def read_table_structure(
    block: MultiDict,
    name: str,
    fn: str,
    data: PDRLike,
    identifiers: DataIdentifiers
) -> pd.DataFrame:
    """
    Try to turn a TABLE/SPREADSHEET/ARRAY/HISTOGRAM definition into a
    format definition DataFrame whose rows represent the columns of the
    defined object and whose columns represent various properties of those
    columns (data type, byte offset, etc.). Due to the complexity of the PDS3
    Standards for these objects, this can include a wide variety of behaviors,
    including recursively unpacking subobjects, loading external format files,
    and adding "placeholder" entries for 'padding' (e.g. extra whitespace,
    separator characters, and row prefixes/suffixes). This is most often
    called by `parse_table_structure()` or `parse_array_structure()`, but some
    special cases use it on its own.
    """
    if "HISTOGRAM" in name:
        fields = get_histogram_fields(block)
    else:
        fields, _ = read_format_block(block, name, fn, data, identifiers)
    import pandas as pd
    from pdr.pd_utils import reindex_df_values

    fmtdef = pd.DataFrame.from_records(fields)
    if "NAME" not in fmtdef.columns:
        fmtdef["NAME"] = name
    # give columns unique names so that none of our table handling explodes
    return reindex_df_values(fmtdef)


def parse_array_structure(
    name: str,
    block: MultiDict,
    fn: str,
    data: PDRLike,
    identifiers: DataIdentifiers
) -> tuple[Optional[pd.DataFrame], Optional[Union[str, np.dtype]]]:
    """`parse_table_structure()` modified for the special needs of ARRAYs."""
    if not block.get("INTERCHANGE_FORMAT") == "BINARY":
        return None, None
    has_sub = check_array_for_subobject(block)
    if not has_sub:
        dt = sample_types(block["DATA_TYPE"], block["BYTES"], True)
        return None, dt
    fmtdef = read_table_structure(block, name, fn, data, identifiers)
    # Sometimes ARRAYS give START_BYTE at top level; sometimes only their
    # elements do. We want to defer responsibility for figuring this out to
    # compute_offsets(). This satisfies its type expectations.
    if "START_BYTE" in fmtdef.columns:
        fmtdef['START_BYTE'].fillna(1, inplace=True)

    from pdr.pd_utils import insert_sample_types_into_df
    return insert_sample_types_into_df(fmtdef, identifiers)


def create_placeholder_field(block_info, definition):
    dummy_column = {
        'NAME': f'PLACEHOLDER_{definition["NAME"]}',
        'DATA_TYPE': 'VOID',
        'START_BYTE': definition['START_BYTE'],
        'BYTES': 0,
        'BLOCK_REPETITIONS': definition.get("REPETITIONS", 1),
        'BLOCK_BYTES': definition.get("BYTES"),
        'BLOCK_NAME': f'PLACEHOLDER_{block_info["BLOCK_NAME"]}'
    }
    if definition.get("AXIS_ITEMS"):
        dummy_column = dummy_column | {'AXIS_ITEMS': definition['AXIS_ITEMS']}
    return dummy_column


PDS3_STRUCTURED_DATA_PARAMETERS = (
    "ARRAY",
    "COLLECTION",
    "COLUMN",
    'CONTAINER',
    "ELEMENT",
    "FIELD",
    "PRIMITIVE_ARRAY",
    "STRUCTURE",
)


def read_format_block(
    block: MultiDict,
    object_name: str,
    fn: str,
    data: PDRLike,
    identifiers: DataIdentifiers,
    within_container: bool = False
) -> tuple[list[dict], bool]:
    """
    Parse a TABLE, ARRAY, SPREADSHEET, CONTAINER, or COLLECTION definition,
    recursing into ARRAY, CONTAINER, or COLLECTION subcomponents of that
    definition and loading external STRUCTURE specifications as needed.

    This function's `fields` return value becomes the rows of the `fmtdef`
    object used extensively in the table/array-reading workflow.
    """
    # load external structure specifications
    format_block = list(block.items())
    # propagate top-level NAME to set offsets correctly for a variety of
    # nesting objects; propagate top-level REPETITIONS and BYTES to set byte
    # offsets correctly in repeating CONTAINERs
    block_info = {
        f"BLOCK_NAME": block.get("NAME"),
        f"BLOCK_REPETITIONS": block.get("REPETITIONS", 1),
        f"BLOCK_BYTES": block.get("BYTES")
    }
    while "^STRUCTURE" in [obj[0] for obj in format_block]:
        format_block = inject_format_files(format_block, object_name, fn, data)
    fields, needs_placeholder, add_placeholder, reps = [], False, False, None
    for item_type, definition in format_block:
        if item_type not in PDS3_STRUCTURED_DATA_PARAMETERS:
            # things formally unrelated to data structure (e.g. physical units)
            continue
        if item_type == "ARRAY":
            if not check_array_for_subobject(definition):
                item_type = "PRIMITIVE_ARRAY"
        if item_type in ("COLUMN", "FIELD", "ELEMENT", "PRIMITIVE_ARRAY"):
            # TODO: this `if "^STRUCTURE"...` block smells incredibly bad. Why
            #  is it guarded by the COLUMN/FIELD/ELEMENT/PRIMITIVE_ARRAY
            #  contitional? Why are we scrupulously calling MultiDict.add()
            #  and then immediately casting `definition` back to `dict`,
            #  discarding any duplicate keys we took such care to retain? What
            #  nightmarish class of cases does this catch?
            if "^STRUCTURE" in definition:
                definition_l = inject_format_files(
                    list(definition.items()), object_name, fn, data
                )
                definition = MultiDict()
                for key, val in definition_l:
                    definition.add(key, val)
            obj = dict(definition) | block_info
            # TODO: also smells very bad. Why is this inside a branch that
            #  matches many things that are not ARRAYS (but does not match
            #  every ARRAY)?
            if "BIT_ELEMENT" in obj.keys():
                raise NotImplementedError(
                    "BIT_ELEMENTS in ARRAYS not yet supported"
                )
            reps = definition.get("ITEMS")
            obj = add_bit_column_info(obj, definition, identifiers)
        elif item_type in ("CONTAINER", "COLLECTION", "ARRAY"):
            # This is a somewhat convoluted way to tell the caller to place a
            # PLACEHOLDER pseudo-field between a running sequence of fields
            # and the fields this function returns.
            if within_container is False or len(fields) == 0:
                needs_placeholder = True
            obj, add_placeholder = read_format_block(
                definition, object_name, fn, data, identifiers
            )
            if item_type == "ARRAY":
                add_placeholder = True
            else:
                reps = definition.get("REPETITIONS")
        else:
            # this suggests we made a typo
            raise NotImplementedError(f"No defined behavior for {item_type}.")
        # Format-level data structures like CONTAINERs should not be exposed
        # to the parser; we only care about the things they contain. However,
        # because START_BYTE is always expressed relative to the parent data
        # structure in PDS3 table format specifications, we still need to
        # account for cases in which these structures are separated from
        # preceding elements by pad bytes / whitespace. These PLACEHOLDER
        # pseudo-fields inform downstream code about spacing while also
        # signaling that bytes / characters within that interval should be
        # ignored by the parser.
        if add_placeholder is True:
            fields.append(create_placeholder_field(block_info, definition))
        # CONTAINERs can have REPETITIONS, and some so-called COLUMNS contain
        # a lot of "columns" (ITEMS) as the term is generally used. We express
        # these cases by simply repeating the definition, renaming duplicates.
        if reps is not None:
            fields = append_repeated_object(obj, fields, reps)
        elif isinstance(obj, list):
            fields.extend(obj)
        else:
            fields.append(obj)
    # semi-legal top-level containers not wrapped in other objects
    if object_name == "CONTAINER":
        if (repeat_count := block.get("REPETITIONS")) is not None:
            fields = list(chain(*[fields for _ in range(repeat_count)]))
    return fields, needs_placeholder


def get_histogram_fields(block: MultiDict) -> list[dict]:
    """
    Simplified version of `read_format_block()` for HISTOGRAM objects, whose
    format specifications are much terser than TABLE/SPREADSHEET/ARRAY.
    """
    # This error could go somewhere else, but at least we catch it early here
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


def inject_format_files(
    block: list[tuple[str, Any]],
    name: str,
    fn: str,
    data: PDRLike
) -> list[tuple[str, Any]]:
    """
    Load format files referenced by a TABLE/SPREADSHEET/CONTAINER/COLLECTION
    definition (or recursively referenced by a referenced format file), parse
    them, and insert them into the referencing definition.
    """
    format_fns = {
        ix: kv[1] for ix, kv in enumerate(block) if kv[0] == "^STRUCTURE"
    }
    # make sure to insert the structure blocks in the correct order --
    # and remember that keys are not unique, so we have to use the index
    assembled_structure = []
    last_ix = 0
    for ix, format_fn in format_fns.items():
        fmt = list(load_format_file(data, format_fn, name, fn).items())
        assembled_structure += block[last_ix:ix] + fmt
        last_ix = ix + 1
    assembled_structure += block[last_ix:]
    return assembled_structure


def load_format_file(
    data: PDRLike,
    format_file: str,
    name: str,
    fn: str
) -> MultiDict:
    """
    Attempt to find and read a PVL format file (usually referenced by
    ^STRUCTURE pointers in an object definition). Normal PVL-reading workflows
    (including just `pdr.read()`) work fine on these files, but this function
    includes additional code to attempt to _find_ the format file.
    """
    label_fns = data.get_absolute_paths(format_file)
    try:
        repo_paths = [
            Path(find_repository_root(Path(fn)), label_path)
            for label_path in ("label", "LABEL")
        ]
        label_fns += [Path(path, format_file) for path in repo_paths]
    except (ValueError, IndexError):
        pass
    try:
        return read_pvl(check_cases(label_fns))[0]
    except FileNotFoundError:
        warnings.warn(
            f"Unable to locate external table format file:\n\t {format_file}. "
            f"Try retrieving this file and placing it in the same path as the "
            f"{name} file."
        )
        raise FileNotFoundError


def get_identifiers(data) -> dict[str, Any]:
    """Query wrapper for `pdr.Data.__getattr__("identifiers")`"""
    return data.identifiers


def get_none() -> None:
    """Don't get anything"""
    return None


DEFAULT_DATA_QUERIES = MappingProxyType(
        {
            "identifiers": get_identifiers,
            "block": specialize(get_block, check_special_block),
            "fn": get_file_mapping,
            "target": get_target,
            "start_byte": specialize(data_start_byte, check_special_offset),
            "debug": get_debug,
            "return_default": get_return_default,
        }
    )
