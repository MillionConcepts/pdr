from __future__ import annotations
import re
from typing import TYPE_CHECKING, Optional

from pdr import formats
from pdr.loaders.utility import is_trivial

if TYPE_CHECKING:
    from pdr.pdrtypes import PDRLike


def check_special_offset(
    name: str, data: PDRLike, identifiers: dict, fn
) -> tuple[bool, Optional[int]]:
    # these incorrectly specify object length rather than
    # object offset in the ^HISTOGRAM pointer target
    if identifiers["INSTRUMENT_ID"] == "CHEMIN":
        return formats.msl_cmn.get_offset(name)
    if identifiers["DATA_SET_ID"] == "CLEM1-L-RSS-5-BSR-V1.0" and name in (
        "HEADER_TABLE",
        "DATA_TABLE",
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_offset(data, name)
    if identifiers["INSTRUMENT_ID"] == "THEMIS" and name == "QUBE":
        return formats.themis.get_qube_offset(data)
    if (
        identifiers["INSTRUMENT_NAME"] == "DESCENT IMAGER SPECTRAL RADIOMETER"
        and (identifiers["PRODUCT_TYPE"] == "RDR")
        or any(
            sub in identifiers["FILE_NAME"]
            for sub in [
                "STRIP",
                "VISIBL",
                "IMAGE",
                "IR_",
                "TIME",
                "SUN",
                "SOLAR",
            ]
        )
    ):
        return formats.cassini.get_offset(fn, identifiers)
    if (
        identifiers["INSTRUMENT_ID"] == "CRAT"
        and identifiers["PRODUCT_TYPE"] == "EDR"
        and name == "TABLE_1"
    ):
        return formats.lro.get_crater_offset()
    return False, None


def check_special_table_reader(
    identifiers, name, fn, fmtdef_dt, block, start_byte
):
    if identifiers["DATA_SET_ID"] in (
        "CO-S-MIMI-4-CHEMS-CALIB-V1.0",
        "CO-S-MIMI-4-LEMMS-CALIB-V1.0",
        "CO-S-MIMI-4-INCA-CALIB-V1.0",
        "CO-E/J/S/SW-MIMI-2-LEMMS-UNCALIB-V1.0",
        "CO-SSA-RADAR-3-ABDR-SUMMARY-V1.0",
    ):
        return True, formats.cassini.spreadsheet_loader(
            fn, fmtdef_dt, identifiers["DATA_SET_ID"]
        )
    if identifiers["INSTRUMENT_ID"] == "CHEMIN" and ("SPREADSHEET" in name):
        # mangled object names + positions
        return True, formats.msl_cmn.spreadsheet_loader(fn)
    if (
        identifiers["INSTRUMENT_NAME"]
        == "ROSETTA PLASMA CONSORTIUM - MUTUAL IMPEDANCE "
        "PROBE"
        and "SPECTRUM_TABLE" in name
    ):
        return True, formats.rosetta.rosetta_table_loader(fn, fmtdef_dt)
    if (
        identifiers["SPACECRAFT_NAME"] == "MAGELLAN"
        and name == "TABLE"
        and identifiers["NOTE"].startswith("Geometry")
    ) or (
        identifiers["DATA_SET_ID"] == "GO-J-NIMS-4-ADR-SL9IMPACT-V1.0"
        and name == "TABLE"
        and (
            "CAL_DATA.TAB" in identifiers["PRODUCT_ID"]
            or "G_DATA.TAB" in identifiers["PRODUCT_ID"]
            or "R_DATA.TAB" in identifiers["PRODUCT_ID"]
        )
    ):
        return True, formats.mgn.geom_table_loader(fn, fmtdef_dt)
    if (
        str(identifiers["DATA_SET_ID"]).startswith("MGN-V-RSS-5-OCC-PROF")
        and name == "TABLE"
    ):
        return True, formats.mgn.occultation_loader(
            identifiers, fmtdef_dt, block, fn
        )
    if (
        identifiers["INSTRUMENT_ID"] == "DLRE"
        and identifiers["PRODUCT_TYPE"] in ("GCP", "PCP", "PRP")
        and name == "TABLE"
    ):
        return True, formats.diviner.diviner_l4_table_loader(fmtdef_dt, fn)
    if (
        identifiers["DATA_SET_ID"] == "GO-J-PWS-5-DDR-PLASMA-DENSITY-FULL-V1.0"
        and name == "SPREADSHEET"
    ):
        return True, formats.galileo.pws_table_loader(fn, fmtdef_dt)
    if (
        identifiers["DATA_SET_ID"] == "ODY-M-GRS-5-ELEMENTS-V1.0"
        and name == "TABLE"
    ):
        return True, formats.odyssey.map_table_loader(fn, fmtdef_dt)
    if (
        identifiers["DATA_SET_ID"] == "MRO-M-MCS-5-DDR-V1.0"
        and name == "TABLE"
    ):
        return True, formats.mro.mcs_ddr_table_loader(
            fmtdef_dt, block, fn, start_byte
        )
    return False, None


def check_special_structure(block, name, fn, identifiers, data):
    if (
        identifiers["DATA_SET_ID"] == "CLEM1-L-RSS-5-BSR-V1.0"
        and name == "DATA_TABLE"
    ):
        # sequence wrapped as string for object names
        return True, formats.clementine.get_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "MARS GLOBAL SURVEYOR"
        and identifiers["INSTRUMENT_ID"] == "RSS"
        and identifiers["PRODUCT_TYPE"] == "ODF"
        and name == "ODF3B_TABLE"
    ):
        return True, formats.mgs.get_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "CASSINI ORBITER"
        and identifiers["INSTRUMENT_ID"] == "RPWS"
        and name == "TIME_SERIES"
    ) or (
        identifiers["INSTRUMENT_HOST_NAME"] == "HUYGENS PROBE"
        and (
            "HUY_DTWG_ENTRY_AERO" in fn
            or (
                "HASI" in data.metaget_("FILE_NAME", "")
                and "PWA" not in identifiers["FILE_NAME"]
            )
        )
    ):
        return True, formats.cassini.get_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "GP-J-NMS-3-ENTRY-V1.0"
        or identifiers["DATA_SET_ID"] == "GP-J-ASI-3-ENTRY-V1.0"
    ) and name == "TABLE":
        return True, formats.galileo.probe_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "GO-E-EPD-2-SAMP-PAD-V1.0"
        and identifiers["PRODUCT_ID"] == "E1PAD_7.TAB"
        and name == "TIME_SERIES"
    ):
        return True, formats.galileo.epd_structure(
            block, name, fn, data, identifiers
        )
    if (
        "VEGA" in identifiers["DATA_SET_ID"]
        and "-C-DUCMA-3-RDR-HALLEY-V1.0" in identifiers["DATA_SET_ID"]
        and name == "TABLE"
    ):
        return True, formats.vega.get_structure(
            block, name, fn, data, identifiers
        )
    if (
        "GIO-C-PIA-3-RDR-HALLEY-V1.0" == identifiers["DATA_SET_ID"]
        or re.match(r"VEGA.-C-PUMA.*", str(identifiers["DATA_SET_ID"]))
    ) and name == "ARRAY":
        return True, formats.vega.fix_array_structure(
            name, block, fn, data, identifiers
        )
    if (
        (identifiers["DATA_SET_ID"] == "MRO-M-MCS-4-RDR-V1.0"
        or identifiers["DATA_SET_ID"] == "MRO-M-MCS-2-EDR-V1.0")
        and name == "TABLE"
    ):
        return True, formats.mro.get_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "ULY-J-GAS-5-SKY-MAPS-V1.0"
        and name == "TABLE"
        and block["^STRUCTURE"] == "GASDATA.FMT"
    ):
        return True, formats.ulysses.get_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "VG2-SS-PLS-4-SUMM-1HR-AVG-V1.0"
        and name == "TABLE"
        and block["^STRUCTURE"] == "VGR_PLS_HR_2017.FMT"
    ):
        return True, formats.voyager.get_structure(
            block, name, fn, data, identifiers
        )
    return False, None


