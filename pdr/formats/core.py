from __future__ import annotations
import re
from typing import TYPE_CHECKING, Callable, Optional

from pdr import formats

if TYPE_CHECKING:
    from pdr.pdrtypes import PDRLike


ID_FIELDS = (
    "INSTRUMENT_ID",
    "INSTRUMENT_NAME",
    "SPACECRAFT_NAME",
    "PRODUCT_TYPE",
    "DATA_SET_NAME",
    "DATA_SET_ID",
    "STANDARD_DATA_PRODUCT_ID"
)


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
    data: PDRLike,
    base_samp_info,
) -> tuple[bool, Optional[str]]:
    if (
        data.metaget_("INSTRUMENT_ID") == "MARSIS"
        and data.metaget_("PRODUCT_TYPE") == "EDR"
    ):
        return formats.mex_marsis.get_sample_type(
           base_samp_info["SAMPLE_TYPE"], base_samp_info["BYTES_PER_PIXEL"]
        )
    if (
        data.metaget_("DATA_SET_ID") == "JNO-J-JIRAM-3-RDR-V1.0"
        and data.metaget("PRODUCT_TYPE") == "RDR"
    ):
        return True, formats.juno.jiram_rdr_sample_type()
    if (
        data.metaget_("INSTRUMENT_ID") == "LROC"
        and data.metaget_("PRODUCT_TYPE") == "EDR"
    ):
        # unsigned integers not specified as such
        return True, formats.lroc.lroc_edr_sample_type()
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


def check_special_block(name, data):
    if name == "XDR_DOCUMENT":
        return True, formats.cassini.xdr_redirect_to_image_block(data)
    return False, None


def check_special_case(pointer, data) -> tuple[bool, Optional[Callable]]:
    if pointer == 'SHADR_HEADER_TABLE':
        return True, formats.messenger.shadr_header_table_loader(data)
    ids = {field: str(data.metaget_(field, "")) for field in ID_FIELDS}
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


def check_special_qube_band_storage(data):
    if (
        data.metaget_("INSTRUMENT_HOST_NAME", "") == "CASSINI_ORBITER"
        # and object_name == "QUBE" #should be repetitive because it's only called
            # inside a QUBE reading function.
    ):
        return formats.cassini.get_special_qube_band_storage()
    return False, None
