from __future__ import annotations
import re
from typing import TYPE_CHECKING, Callable, Optional

from pdr import formats
from pdr.loaders.utility import trivial, is_trivial

if TYPE_CHECKING:
    from pdr.pdrtypes import PDRLike


def check_special_offset(
    name: str, data: PDRLike, identifiers: dict, filename
) -> tuple[bool, Optional[int]]:
    # these incorrectly specify object length rather than
    # object offset in the ^HISTOGRAM pointer target
    if identifiers["INSTRUMENT_ID"] == "CHEMIN":
        return formats.msl_cmn.get_offset(name)
    if (
        identifiers["DATA_SET_ID"] == "CLEM1-L-RSS-5-BSR-V1.0"
        and name in ("HEADER_TABLE", "DATA_TABLE")
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_offset(data, name)
    if identifiers["INSTRUMENT_ID"] == "THEMIS" and name == "QUBE":
        return formats.themis.get_qube_offset(data)
    if (
        identifiers["INSTRUMENT_NAME"] == "DESCENT IMAGER SPECTRAL RADIOMETER"
        and (identifiers["PRODUCT_TYPE"] == "RDR")
        or any(
            sub in identifiers["FILE_NAME"] for sub in
            ["STRIP", "VISIBL", "IMAGE", "IR_", "TIME", "SUN", "SOLAR"]
        )
    ):
        return formats.cassini.get_offset(filename, identifiers)
    return False, None


def check_special_table_reader(identifiers, data, name, filename, fmtdef_dt, block):
    if (
        identifiers["DATA_SET_ID"] in (
            "CO-S-MIMI-4-CHEMS-CALIB-V1.0",
            "CO-S-MIMI-4-LEMMS-CALIB-V1.0",
            "CO-S-MIMI-4-INCA-CALIB-V1.0",
            "CO-E/J/S/SW-MIMI-2-LEMMS-UNCALIB-V1.0"
        )
        and name == "SPREADSHEET"
    ):
        return True, formats.cassini.ppi_table_loader(filename, fmtdef_dt,
                                                      identifiers["DATA_SET_ID"])
    if (
        identifiers["INSTRUMENT_ID"] == "CHEMIN"
        and ((name == "HEADER") or ("SPREADSHEET" in name))
    ):
        # mangled object names + positions
        return formats.msl_cmn.table_loader(data, name)  # TODO: try and refactor out data
    if (
        identifiers["INSTRUMENT_NAME"] == "ROSETTA PLASMA CONSORTIUM - MUTUAL IMPEDANCE "
                                          "PROBE"
        and "SPECTRUM_TABLE" in name
    ):
        return True, formats.rosetta.rosetta_table_loader(filename, fmtdef_dt)
    if (
        identifiers["SPACECRAFT_NAME"] == "MAGELLAN"
        and name == "TABLE"
        and identifiers["NOTE"].startswith("Geometry")
    ):
        return True, formats.mgn.geom_table_loader(filename, fmtdef_dt)
    if identifiers["DATA_SET_ID"].startswith("MGN-V-RSS-5-OCC-PROF") and name == \
            "TABLE":
        return True, formats.mgn.occultation_loader(identifiers, fmtdef_dt, block,
                                                    filename)
    if (
        identifiers["INSTRUMENT_ID"] == "DLRE"
        and identifiers["PRODUCT_TYPE"] in ("GCP", "PCP", "PRP")
        and name == "TABLE"
    ):
        return True, formats.diviner.diviner_l4_table_loader(fmtdef_dt, filename)
    return False, None


def check_special_structure(block, name, filename, identifiers, data):
    if (identifiers["DATA_SET_ID"] == "CLEM1-L-RSS-5-BSR-V1.0"
            and name == "DATA_TABLE"):
        # sequence wrapped as string for object names
        return True, formats.clementine.get_structure(block, name, filename, data,
                                                      identifiers)
    if (identifiers["INSTRUMENT_HOST_NAME"] == "MARS GLOBAL SURVEYOR"
            and identifiers["INSTRUMENT_ID"] == "RSS"
            and identifiers["PRODUCT_TYPE"] == "ODF" and name == "ODF3B_TABLE"):
        return True, formats.mgs.get_structure(block, name, filename, data, identifiers)
    if (identifiers["INSTRUMENT_HOST_NAME"] == "CASSINI ORBITER"
            and identifiers["INSTRUMENT_ID"] == "RPWS"
            and name == "TIME_SERIES") \
            or (identifiers["INSTRUMENT_HOST_NAME"] == "HUYGENS PROBE"
                and ("HUY_DTWG_ENTRY_AERO" in filename or
                     ("HASI" in data.metaget_("FILE_NAME", "") and "PWA" not in
                      identifiers["FILE_NAME"]))):
        return True, formats.cassini.get_structure(block, name, filename, data,
                                                   identifiers)
    return False, None


def check_special_position(identifiers, block, target, name, filename, start_byte):
    if (identifiers["INSTRUMENT_ID"] == "MARSIS" and
            " TEC " in identifiers["DATA_SET_NAME"]):
        return True, formats.mex_marsis.get_position(identifiers, block, target, name,
                                                     start_byte)
    if (
            identifiers["INSTRUMENT_HOST_NAME"] == "HUYGENS PROBE"
            and any(
                sub in identifiers["FILE_NAME"]
                for sub in ["DARK", "STRIP", "VIS_EX", "SUN",
                            "VISIBL", "TIME", "SOLAR", "IMAGE"]
            )
            or (
                identifiers["INSTRUMENT_NAME"] == "DESCENT IMAGER SPECTRAL RADIOMETER"
                and identifiers["PRODUCT_TYPE"] == "RDR")
            and (name in ("TABLE", "HEADER"))
    ):
        return True, formats.cassini.get_position(identifiers, block, target, name,
                                                  filename, start_byte)
    return False, None


def check_special_sample_type(
    base_samp_info,
    identifiers: dict,
) -> tuple[bool, Optional[str]]:
    if (
        identifiers["INSTRUMENT_ID"] == "MARSIS"
        and identifiers.get("PRODUCT_TYPE", "") == "EDR"
    ):
        return formats.mex_marsis.get_sample_type(
           base_samp_info["SAMPLE_TYPE"], base_samp_info["BYTES_PER_PIXEL"]
        )
    if (
        identifiers["DATA_SET_ID"] == "JNO-J-JIRAM-3-RDR-V1.0"
        and identifiers.get("PRODUCT_TYPE", "") == "RDR"
    ):
        return True, formats.juno.jiram_rdr_sample_type()
    if (
        identifiers["INSTRUMENT_ID"] == "LROC"
        and identifiers["PRODUCT_TYPE"] == "EDR"
    ):
        # unsigned integers not specified as such
        return True, formats.lroc.lroc_edr_sample_type()
    return False, None


def check_special_bit_column_case(identifiers: dict):
    instrument = identifiers["INSTRUMENT_NAME"]
    if instrument in (
        "ALPHA PARTICLE X-RAYSPECTROMETER",
        "JOVIAN AURORAL PLASMA DISTRIBUTIONS EXPERIMENT",
        "CHEMISTRY AND MINERALOGY INSTRUMENT",
        "MARS ADVANCED RADAR FOR SUBSURFACE ANDIONOSPHERE SOUNDING"
    ):
        return True, "MSB_BIT_STRING"
    return False, None


def check_special_bit_start_case(
    identifiers, list_of_pvl_objects_for_bit_columns, start_bit_list
):
    if identifiers["INSTRUMENT_NAME"] in "JOVIAN INFRARED AURORAL MAPPER":
        return formats.juno.bit_start_find_and_fix(
            list_of_pvl_objects_for_bit_columns, start_bit_list
        )
    return False, None


def check_special_block(name, data, identifiers):
    if name == "XDR_DOCUMENT":
        return True, formats.cassini.xdr_redirect_to_image_block(data)
    if name == "CHMN_HSK_HEADER_TABLE":
        return True, formats.msl_cmn.fix_mangled_name(data)
    if (
        identifiers["DATA_SET_ID"].startswith("JNO-E/J/SS")
        and "BSTFULL" in identifiers["DATA_SET_ID"]
        and "FREQ_OFFSET_TABLE" in data.keys()
        and name in ("FREQ_OFFSET_TABLE", "DATA_TABLE")
    ):
        return True, formats.juno.waves_burst_fix_table_names(data, name)
    return False, None


def check_trivial_case(pointer, identifiers, filename) -> tuple[bool, Optional[Callable]]:
    if is_trivial(pointer):
        return True, trivial
    if identifiers["INSTRUMENT_ID"] == "APXS" and "ERROR_CONTROL_TABLE" in pointer:
        return True, formats.msl_apxs.table_loader(pointer)
    if (
        identifiers["INSTRUMENT_NAME"] == "TRIAXIAL FLUXGATE MAGNETOMETER"
        and pointer == "TABLE" and "-EDR-" in identifiers["DATA_SET_ID"]
    ):
        return True, formats.galileo.galileo_table_loader()
    if (
        identifiers["INSTRUMENT_NAME"] == "CHEMISTRY CAMERA REMOTE MICRO-IMAGER"
        and pointer == "IMAGE_REPLY_TABLE"
    ):
        return True, formats.msl_ccam.image_reply_table_loader()
    if (
        identifiers["DATA_SET_ID"].startswith("ODY-M-THM-5")
        and (pointer in ("HEADER", "HISTORY"))
    ):
        return True, formats.themis.trivial_themis_geo_loader(pointer)
    if re.match(r"CO-(CAL-ISS|[S/EVJ-]+ISSNA/ISSWA-2)", identifiers["DATA_SET_ID"]):
        if pointer in ("TELEMETRY_TABLE", "LINE_PREFIX_TABLE"):
            return True, formats.cassini.trivial_loader(pointer)
    if (identifiers["SPACECRAFT_NAME"] == "MAGELLAN" and (filename.endswith(
            '.img') or filename.endswith('.ibg')) and pointer == "TABLE"):
        return True, formats.mgn.orbit_table_in_img_loader()
    return False, None


def special_image_constants(identifiers):
    consts = {}
    if identifiers["INSTRUMENT_ID"] == "CRISM":
        consts["NULL"] = 65535
    return consts


def check_special_fn(data, object_name, identifiers) -> tuple[bool, Optional[str]]:
    """
    special-case handling for labels with nonstandard filename specifications
    """
    if (
        (identifiers["DATA_SET_ID"] == "CLEM1-L-RSS-5-BSR-V1.0")
        and (object_name in ("HEADER_TABLE", "DATA_TABLE"))
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_fn(data, object_name)
    if (
        identifiers["SPACECRAFT_NAME"] == "MAGELLAN"
        and (data.filename.endswith('.img') or data.filename.endswith('ibg'))
        and object_name == "TABLE"
    ):
        return formats.mgn.get_fn(data)
    # filenames are frequently misspecified
    if str(identifiers["DATA_SET_ID"]).startswith("CO-D-CDA") \
            and (object_name == "TABLE"):
        return formats.cassini.cda_table_filename(data)
    # THEMIS labels don't always mention when a file is stored gzipped
    if identifiers["INSTRUMENT_ID"] == "THEMIS":
        return formats.themis.check_gzip_fn(data, object_name)
    return False, None


def check_special_qube_band_storage(identifiers):
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "CASSINI_ORBITER"
        # and object_name == "QUBE" #should be repetitive because it's only called
            # inside a QUBE reading function.
    ):
        return formats.cassini.get_special_qube_band_storage()
    return False, None