def check_special_position(identifiers, block, target, name, fn, start_byte):
    if (
        identifiers["INSTRUMENT_ID"] == "MARSIS"
        and " TEC " in identifiers["DATA_SET_NAME"]
    ):
        return True, formats.mex_marsis.get_position(
            identifiers, block, target, name, start_byte
        )
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "HUYGENS PROBE"
        and any(
            sub in identifiers["FILE_NAME"]
            for sub in [
                "DARK",
                "STRIP",
                "VIS_EX",
                "SUN",
                "VISIBL",
                "TIME",
                "SOLAR",
                "IMAGE",
            ]
        )
        or (
            identifiers["INSTRUMENT_NAME"]
            == "DESCENT IMAGER SPECTRAL RADIOMETER"
            and identifiers["PRODUCT_TYPE"] == "RDR"
        )
        and (name in ("TABLE", "HEADER"))
    ):
        return True, formats.cassini.get_position(
            identifiers, block, target, name, fn, start_byte
        )
    if (
        identifiers["DATA_SET_ID"] == "LRO-L-RSS-1-TRACKING-V1.0"
        and name == "WEAREC_TABLE"
    ):
        return formats.lro.rss_get_position(
            identifiers, block, target, name, start_byte
        )
    if (
        identifiers["DATA_SET_ID"] == "DIF-C-HRIV/MRI-5-HARTLEY2-SHAPE-V1.0"
        and identifiers["PRODUCT_ID"] == "HARTLEY2-CARTESIAN-PLATE-MODEL"
        and "TABLE" in name
    ):
        return True, formats.epoxi.cart_model_get_position(
            identifiers, block, target, name, start_byte
            )
    return False, None


