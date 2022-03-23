from functools import partial
from operator import contains
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from pdr import formats
from pdr.datatypes import sample_types
from pdr.utils import in_both_cases


if TYPE_CHECKING:
    from pdr import Data

LABEL_EXTENSIONS = in_both_cases((".xml", ".lbl"))
IMAGE_EXTENSIONS = (".img", ".tif", ".tiff", ".rgb")
TABLE_EXTENSIONS = (".tab", ".csv")
TEXT_EXTENSIONS = (".txt", ".md")
FITS_EXTENSIONS = (".fits", ".fit")


def looks_like_this_kind_of_file(filename: str, kind_extensions) -> bool:
    is_this_kind_of_extension = partial(contains, kind_extensions)
    return any(map(is_this_kind_of_extension, Path(filename.lower()).suffixes))


def file_extension_to_loader(filename: str, data: "Data") -> Callable:
    """
    attempt to select the correct method of pdr.Data for objects only
    specified by a PDS3 FILE_NAME pointer (or by filename otherwise).
    """
    if looks_like_this_kind_of_file(filename, IMAGE_EXTENSIONS):
        return data.read_image
    if looks_like_this_kind_of_file(filename, FITS_EXTENSIONS):
        return data.handle_fits_file
    if looks_like_this_kind_of_file(filename, TEXT_EXTENSIONS):
        return data.read_text
    if looks_like_this_kind_of_file(filename, TABLE_EXTENSIONS):
        return data.read_table
    return data.tbd


def check_special_offset(pointer, data) -> tuple[bool, Optional[int]]:
    # these incorrectly specify object length rather than
    # object offset in the ^HISTOGRAM pointer target
    if data.LABEL.get("INSTRUMENT_ID") == "CHEMIN":
        return formats.msl_cmn.get_offset(data, pointer)
    return False, None


def check_special_case(pointer, data) -> tuple[bool, Optional[Callable]]:
    if (
        ("JUNO JUPITER JIRAM REDUCED" in data.LABEL.get("DATA_SET_NAME", ""))
        and (pointer == "IMAGE")
    ):
        return True, formats.juno.jiram_image_loader(data, pointer)
    if (
        data.LABEL.get("INSTITUTION_NAME") == "MALIN SPACE SCIENCE SYSTEMS"
        and data.LABEL.get("MISSION_NAME") == "MARS SCIENCE LABORATORY"
        and pointer == "IMAGE"
    ):
        return True, formats.msl_mmm.image_loader(data, pointer)
    if (
        data.LABEL.get("INSTRUMENT_ID") == "APXS"
        and "TABLE" in pointer
    ):
        # just an ambiguous name: best to specify it)
        return True, formats.msl_apxs.table_loader(data, pointer)
    if (
        data.LABEL.get("INSTRUMENT_ID") == "CHEMIN"
        and (("HEADER" in pointer) or ("SPREADSHEET" in pointer))
    ):
        # mangled object names + positions
        return True, formats.msl_cmn.table_loader(data, pointer)
    # unusual line prefixes; rasterio happily reads it, but incorrectly
    if data.LABEL.get("INSTRUMENT_ID") == "M3" and pointer == "L0_IMAGE":
        return True, formats.m3.l0_image_loader(data)
    # difficult table formats that are handled well by astropy.io.ascii
    if (
        data.LABEL.get("INSTRUMENT_NAME") == "TRIAXIAL FLUXGATE MAGNETOMETER"
        and pointer == "TABLE"
    ):
        return True, formats.galileo.galileo_table_loader(data)
    return False, None


