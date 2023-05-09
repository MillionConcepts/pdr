from __future__ import annotations
import re
import warnings
from functools import partial
from operator import contains
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional

from pdr import formats
from pdr.parselabel.pds3 import pointerize
from pdr.utils import check_cases

if TYPE_CHECKING:
    from pdr.pdrtypes import PDRLike

LABEL_EXTENSIONS = (".xml", ".lbl")
IMAGE_EXTENSIONS = (".img", ".rgb")
TABLE_EXTENSIONS = (".tab", ".csv")
TEXT_EXTENSIONS = (".txt", ".md")
FITS_EXTENSIONS = (".fits", ".fit")
TIFF_EXTENSIONS = (".tif", ".tiff")
JP2_EXTENSIONS = (".jp2", ".jpf", ".jpc", ".jpx")

ID_FIELDS = (
    "INSTRUMENT_ID",
    "INSTRUMENT_NAME",
    "SPACECRAFT_NAME",
    "PRODUCT_TYPE",
    "DATA_SET_NAME",
    "DATA_SET_ID",
    "STANDARD_DATA_PRODUCT_ID"
)


def looks_like_this_kind_of_file(filename: str, kind_extensions) -> bool:
    is_this_kind_of_extension = partial(contains, kind_extensions)
    return any(
        map(is_this_kind_of_extension, Path(filename.lower()).suffixes)
    )


def file_extension_to_loader(filename: str, data: "Data") -> Callable:
    """
    attempt to select the correct method of pdr.Data for objects only
    specified by a PDS3 FILE_NAME pointer (or by filename otherwise).
    """
    if looks_like_this_kind_of_file(filename, FITS_EXTENSIONS):
        return data.handle_fits_file
    if looks_like_this_kind_of_file(filename, TIFF_EXTENSIONS):
        return data.handle_compressed_image
    if looks_like_this_kind_of_file(filename, IMAGE_EXTENSIONS):
        return data.read_image
    if looks_like_this_kind_of_file(filename, TEXT_EXTENSIONS):
        return data.read_text
    if looks_like_this_kind_of_file(filename, TABLE_EXTENSIONS):
        return data.read_table
    if looks_like_this_kind_of_file(filename, JP2_EXTENSIONS):
        return data.handle_compressed_image
    return data.tbd