def check_special_sample_type(
    identifiers: dict,
    base_samp_info: dict,
) -> tuple[bool, Optional[str]]:
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
    if (
        identifiers["DATA_SET_ID"] == "MGN-V-RDRS-5-GVDR-V1.0"
        and "GVANF" in identifiers["PRODUCT_ID"]
        and "N/A" in base_samp_info["SAMPLE_TYPE"]
    ):
        return True, formats.mgn.gvanf_sample_type()
    if identifiers["DATA_SET_ID"] == "LRO-L-CRAT-2-EDR-RAWDATA-V1.0":
        return formats.lro.crater_bit_col_sample_type(base_samp_info)
    if (
        identifiers["SPACECRAFT_NAME"] == "GALILEO_ORBITER"
        and "-NIMS-2-EDR-V1.0" in identifiers["DATA_SET_ID"]
    ):
        return formats.galileo.nims_edr_sample_type(base_samp_info)
    if (
        identifiers["DATA_SET_ID"] == "ULY-J-EPAC-4-SUMM-PHA-24HR-V1.0"
        and identifiers["PRODUCT_ID"].endswith("BIN")
    ):
        return formats.ulysses.get_sample_type(base_samp_info)
    return False, None


def check_special_bit_column_case(identifiers: dict):
    instrument = identifiers["INSTRUMENT_NAME"]
    if instrument in (
        "ALPHA PARTICLE X-RAYSPECTROMETER",
        "JOVIAN AURORAL PLASMA DISTRIBUTIONS EXPERIMENT",
        "CHEMISTRY AND MINERALOGY INSTRUMENT",
        "MARS ADVANCED RADAR FOR SUBSURFACE ANDIONOSPHERE SOUNDING",
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
        str(identifiers["DATA_SET_ID"]).startswith("JNO-E/J/SS")
        and "BSTFULL" in identifiers["DATA_SET_ID"]
        and "FREQ_OFFSET_TABLE" in data.keys()
        and name in ("FREQ_OFFSET_TABLE", "DATA_TABLE")
    ):
        return True, formats.juno.waves_burst_fix_table_names(data, name)
    if (
        identifiers["INSTRUMENT_ID"] == "LAMP"
        and identifiers["PRODUCT_TYPE"] == "RDR"
        and "IMAGE" in name
        and "HISTOGRAM" in name
    ):
        # multiple image objects are defined by one non-unique image object
        return True, formats.lro.lamp_rdr_histogram_image_loader(data)
    if (
        identifiers["DATA_SET_ID"] == "LRO-L-MRFLRO-5-GLOBAL-MOSAIC-V1.0"
        and "GLOBAL_S4_32PPD" in data.metaget_("PRODUCT_ID")
        and name == "IMAGE"
    ):
        # typo in one of the labels
        return True, formats.lro.mini_rf_image_loader(data, name)
    if (
        identifiers["DATA_SET_ID"] == "PVO-V-ORPA-5-ELE/ION/PHOTO/UADS-V1.0"
        and "ORPA_LOW_RES" in identifiers["PRODUCT_ID"]
        and name == "TABLE"
    ):
        return True, formats.pvo.orpa_low_res_loader(data, name)
    if (
        identifiers["DATA_SET_ID"] == "PVO-V-OIMS-4-IONDENSITY-12S-V1.0"
        and name == "TABLE"
    ):
        return True, formats.pvo.oims_12s_loader(data, name)
    if (
        "GO-E-EPD-4-SUMM-" in identifiers["DATA_SET_ID"]
        and "E1_" in identifiers["PRODUCT_ID"]
        and name == "TIME_SERIES"
    ):
        return True, formats.galileo.epd_special_block(data, name)
    if (
        identifiers["INSTRUMENT_NAME"] == "PLASMA WAVE RECEIVER"
        and "SUMM" in identifiers["DATA_SET_ID"]
        and (name == "TIME_SERIES" or name == "TABLE")
    ):
        return True, formats.galileo.pws_special_block(data, name)
    if (
        "ULY-J-EPAC-4-SUMM-PSTL" in identifiers["DATA_SET_ID"]
        and name == "TABLE"
    ):
        return True, formats.ulysses.get_special_block(data, name)
    if (
        "VG2-N-MAG-4-RDR-HGCOORDS" in identifiers["DATA_SET_ID"]
        and identifiers["STANDARD_DATA_PRODUCT_ID"] == "ASCII DATA"
        and name == "TABLE"
    ):
        return True, formats.voyager.mag_special_block(data, name)
    if (
        identifiers["DATA_SET_ID"] == "VG2-SS-PLS-4-SUMM-1HR-AVG-V1.0"
        and name == "TABLE"
    ):
        return formats.voyager.pls_avg_special_block(data, name)
    if (
        identifiers["DATA_SET_ID"] == "VG2-SS-PLS-3-RDR-FINE-RES-V1.0"
        and name == "TABLE"
    ):
        return formats.voyager.pls_fine_special_block(data, name)
    if (
        identifiers["DATA_SET_ID"] == "VG2-U-PLS-5-SUMM-IONBR-48SEC-V1.0"
        and identifiers["PRODUCT_ID"] == "SUMRY.DAT"
        and name == "TIME_SERIES"
    ):
        return formats.voyager.pls_ionbr_special_block(data, name, identifiers)
    return False, None