# noinspection PyTypeChecker
def pointer_to_loader(pointer: str, data: "Data") -> Callable:
    """
    attempt to select an appropriate loading function based on a PDS3 pointer
    name. checks for special cases and then falls back to generic loading
    methods of pdr.Data.
    """
    is_special, loader = check_special_case(pointer, data)
    if is_special is True:
        return loader
    # TIFF tags / headers should always be parsed by the TIFF parser itself
    if ("TIFF" in pointer) and ("IMAGE" not in pointer):
        return data.trivial
    if "DESC" in pointer:  # probably points to a reference file
        return data.read_text
    if "LINE_PREFIX_TABLE" in pointer:
        return data.tbd
    if (
        ("TABLE" in pointer)
        or ("SPREADSHEET" in pointer)
        or ("CONTAINER" in pointer)
    ):
        return data.read_table
    if "HISTOGRAM" in pointer:
        return data.read_histogram
    if "HEADER" in pointer or "DATA_SET_MAP_PROJECTION" in pointer:
        return data.read_header
    # I have moved this below "table" due to the presence of a number of
    # binary tables named things like "Image Time Table". If there are pictures
    # of tables, we will need to do something more sophisticated.
    if ("IMAGE" in pointer) or ("QUB" in pointer):
        # TODO: sloppy pt. 1. this will be problematic for
        #  products with a 'secondary' fits file, etc.
        if looks_like_this_kind_of_file(
            data._target_path(pointer), FITS_EXTENSIONS
        ):
            return data.handle_fits_file
        return data.read_image
    # we don't present STRUCTURES separately from their tables;
    if "STRUCTURE" in pointer:
        return data.trivial
    if "FILE_NAME" in pointer:
        return file_extension_to_loader(pointer, data)
    # TODO: sloppy pt. 2
    if looks_like_this_kind_of_file(data.filename, FITS_EXTENSIONS):
        return data.handle_fits_file
    return data.tbd


def qube_image_properties(block):
    props = {}
    props["BYTES_PER_PIXEL"] = int(block["CORE_ITEM_BYTES"])  # / 8)
    props["sample_type"] = sample_types(
        block["CORE_ITEM_TYPE"], props["BYTES_PER_PIXEL"]
    )
    props["nrows"] = block["CORE_ITEMS"][2]
    props["ncols"] = block["CORE_ITEMS"][0]
    props["prefix_cols"], props["prefix_bytes"] = 0, 0
    # TODO: Handle the QUB suffix data
    props["BANDS"] = block["CORE_ITEMS"][1]
    props["band_storage_type"] = "ISIS2_QUBE"
    return props


def generic_image_properties(object_name, block, data) -> dict:
    if object_name == "QUBE":  # ISIS2 QUBE format
        props = qube_image_properties(block)
    else:
        props = {}
        props["BYTES_PER_PIXEL"] = int(block["SAMPLE_BITS"] / 8)
        # TODO: I think this should have for_numpy set
        props["sample_type"] = sample_types(
            block["SAMPLE_TYPE"], props["BYTES_PER_PIXEL"]
        )
        props["nrows"] = block["LINES"]
        props["ncols"] = block["LINE_SAMPLES"]
        if "LINE_PREFIX_BYTES" in block.keys():
            props["prefix_cols"] = int(
                block["LINE_PREFIX_BYTES"] / props["BYTES_PER_PIXEL"]
            )
            props["prefix_bytes"] = (
                props["prefix_cols"] * props["BYTES_PER_PIXEL"]
            )
        else:
            props["prefix_cols"], props["prefix_bytes"] = 0, 0
        if "BANDS" in block:
            props["BANDS"] = block["BANDS"]
            props["band_storage_type"] = block["BAND_STORAGE_TYPE"]
        else:
            props["BANDS"] = 1
            props["band_storage_type"] = None
    props["pixels"] = (
        props["nrows"]
        * (props["ncols"] + props["prefix_cols"])
        * props["BANDS"]
    )
    # TODO: handle cases where image blocks are nested inside file
    #  blocks and info such as RECORD_BYTES is found only there
    #  -- previously I did this by making pointers lists, but this may
    #  be an unwieldy solution
    props["start_byte"] = data.data_start_byte(object_name)
    return props


def check_special_fn(data, object_name) -> tuple[bool, Optional[str]]:
    """
    special-case handling for labels with nonstandard filename specifications
    """
    if (
        ("HIRISE" in data.LABEL.get("DATA_SET_ID"))
        and (object_name == "IMAGE")
        and ("-EDR-" not in data.LABEL.get("DATA_SET_ID"))
        and ("-EDR-" not in data.LABEL.get("DATA_SET_ID"))
    ):
        return True, data.LABEL['COMPRESSED_FILE']['FILE_NAME']
    return False, None


# pointers we do not automatically load even when loading greedily --
# generally these are reference files, usually throwaway ones, that are not
# archived in the same place as the data products and add little, if any,
# context to individual products
OBJECTS_IGNORED_BY_DEFAULT = (
    "DESCRIPTION", "DATA_SET_MAP_PROJECTION", "MODEL_DESC", "ERROR_MODEL_DESC"
)