def check_special_offset(
    name: str, data: PDRLike
) -> tuple[bool, Optional[int]]:
    # these incorrectly specify object length rather than
    # object offset in the ^HISTOGRAM pointer target
    if data.metaget_("INSTRUMENT_ID", "") == "CHEMIN":
        return formats.msl_cmn.get_offset(data, name)
    if (
        data.metaget_("DATA_SET_ID", "") == "CLEM1-L-RSS-5-BSR-V1.0"
        and name in ("HEADER_TABLE", "DATA_TABLE")
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_offset(data, name)
    if data.metaget_("INSTRUMENT_ID") == "THEMIS" and name == "QUBE":
        return formats.themis.get_qube_offset(data)
    if (
        data.metaget_("INSTRUMENT_NAME", "") == "DESCENT IMAGER SPECTRAL RADIOMETER"
        and (data.metaget_("PRODUCT_TYPE", "") == "RDR")
        or any(
            sub in data.metaget_("FILE_NAME", "") for sub in
            ["STRIP", "VISIBL", "IMAGE", "IR_", "TIME", "SUN", "SOLAR"]
        )
    ):
        return formats.cassini.get_offset(data, name)
    return False, None


def check_special_structure(pointer, data):
    if (data.metaget_("DATA_SET_ID", "") == "CLEM1-L-RSS-5-BSR-V1.0"
            and pointer == "DATA_TABLE"):
        # sequence wrapped as string for object names
        return formats.clementine.get_structure(pointer, data)
    if (data.metaget_("INSTRUMENT_HOST_NAME", "") == "MARS GLOBAL SURVEYOR"
            and data.metaget_("INSTRUMENT_ID", "") == "RSS"
            and data.metaget_("PRODUCT_TYPE", "") == "ODF" and pointer == "ODF3B_TABLE"):
        return formats.mgs.get_structure(pointer, data)
    if (data.metaget_("INSTRUMENT_HOST_NAME", "") == "CASSINI ORBITER"
            and data.metaget_("INSTRUMENT_ID", "") == "RPWS"
            and pointer == "TIME_SERIES"):
        return formats.cassini.get_structure(pointer, data)
    if (data.metaget_("INSTRUMENT_HOST_NAME", "") == "HUYGENS PROBE"
            and "HUY_DTWG_ENTRY_AERO" in data.filename):
        return formats.cassini.get_structure(pointer, data)
    return False, None, None


def check_special_position(start, length, as_rows, data, object_name):
    if (data.metaget_("INSTRUMENT_ID", "") == "MARSIS" and
            " TEC " in data.metaget_("DATA_SET_NAME", "")):
        return formats.mex_marsis.get_position(start, length, as_rows, data)
    if (
            data.metaget_("INSTRUMENT_HOST_NAME", "") == "HUYGENS PROBE"
            and any(
                sub in data.metaget_("FILE_NAME", "")
                for sub in ["DARK", "STRIP", "VIS_EX", "SUN", "VISIBL", "TIME", "SOLAR", "IMAGE"]
            )
            or (
                data.metaget_("INSTRUMENT_NAME", "") == "DESCENT IMAGER SPECTRAL RADIOMETER"
                and data.metaget_("PRODUCT_TYPE", "") == "RDR")
            ):
        return formats.cassini.get_position(start, length, as_rows, data, object_name)
    return False, None, None, None


def check_special_sample_type(
    data: "Data",
    sample_type: str,
    sample_bytes: int,
    for_numpy: bool
) -> tuple[bool, Optional[str]]:
    if (
        data.metaget_("INSTRUMENT_ID") == "MARSIS"
        and data.metaget_("PRODUCT_TYPE") == "EDR"
    ):
        return formats.mex_marsis.get_sample_type(
            sample_type, sample_bytes, for_numpy
        )
    if (
        data.metaget_("DATA_SET_ID") == "JNO-J-JIRAM-3-RDR-V1.0"
        and data.metaget("PRODUCT_TYPE") == "RDR"
    ):
        return formats.juno.jiram_rdr_sample_type()
    return False, None


def check_special_bit_column_case(data):
    instrument = data.metaget_("INSTRUMENT_NAME")
    if instrument in (
        "ALPHA PARTICLE X-RAYSPECTROMETER",
        "JOVIAN AURORAL PLASMA DISTRIBUTIONS EXPERIMENT",
        "CHEMISTRY AND MINERALOGY INSTRUMENT",
        "MARS ADVANCED RADAR FOR SUBSURFACE ANDIONOSPHERE SOUNDING"
    ):
        return True, "MSB_BIT_STRING"
    return False, None


def check_special_bit_start_case(
    data, list_of_pvl_objects_for_bit_columns, start_bit_list
):
    if data.metaget_("INSTRUMENT_NAME", "") in "JOVIAN INFRARED AURORAL MAPPER":
        return formats.juno.bit_start_find_and_fix(
            list_of_pvl_objects_for_bit_columns, start_bit_list
        )
    return False, None


def check_special_case(pointer, data) -> tuple[bool, Optional[Callable]]:
    if pointer == 'SHADR_HEADER_TABLE':
        return True, formats.messenger.shadr_header_table_loader(data)
    ids = {field: str(data.metaget_(field, "")) for field in ID_FIELDS}
    if (
        ids["INSTRUMENT_ID"] == "LROC"
        and ids["PRODUCT_TYPE"] == "EDR"
        and pointer == "IMAGE"
    ):
        # unsigned integers not specified as such
        return True, formats.lroc.lroc_edr_image_loader(data, pointer)
    if (
        ids["SPACECRAFT_NAME"] == "MAGELLAN" 
        and pointer == "TABLE"
        and data.metaget_("NOTE", "").startswith("Geometry")
    ):
        return True, formats.mgn.geom_table_loader(data, pointer)
    if (
        ids["INSTRUMENT_NAME"] == "ROSETTA PLASMA CONSORTIUM - MUTUAL IMPEDANCE PROBE"
        and "SPECTRUM_TABLE" in pointer
    ):
        return True, formats.rosetta.rosetta_table_loader(data, pointer)
    if ids["INSTRUMENT_ID"] == "APXS" and "TABLE" in pointer:
        # just an ambiguous name: best to specify it)
        return True, formats.msl_apxs.table_loader(data, pointer)
    if (
        ids["INSTRUMENT_ID"] == "CHEMIN"
        and (("HEADER" in pointer) or ("SPREADSHEET" in pointer))
    ):
        # mangled object names + positions
        return True, formats.msl_cmn.table_loader(data, pointer)
    # difficult table formats that are handled well by astropy.io.ascii
    if (
        ids["INSTRUMENT_NAME"] == "TRIAXIAL FLUXGATE MAGNETOMETER"
        and pointer == "TABLE"
    ):
        return True, formats.galileo.galileo_table_loader(data)
    if (
        ids["INSTRUMENT_NAME"] == "CHEMISTRY CAMERA REMOTE MICRO-IMAGER"
        and pointer == "IMAGE_REPLY_TABLE"
    ):
        return True, formats.msl_ccam.image_reply_table_loader(data)
    if (
        ids["DATA_SET_ID"].startswith("JNO-E/J/SS")
        and "BSTFULL" in ids["DATA_SET_ID"]
        and "FREQ_OFFSET_TABLE" in data.keys()
        and pointer in ("FREQ_OFFSET_TABLE", "DATA_TABLE")
    ):
        return True, formats.juno.waves_burst_with_offset_loader(data)
    if (
        ids["DATA_SET_ID"] in (
            "CO-S-MIMI-4-CHEMS-CALIB-V1.0",
            "CO-S-MIMI-4-LEMMS-CALIB-V1.0",
            "CO-S-MIMI-4-INCA-CALIB-V1.0",
            "CO-E/J/S/SW-MIMI-2-LEMMS-UNCALIB-V1.0"
        )
        and pointer == "SPREADSHEET"
    ):
        return True, formats.cassini.ppi_table_loader(
            data, pointer, ids["DATA_SET_ID"]
        )
    if (
        ids["INSTRUMENT_ID"] == "DLRE"
        and ids["PRODUCT_TYPE"] in ("GCP", "PCP", "PRP")
        and pointer == "TABLE"
    ):
        return True, formats.diviner.diviner_l4_table_loader(data, pointer)
    if (
        ids["DATA_SET_ID"].startswith("ODY-M-THM-5")
        and (pointer in ("HEADER", "HISTORY"))
    ):
        return True, formats.themis.trivial_themis_geo_loader(data, pointer)
    if re.match(r"CO-(CAL-ISS|[S/EVJ-]+ISSNA/ISSWA-2)", ids["DATA_SET_ID"]):
        if pointer in ("TELEMETRY_TABLE", "LINE_PREFIX_TABLE"):
            return True, formats.cassini.trivial_loader(pointer, data)
    if pointer == "XDR_DOCUMENT":
        return True, formats.cassini.xdr_loader(pointer, data)
    if (data.metaget_("INSTRUMENT_HOST_NAME", "") == "HUYGENS PROBE"
            and "HASI" in data.metaget_("FILE_NAME", "") and "PWA" not in
            data.metaget_("FILE_NAME", "") and pointer == "TABLE"):
        return True, formats.cassini.hasi_loader(pointer, data)
    if (data.metaget_("SPACECRAFT_NAME", "") == "MAGELLAN" and (data.filename.endswith(
            '.img') or data.filename.endswith('.ibg')) and pointer == "TABLE"):
        return True, formats.mgn.orbit_table_in_img_loader(data, pointer)
    if ids["DATA_SET_ID"].startswith("MGN-V-RSS-5-OCC-PROF") and pointer == "TABLE":
        return True, formats.mgn.occultation_loader(data, pointer)
    return False, None


def is_trivial(pointer) -> bool:
    # TIFF tags / headers should always be parsed by the TIFF parser itself
    if (
        ("TIFF" in pointer)
        and ("IMAGE" not in pointer)
        and ("DOCUMENT" not in pointer)
    ):
        return True
    # we don't present STRUCTURES separately from their tables
    if "STRUCTURE" in pointer:
        return True
    return False


# noinspection PyTypeChecker
def pointer_to_loader(pointer: str, data: "Data") -> Callable:
    """
    attempt to select an appropriate loading function based on a PDS3 pointer
    name. checks for special cases and then falls back to generic loading
    methods of pdr.Data.
    """
    if is_trivial(pointer) is True:
        return data.trivial
    is_special, loader = check_special_case(pointer, data)
    if is_special is True:
        return loader
    if pointer == "LABEL":
        return data.read_label
    if "TEXT" in pointer or "PDF" in pointer or "MAP_PROJECTION_CATALOG" in pointer:
        return data.read_text
    if "DESC" in pointer:  # probably points to a reference file
        return data.read_text
    if "ARRAY" in pointer:
        return data.read_array
    if "LINE_PREFIX_TABLE" in pointer:
        return data.tbd
    if (
        ("TABLE" in pointer)
        or ("SPREADSHEET" in pointer)
        or ("CONTAINER" in pointer)
        or ("TIME_SERIES" in pointer)
        or ("SERIES" in pointer)
        or ("SPECTRUM" in pointer)
    ):
        return data.read_table
    if "HISTOGRAM" in pointer:
        return data.read_histogram
    if "HEADER" in pointer:
        return data.read_header
    # I have moved this below "table" due to the presence of a number of
    # binary tables named things like "Image Time Table". If there are pictures
    # of tables, we will need to do something more sophisticated.
    if ("IMAGE" in pointer) or ("QUB" in pointer):
        # TODO: sloppy pt. 1. this may be problematic for
        #  products with a 'secondary' fits file, etc.
        if image_lib_dispatch(pointer, data) is not None:
            return image_lib_dispatch(pointer, data)
        return data.read_image
    if "FILE_NAME" in pointer:
        return file_extension_to_loader(pointer, data)
    # TODO: sloppy pt. 2
    if image_lib_dispatch(pointer, data) is not None:
        return image_lib_dispatch(pointer, data)
    return data.tbd


def image_lib_dispatch(pointer: str, data: "Data") -> Optional[Callable]:
    """
    check file extensions to see if we want to toss a file to an external
    library rather than using our internal raster handling. current cases are:
    pillow for tiff, astropy for fits
    """
    object_filename = data._target_path(pointer)
    if looks_like_this_kind_of_file(object_filename, FITS_EXTENSIONS):
        return data.handle_fits_file
    if looks_like_this_kind_of_file(object_filename, TIFF_EXTENSIONS):
        return data.handle_compressed_image
    if looks_like_this_kind_of_file(object_filename, JP2_EXTENSIONS):
        return data.handle_compressed_image
    return None


def special_image_constants(data):
    consts = {}
    if data.metaget_("INSTRUMENT_ID") == "CRISM":
        consts["NULL"] = 65535
    return consts


def check_special_fn(data, object_name) -> tuple[bool, Optional[str]]:
    """
    special-case handling for labels with nonstandard filename specifications
    """
    dsi = data.metaget_("DATA_SET_ID", "")
    if (
        (dsi == "CLEM1-L-RSS-5-BSR-V1.0")
        and (object_name in ("HEADER_TABLE", "DATA_TABLE"))
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_fn(data, object_name)
    if (
        data.metaget_("SPACECRAFT_NAME", "") == "MAGELLAN"
        and (data.filename.endswith('.img') or data.filename.endswith('ibg'))
        and object_name == "TABLE"
    ):
        return formats.mgn.get_fn(data)
    # filenames are frequently misspecified
    if str(dsi).startswith("CO-D-CDA") and (object_name == "TABLE"):
        return formats.cassini.cda_table_filename(data)
    # THEMIS labels don't always mention when a file is stored gzipped
    if data.metaget("INSTRUMENT_ID") == "THEMIS":
        return formats.themis.check_gzip_fn(data, object_name)
    return False, None


# pointers we do not automatically load even when loading greedily --
# generally these are reference files, usually throwaway ones, that are not
# archived in the same place as the data products and add little, if any,
# context to individual products
objects_to_ignore = [
    "DESCRIPTION", "DATA_SET_MAP_PROJECT.*", ".*_DESC"
]
OBJECTS_IGNORED_BY_DEFAULT = re.compile('|'.join(objects_to_ignore))


def ignore_if_pdf(data, object_name, path):
    if looks_like_this_kind_of_file(path, [".pdf"]):
        warnings.warn(
            f"Cannot open {path}; PDF files are not supported."
        )
        block = data.metaget_(object_name)
        if block is None:
            return data.metaget_(pointerize(object_name))
        return block
    return open(check_cases(path)).read()


def check_special_qube_band_storage(props, data):
    if (
        data.metaget_("INSTRUMENT_HOST_NAME", "") == "CASSINI_ORBITER"
        # and object_name == "QUBE" #should be repetitive because it's only called
            # inside a QUBE reading function.
    ):
        return formats.cassini.get_special_qube_band_storage(props)
    return False, None