def check_trivial_case(pointer, identifiers, fn) -> bool:
    if is_trivial(pointer):
        return True
    if (
        identifiers["INSTRUMENT_ID"] == "APXS"
        and "ERROR_CONTROL_TABLE" in pointer
    ):
        return formats.msl_apxs.table_loader(pointer)
    if (
        identifiers["INSTRUMENT_NAME"] == "TRIAXIAL FLUXGATE MAGNETOMETER"
        and pointer == "TABLE"
        and "-EDR-" in identifiers["DATA_SET_ID"]
    ):
        return formats.galileo.galileo_table_loader()
    if (
        identifiers["INSTRUMENT_NAME"]
        == "CHEMISTRY CAMERA REMOTE MICRO-IMAGER"
        and pointer == "IMAGE_REPLY_TABLE"
    ):
        return formats.msl_ccam.image_reply_table_loader()
    if str(identifiers["DATA_SET_ID"]).startswith("ODY-M-THM-5") and (
        pointer in ("HEADER", "HISTORY")
    ):
        return formats.themis.trivial_themis_geo_loader(pointer)
    if re.match(
        r"CO-(CAL-ISS|[S/EVJ-]+ISSNA/ISSWA-2)", str(identifiers["DATA_SET_ID"])
    ):
        if pointer in ("TELEMETRY_TABLE", "LINE_PREFIX_TABLE"):
            return formats.cassini.trivial_loader(pointer)
    if (
        identifiers["SPACECRAFT_NAME"] == "MAGELLAN"
        and (fn.endswith(".img") or fn.endswith(".ibg"))
        and pointer == "TABLE"
    ):
        return formats.mgn.orbit_table_in_img_loader()
    if (
        "GO-A-SSI-3-" in identifiers["DATA_SET_ID"]
        and "-CALIMAGES-V1.0" in identifiers["DATA_SET_ID"]
        and "QUB" in identifiers["PRODUCT_ID"]
        and pointer == "HEADER"
    ):
        return formats.galileo.ssi_cubes_header_loader()
    if identifiers["INSTRUMENT_ID"] == "CHEMIN" and (pointer == "HEADER"):
        return formats.msl_cmn.trivial_header_loader()
    return False


def special_image_constants(identifiers):
    consts = {}
    if identifiers["INSTRUMENT_ID"] == "CRISM":
        consts["NULL"] = 65535
    return consts


def check_special_fn(
    data, object_name, identifiers
) -> tuple[bool, Optional[str]]:
    """
    special-case handling for labels with nonstandard filename specifications
    """
    if (identifiers["DATA_SET_ID"] == "CLEM1-L-RSS-5-BSR-V1.0") and (
        object_name in ("HEADER_TABLE", "DATA_TABLE")
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_fn(data, object_name)
    if (
        identifiers["SPACECRAFT_NAME"] == "MAGELLAN"
        and (data.filename.endswith(".img") or data.filename.endswith("ibg"))
        and object_name == "TABLE"
    ):
        return formats.mgn.get_fn(data)
    # filenames are frequently misspecified
    if str(identifiers["DATA_SET_ID"]).startswith("CO-D-CDA") and (
        object_name == "TABLE"
    ):
        return formats.cassini.cda_table_filename(data)
    # THEMIS labels don't always mention when a file is stored gzipped
    if identifiers["INSTRUMENT_ID"] == "THEMIS":
        return formats.themis.check_gzip_fn(data, object_name)
    if (
        identifiers["DATA_SET_ID"] in ["NH-P-PEPSSI-4-PLASMA-V1.0",
                                       "NH-X-SWAP-5-DERIVED-SOLARWIND-V1.0",
                                       "NH-P/PSA-LORRI/ALICE/REX-5-ATMOS-V1.0"]
        and object_name == "SPREADSHEET"
    ):
        return formats.nh.get_fn(data)
    return False, None


def check_special_qube_band_storage(identifiers):
    if (
        identifiers["INSTRUMENT_HOST_NAME"]
        == "CASSINI_ORBITER"
        # and object_name == "QUBE" #should be repetitive because it's only called
        # inside a QUBE reading function.
    ):
        return formats.cassini.get_special_qube_band_storage()
    return False, None


def check_special_hdu_name(data, identifiers, fn, name):
    if (
        identifiers['INSTRUMENT_HOST_NAME'] == 'DAWN'
        and 'FC2' in identifiers['DATA_SET_ID']
    ):
        return True, formats.dawn.dawn_hdu_name(name)
    if identifiers['DATA_SET_ID'].startswith('MSGR-H-MDIS-6-CAL'):
        return True, formats.galileo.mdis_hdu_name(name)
    if (
        identifiers["INSTRUMENT_NAME"] == "STUDENT DUST COUNTER"
        and '-SDC-' in identifiers["DATA_SET_ID"]
        and identifiers['PRODUCT_TYPE'] == 'EDR'
    ):
        return True, formats.nh.sdc_edr_hdu_name(name)
    if re.match(r"NH-\w-REX-[23]", identifiers['DATA_SET_ID']):
        return True, formats.nh.rex_hdu_name(name)
    if identifiers['INSTRUMENT_ID'] == 'PEPSSI':
        if re.search(
            r"(JUPITER|LAUNCH|CRUISE)", identifiers['DATA_SET_ID']
        ):
            return False, None  # these seem ok
        elif identifiers['PRODUCT_TYPE'] == 'EDR':
            return True, formats.nh.pepssi_edr_hdu_name(name)
        elif "PLUTO" in identifiers['DATA_SET_ID']:
            return True, formats.nh.pepssi_pluto_rdr_hdu_name(name)
        else:
            return True, formats.nh.pepssi_rdr_hdu_name(name)
    if re.match(r"NH.*SWAP", identifiers["DATA_SET_ID"]):
        return True, formats.nh.swap_hdu_stubs(data, identifiers, fn, name)
    if identifiers['DATA_SET_ID'].startswith('HST-S-WFPC2-3-RPX'):
        return True, formats.saturn_rpx.hst_hdu_name(name)
    return False, None
