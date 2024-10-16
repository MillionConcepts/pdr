"""
This module contains functions that preempt generic metadata- or data-parsing
behaviors. They are intended to manage idiosyncracies common to all products
of a particular type (or even all products in a whole dataset), including but
not limited to:

* Malformatted labels
* Incorrect metadata
* Malformatted data
* Technically correct but extremely unusual data formatting

To put this another way, they facilitate single-dispatch polymorphism on the
semantic level of data product type.

Most functions in this file are intended to be applied by `func.specialize`
as wrappers to other functions, typically a query function in `loaders.queries`
or the `loader_function` attribute of a `loaders.queries.Loader` subclass.
However, this is not strict; they may also wrap functions in other
modules, and functions may call them inline rather than use them as wrappers.

Every function in this module should be named `check_special_{something}`,
where 'something' clearly designates the metadata-parsing or data-loading
behavior it may sometimes preempt.

Most functions in this module should return a tuple whose first element is a
`bool` and whose second element is the "special" value. If the first element
is `True`, it means that there is a relevant special case, so the caller
should use the "special" value instead of engaging in its normal behavior; if
it is `False`, there is no relevant special case and the caller should continue
with its normal behavior. The second element of the tuple should always be
`None` if the first element is `False`.

If the function is intended to wrap a generic function, the second element of
this tuple, when not None, must always share the return type of that generic
function. Also, if it is intended for the `func.softquery()` workflow, it
should follow that workflow's argument naming and type annotation conventions.

Exceptions to these naming and signature conventions can be made for checkers
designed specifically to be called inline of a specific handler function.
"""
from __future__ import annotations
import re
from typing import Any, Mapping, Optional, TYPE_CHECKING

from multidict import MultiDict

from pdr import formats
from pdr.loaders.utility import is_trivial

if TYPE_CHECKING:
    from pdr.loaders.astrowrap import HDUList
    import numpy as np
    import pandas as pd

    from pdr.pdrtypes import DataIdentifiers, PDRLike, PhysicalTarget


def check_special_offset(
    name: str, data: PDRLike, identifiers: DataIdentifiers, fn: str
) -> tuple[bool, Optional[int]]:
    """
    Preempt generic inference of an object's byte offset within a file. Wraps
    `loaders.queries.data_start_byte()`.
    """
    # these incorrectly specify object length rather than
    # object offset in the ^HISTOGRAM pointer target
    if identifiers["INSTRUMENT_ID"] == "CHEMIN":
        return formats.msl_cmn.get_offset(name)
    if (
        identifiers["DATA_SET_ID"] == "CLEM1-L-RSS-5-BSR-V1.0"
        and re.match("(HEADER|DATA)_TABLE", name)
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_offset(data, name)
    if identifiers["INSTRUMENT_ID"] == "THEMIS" and name == "QUBE":
        return formats.themis.get_qube_offset(data)
    disrsubs = re.compile(r"STRIP|VISIBL|IMAGE|IR_|TIME|SUN|SOLAR")
    if (
        identifiers["INSTRUMENT_NAME"] == "DESCENT IMAGER SPECTRAL RADIOMETER"
        and identifiers["PRODUCT_TYPE"] == "RDR"
        or disrsubs.search(identifiers["FILE_NAME"])
    ):
        return formats.cassini.get_offset(fn, identifiers)
    if (
        identifiers["INSTRUMENT_ID"] == "CRAT"
        and identifiers["PRODUCT_TYPE"] == "EDR"
        and name == "TABLE_1"
    ):
        return formats.lro.get_crater_offset()
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-SSI-5-ATMOS-OPACITY-V1.0"
        and "TABLE" in name
    ):
        return formats.phoenix.phxao_table_offset(fn, identifiers)
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-MECA-4-NIRDR-V1.0"
        and identifiers["PRODUCT_TYPE"] in ("MECA_WCL_CP", "MECA_WCL_CV")
        and "TABLE" in name
    ):
        return formats.phoenix.wcl_rdr_offset(data, name)
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "MARS SCIENCE LABORATORY"
        and identifiers["INSTRUMENT_ID"] == "REMS"
        and name == "REMS_REPORT_TABLE"
        and ("HSDEF__" in identifiers["PRODUCT_ID"] or 
             "HSREG__" in identifiers["PRODUCT_ID"])
    ):
        return formats.msl_rems.edr_offset(data, name)
    return False, None


def check_special_table_reader(
    identifiers: DataIdentifiers,
    name: str,
    fn: str,
    fmtdef_dt: tuple[pd.DataFrame, np.dtype],
    block: MultiDict,
    start_byte: int,
):
    """Preempt loaders.datawrap.ReadTable's dispatch to `read_table()`."""
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
        "MSL-M-SAM-" in identifiers["DATA_SET_ID"]
        and "QMS" in identifiers["PRODUCT_ID"]
        and "TABLE" in name
    ):
        # reusing the msl_cmn special case for msl_sam qms tables
        return True, formats.msl_cmn.spreadsheet_loader(fn)
    if (
        identifiers["DATA_SET_ID"] == "MSL-M-ROVER-6-RDR-PLACES-V1.0"
        and name == "SPREADSHEET"
    ):
        return True, formats.msl_places.spreadsheet_loader(fn, fmtdef_dt)
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
        identifiers["DATA_SET_ID"].startswith("MGN-V-RSS-5-OCC-PROF")
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
        identifiers["DATA_SET_ID"] == "ULY-J-GAS-5-SKY-MAPS-V1.0"
        and name == "TABLE"
        and block["^STRUCTURE"] == "GASDATA.FMT"
    ):
        return True, formats.ulysses.gas_table_loader(fn, fmtdef_dt)
    if (
        identifiers["DATA_SET_ID"] == "MRO-M-MCS-5-DDR-V1.0"
        and name == "TABLE"
    ):
        return True, formats.mro.mcs_ddr_table_loader(
            fmtdef_dt, block, fn, start_byte
        )
    if (
        identifiers["DATA_SET_ID"] == "IHW-C-IRFCURV-3-EDR-HALLEY-V2.0"
        and name == "TABLE"
    ):
        return True, formats.ihw.curve_table_loader(fn, fmtdef_dt)
    if (
        identifiers["DATA_SET_ID"]
        in (
            "IHW-C-PPFLX-3-RDR-HALLEY-V1.0",
            "IHW-C-PPOL-3-RDR-HALLEY-V1.0",
            "IHW-C-PPSTOKE-3-RDR-HALLEY-V1.0",
            "IHW-C-PPMAG-3-RDR-HALLEY-V1.0",
            "IHW-C-MSNRDR-3-RDR-HALLEY-ETA-AQUAR-V1.0",
            "IHW-C-MSNRDR-3-RDR-HALLEY-ORIONID-V1.0",
            "IHW-C-MSNVIS-3-RDR-HALLEY-ETA-AQUAR-V1.0",
            "IHW-C-MSNVIS-3-RDR-HALLEY-ORIONID-V1.0",
            "IHW-C-IRFTAB-3-RDR-HALLEY-V1.0",
            "IHW-C-IRPOL-3-RDR-HALLEY-V1.0",
            "IHW-C-IRPHOT-3-RDR-HALLEY-V1.0",
        )
        and name == "TABLE"
    ):
        return True, formats.ihw.add_newlines_table_loader(
            fmtdef_dt, block, fn, start_byte
        )
    if (
        identifiers["DATA_SET_ID"] == "VG1-J-LECP-4-SUMM-SECTOR-15MIN-V1.1"
        and name == "TABLE"
    ):
        return True, formats.voyager.lecp_table_loader(fn, fmtdef_dt)
    if (
        identifiers["DATA_SET_ID"] == "VG2-U-LECP-4-RDR-STEP-12.8MIN-V1.0"
        and block["INTERCHANGE_FORMAT"] == "ASCII"
        and name == "TABLE"
    ):
        return True, formats.voyager.lecp_table_loader(fn, fmtdef_dt)
    if (
        identifiers["DATA_SET_ID"] == "VG1-S-LECP-3-RDR-STEP-6MIN-V1.0"
        and name == "SPREADSHEET"
    ):
        return True, formats.voyager.lecp_vg1_sat_table_loader(fn, fmtdef_dt)
    if identifiers["DATA_SET_ID"] == "VL2-M-SEIS-5-RDR-V1.0" and name in (
        "TABLE",
        "SPREADSHEET",
    ):
        return True, formats.viking.seis_table_loader(fn, fmtdef_dt)
    if (
        "MEX-M-ASPERA3-2-EDR-IMA" in identifiers["DATA_SET_ID"]
        and name == "SPREADSHEET"
    ):
        return True, formats.mex.aspera_table_loader(fn, fmtdef_dt)
    if (
        re.match(r"MER[12]-M-RSS-1-EDR-V1.0", identifiers["DATA_SET_ID"])
        and identifiers["PRODUCT_TYPE"] == "UHFD"
        and name == "SPREADSHEET"
    ):
        return True, formats.mer.rss_spreadsheet_loader(fn, fmtdef_dt)
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-MECA-4-NIRDR-V1.0"
        and identifiers["INSTRUMENT_ID"] == "MECA_AFM"
        and "TABLE" in name
    ):
        return True, formats.phoenix.afm_table_loader(fn, fmtdef_dt, name)
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "MARS EXPRESS"
        and identifiers["INSTRUMENT_ID"] == "MRS"
        and all(x in identifiers["PRODUCT_ID"] for x in ["ODF","L1B"])
        and "TABLE" in name
    ):
        return True, formats.mex.mrs_l1b_odf_table_loader(fn, fmtdef_dt)
    if (
        identifiers["DATA_SET_ID"] == "LRO-L-MRFLRO-1-PDR-V1.0"
        and "HK_" in identifiers["PRODUCT_ID"]
        and name == "SPREADSHEET"
    ):
        return True, formats.lro.mini_rf_spreadsheet_loader(fn, fmtdef_dt)
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "MARS SCIENCE LABORATORY"
        and identifiers["INSTRUMENT_ID"] == "REMS"
        and "TABLE" in name
        and "SP_____" in identifiers["PRODUCT_ID"]
    ):
        return True, formats.msl_rems.edr_table_loader(
            fn, fmtdef_dt, block, start_byte
        )
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "MARS SCIENCE LABORATORY"
        and identifiers["INSTRUMENT_ID"] == "REMS"
        and name == "REMS_SCIENCE_TABLE"
        and "RDR" in identifiers["DATA_SET_ID"]
    ):
        return True, formats.msl_rems.rdr_table_loader(fn, fmtdef_dt)
    if (
        all(x in identifiers["DATA_SET_ID"] for x in ["ICE-C-","-3-RDR-"])
        and "TRAJ_ICE" in fn
        and name == "TABLE"
    ):
        return True, formats.ihw.add_newlines_table_loader(
            fmtdef_dt, block, fn, start_byte
        )
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "LUNAR RECONNAISSANCE ORBITER"
        and identifiers["INSTRUMENT_NAME"] == "RADIO SCIENCE SUBSYSTEM"
        and name == "WEAREC_TABLE"
    ):
        return True, formats.lro.wea_table_loader(fn, fmtdef_dt)
    return False, None


def check_special_structure(
    name: str,
    block: MultiDict,
    fn: str,
    data: PDRLike,
    identifiers: DataIdentifiers
) -> tuple[bool, Optional[tuple[pd.DataFrame, Optional[np.dtype]]]]:
    """
    Preempt generic ARRAY/TABLE/SPREADSHEET format definition parsing. Wraps
    `parse_array_structure()` and `parse_table_structure()`.
    """
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
        return True, formats.mgs.get_odf_structure(
            block, name, fn, data, identifiers
        )

    if (
        identifiers.get("INSTRUMENT_HOST_NAME") == "MARS GLOBAL SURVEYOR"
        and identifiers.get("INSTRUMENT_NAME") == "RADIO SCIENCE SUBSYSTEM"
        and identifiers.get("PRODUCT_TYPE") == "ECS"
    ):
        return True, formats.mgs.get_ecs_structure(
            block, name, fn, data, identifiers
        )
    # TODO: yikes
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
        re.match(
            r"GP-J-(NMS|ASI)-3-ENTRY-V1.0", identifiers["DATA_SET_ID"]
        )
        and name == "TABLE"
    ):
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
        or re.match(r"VEGA.-C-PUMA.*", identifiers["DATA_SET_ID"])
    ) and name == "ARRAY":
        return True, formats.vega.fix_array_structure(
            name, block, fn, data, identifiers
        )
    if (
        re.match(r"MRO-M-MCS-(4-RDR|2-EDR)-V1.0", identifiers["DATA_SET_ID"])
        and name == "TABLE"
    ):
        return True, formats.mro.get_structure(
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
    if "IHW-C-SPEC-" in identifiers["DATA_SET_ID"] and name == "SPECTRUM":
        return True, formats.ihw.get_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-MECA-2-NIEDR-V1.0"
        and name == "TBL_TABLE"
        and block["CONTAINER"]["^STRUCTURE"] == "TBL_0_STATE_DATA.FMT"
    ):
        return True, formats.phoenix.elec_em6_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-MECA-4-NIRDR-V1.0"
        and identifiers["INSTRUMENT_ID"] == "MECA_AFM"
        and "HEADER_TABLE" in name
    ):
        return True, formats.phoenix.afm_rdr_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-TEGA-2-LEDEDR-V1.0"
        and name == "TIME_SERIES"
        and block["^STRUCTURE"] == "TEGA_LED.FMT"
    ):
        return True, formats.phoenix.led_edr_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-TEGA-4-SCRDR-V1.0"
        and name == "TIME_SERIES"
        and block["^STRUCTURE"] == "TEGA_SCRDR.FMT"
    ):
        return True, formats.phoenix.sc_rdr_structure(
            block, name, fn, data, identifiers
        )
    if (
        identifiers["DATA_SET_ID"] == "MEX-SUN-ASPERA3-4-SWM-V1.0"
        and name == "TABLE"
    ):
        return True, formats.mex.aspera_ima_ddr_structure(
            block, name, fn, data, identifiers
        )
    if (
        "-MIDAS-3-" in identifiers["DATA_SET_ID"]
        and "SPS" in identifiers["PRODUCT_ID"]
        and name == "TIME_SERIES"
    ):
        return True, formats.rosetta.midas_rdr_sps_structure(
            block, name, fn, data, identifiers
        )
    if (
        "-MIDAS-3-" in identifiers["DATA_SET_ID"]
        and "FSC" in identifiers["PRODUCT_ID"]
        and name == "FREQUENCY_SERIES"
    ):
        return True, formats.rosetta.fix_pad_length_structure(
            block, name, fn, data, identifiers
        )
    if (
        "ROSETTA" in identifiers["DATA_SET_NAME"] 
        and "CONSERT" in identifiers["DATA_SET_NAME"]
        and "TABLE" in name
        and name.startswith(("I_", "Q_"))
    ):
        if "GRNDBENCH" in identifiers["DATA_SET_ID"]:
            return False, None
        return True, formats.rosetta.fix_pad_length_structure(
            block, name, fn, data, identifiers
        )
    return False, None


def check_special_position(
    identifiers: DataIdentifiers,
    block: MultiDict,
    target: PhysicalTarget,
    name: str,
    fn: str,
    start_byte: int,
) -> tuple[bool, Optional[int]]:
    """
    Preempt generic detection of a table's row or byte offset within a file.
    Wraps `table_position()`. Used for table-specific cases that are partially
    but not wholly handled by `data_start_byte()`, so should not be defined
    in `check_special_offset()`.
    """
    if (
        identifiers["INSTRUMENT_ID"] == "MARSIS"
        and " TEC " in identifiers["DATA_SET_NAME"]
    ):
        return True, formats.mex.marsis_get_position(
            identifiers, block, target, name, start_byte
        )
    huysubs = re.compile(r"DARK|STRIP|VIS_EX|SUN|VISIBL|TIME|SOLAR|IMAGE")
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "HUYGENS PROBE"
        and huysubs.search(identifiers["FILE_NAME"])
        or (
            identifiers["INSTRUMENT_NAME"]
            == "DESCENT IMAGER SPECTRAL RADIOMETER"
            and identifiers["PRODUCT_TYPE"] == "RDR"
        )
        and name in ("TABLE", "HEADER")
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
    if (
        "MEX-M-MRS-5-OCC" in identifiers["DATA_SET_ID"]
        and name == "ATM_TABLE"
    ):
        return True, formats.mex.mrs_ddr_atmo_position(
            identifiers, block, target, name, start_byte
        )
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-SSI-5-ATMOS-OPACITY-V1.0"
        and "HEADER" in name
    ):
        return True, formats.phoenix.phxao_header_position(
            identifiers, block, target, name, start_byte
        )
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "MARS EXPRESS"
        and identifiers["INSTRUMENT_ID"] == "MRS"
        and all(x in identifiers["PRODUCT_ID"] for x in ["ICL","L1B"])
        and name == "DOPPLER_TABLE"
    ):
        return True, formats.mex.mrs_get_position(
            identifiers, block, target, name, start_byte
        )
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "MARS EXPRESS"
        and identifiers["INSTRUMENT_ID"] == "MRS"
        and all(x in identifiers["PRODUCT_ID"] for x in ["ODF","L02"])
        and name == "RANGING_TABLE"
    ):
        return True, formats.mex.mrs_get_position(
            identifiers, block, target, name, start_byte
        )
    return False, None


def check_special_sample_type(
    identifiers: DataIdentifiers,
    base_samp_info: dict,
) -> tuple[bool, Optional[str]]:
    """
    Preempt generic mapping of PDS3 data types to numpy dtype strings. Wraps
    `image_sample_type()`; called inline by `insert_sample_types_into_df()`.
    """
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


def check_special_bit_column_case(
    identifiers: Mapping[str, Any]
) -> tuple[bool, Optional[str]]:
    """
    Special case checker used by `bit_handling.set_bit_string_data_type()`
    to preempt generic data type inference.
    """
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
) -> tuple[bool, Optional[list[int]]]:
    """
    Special case checker used by get_bit_start_and_size() to fix
    incorrectly-defined bit offsets.
    """
    if identifiers["INSTRUMENT_NAME"] in "JOVIAN INFRARED AURORAL MAPPER":
        return formats.juno.bit_start_find_and_fix(
            list_of_pvl_objects_for_bit_columns, start_bit_list
        )
    return False, None


def check_special_bit_format(
    obj: dict,
    definition: MultiDict,
    identifiers: DataIdentifiers
) -> tuple[bool, Optional[dict]]:
    """
    Special case checker used by add_bit_column_info() to fix problems in `obj` 
    and/or `definition` caused by mistakes in an external format file. Intended 
    for cases where check_special_block() doesn't touch the relevant metadata, 
    and errors are hit before check_special_structure() can be useful.
    """
    if re.match(
        r"CO-(CAL-ISS|[S/EVJ-]+ISSNA/ISSWA-2)", identifiers["DATA_SET_ID"]
    ):
        return formats.cassini.iss_telemetry_bit_col_format(obj, definition)
    if (
        identifiers["SPACECRAFT_NAME"] == "GALILEO ORBITER"
        and identifiers["INSTRUMENT_NAME"] == "SOLID_STATE_IMAGING"
    ):
        return formats.galileo.ssi_telemetry_bit_col_format(definition)
    return False, None


def specialblock(data: PDRLike, name: str):
    """
    Special-purpose wrapper for check_special_block() intended for use
    outside of the query workflow.
    """
    is_special, block = check_special_block(name, data, data.identifiers)
    if is_special is True:
        return block
    return data.metablock_(name)


def check_special_block(
    name: str, data: PDRLike, identifiers: Mapping
) -> tuple[bool, Optional[MultiDict]]:
    """
    `specialize()` target for `queries.get_block()`. Intended for cases in
    which label pointers don't correspond to label block names AND/OR if a
    value within the block needs to be changed before going to other functions.
    """
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
    if "ULY-J-EPAC-4-SUMM" in identifiers["DATA_SET_ID"] and name == "TABLE":
        return True, formats.ulysses.get_special_block(data, name, identifiers)
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
        return formats.voyager.pls_ionbr_special_block(data, name)
    if identifiers["DATA_SET_ID"] == "M9-M-IRIS-3-RDR-V1.0" and (
        name == "SPECTRAL_SERIES"  # the data product
        or "SPECTRUM" in name  # the calibration data
    ):
        return True, formats.mariner.get_special_block(data, name)
    if (
        re.match(
            r"IHW-C-MSNRDR-3-RDR-HALLEY-(ETA-AQUAR|ORIONID)-V1.0",
            identifiers["DATA_SET_ID"],
        )
        and name == "TABLE"
    ):
        return True, formats.ihw.get_special_block(data, name)
    if (
        "VG2-" in identifiers["DATA_SET_ID"]
        and "-PRA-3-RDR-LOWBAND-6SEC-V1.0" in identifiers["DATA_SET_ID"]
        and name == "TABLE"
    ):
        return formats.voyager.pra_special_block(data, name, identifiers)
    if (
        identifiers["DATA_SET_ID"] == "PHX-M-MECA-2-NIEDR-V1.0"
        and re.match(r"MECA-EM1[012]", identifiers["PRODUCT_TYPE"])
        and name == "WCHEM_TABLE"
    ):
        return True, formats.phoenix.wcl_edr_special_block(data, name)
    if (
        "MEX-M-PFS-2-EDR-" in identifiers["DATA_SET_ID"]
        and (
            "RAW" in identifiers["PRODUCT_ID"]
            or "HK" in identifiers["PRODUCT_ID"]
        )
        and name == "TABLE"
    ):
        return formats.mex.pfs_edr_special_block(data, name)
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "MARS EXPRESS"
        and identifiers["INSTRUMENT_ID"] == "MRS"
        and all(x in identifiers["PRODUCT_ID"] for x in ["ODF","L1B","RMP"]) 
        and "TABLE" in name
    ):
        return True, formats.mex.mrs_l1b_odf_rmp_redirect(data)
    if (
        identifiers["DATA_SET_ID"] == "WFF-E-ATM-1/5-V1.0"
        and name == "IMAGE"
    ):
        return formats.ground.wff_atm_special_block(data, name)
    if (
        identifiers["DATA_SET_ID"] == "CO-CAL-ISS-2-V1.0"
        and name == "IMAGE"
        and ".DA" in data.metaget_("^IMAGE")[0]
    ):
        return formats.cassini.iss_calib_da_special_block(data, name)
    if (
        identifiers["DATA_SET_ID"] == "MGS-M-MOLA-3-PEDR-L1A-V1.0"
        and "TABLE" in name
    ):
        return True, formats.mgs.mola_pedr_special_block(data, name, identifiers)
    if (
        identifiers["DATA_SET_ID"] == "IUE-C-SWP-3-EDR-IUECDB-V1.0"
        and name == "QUALITY_IMAGE"
    ):
        return formats.iue.get_special_block(data, name)
    return False, None


def check_trivial_case(pointer: str, identifiers: DataIdentifiers, fn: str) -> bool:
    """
    Supplement generic definition of 'trivial' pointers. Intended primarily to
    preempt attempts to load known-unsupported data objects associated with
    otherwise-supported products. Called inline by `pointer_to_loader()`.
    """
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
    if identifiers["DATA_SET_ID"].startswith("ODY-M-THM-5") and (
        pointer in ("HEADER", "HISTORY")
    ):
        return formats.themis.trivial_themis_geo_loader(pointer)
    if re.match(
        r"CO-(CAL-ISS|[S/EVJ-]+ISSNA/ISSWA-2)", identifiers["DATA_SET_ID"]
    ):
        if pointer == "LINE_PREFIX_TABLE":
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
    if "MSL-M-SAM-" in identifiers["DATA_SET_ID"] and "FILE" in pointer:
        # reusing the msl_cmn special case for msl_sam 'FILE' pointers
        return formats.msl_cmn.trivial_header_loader()
    if (
        identifiers["INSTRUMENT_ID"] == "NIMS"
        and identifiers["SPACECRAFT_NAME"] == 'GALILEO_ORBITER'
        and pointer == "SAMPLE_SPECTRUM_QUBE"
    ):
        return formats.galileo.nims_sample_spectral_qube_trivial_loader()
    return False


def special_image_constants(identifiers: DataIdentifiers) -> dict[str, int]:
    """
    Defines 'secret' special constants for a dataset or product type. Called
    inline by `Data.find_special_constants()`.
    """
    consts = {}
    if identifiers["INSTRUMENT_ID"] == "CRISM":
        consts["NULL"] = 65535
    return consts


def check_special_fn(
    data: PDRLike, object_name: str, identifiers: DataIdentifiers
) -> tuple[bool, Optional[str]]:
    """
    Preempts generic filename specification. Called inline by
    `Data._object_to_filename()`.
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
    if identifiers["DATA_SET_ID"].startswith("CO-D-CDA") and (
        object_name == "TABLE"
    ):
        return formats.cassini.cda_table_filename(data)
    # THEMIS labels don't always mention when a file is stored gzipped
    if identifiers["INSTRUMENT_ID"] == "THEMIS":
        return formats.themis.check_gzip_fn(data, object_name)
    if (
        identifiers["DATA_SET_ID"]
        in (
            "NH-P-PEPSSI-4-PLASMA-V1.0",
            "NH-X-SWAP-5-DERIVED-SOLARWIND-V1.0",
            "NH-P/PSA-LORRI/ALICE/REX-5-ATMOS-V1.0",
        )
        and object_name == "SPREADSHEET"
    ):
        return formats.nh.get_fn(data)
    return False, None


def check_special_qube_band_storage(identifiers: DataIdentifiers):
    """
    Defines band storage types for QUBE procuts whose labels do not correctly
    specify them. Wraps `get_qube_band_storage_type()`.
    """
    if identifiers["INSTRUMENT_HOST_NAME"] == "CASSINI_ORBITER":
        return formats.cassini.get_special_qube_band_storage()
    return False, None


def check_special_fits_start_byte(
    identifiers: DataIdentifiers, name: str, hdulist: HDUList
) -> tuple[bool, Optional[int]]:
    """
    Preempts generic PDS3 data object -> FITS start byte mapping. Wraps
    `get_fits_start_byte()`.
    """
    if (
        identifiers["INSTRUMENT_HOST_NAME"] == "DAWN"
        and "FC2" in identifiers["DATA_SET_ID"]
        and name == "HISTORY"
    ):
        return True, formats.dawn.dawn_history_hdu_exception()
    if (
        identifiers["DATA_SET_ID"].startswith("HST-S-WFPC2-3-RPX")
        and "IMAGE" in name
    ):
        return True, formats.saturn_rpx.rpx_img_hdu_start_byte(name, hdulist)
    if (
        identifiers["INSTRUMENT_ID"] == "HRIV"
        and identifiers["PRODUCT_TYPE"] == "RADIANCE_DECONVOLVED"
        and name.startswith("EXT_MASK")
    ):
        return True, formats.epoxi.hriv_deconv_mask_start_byte(name, hdulist)
    if identifiers["DATA_SET_ID"].startswith("MSGR-H-MDIS-6-CAL"):
        return True, formats.galileo.mdis_fits_start_byte(name, hdulist)
    if identifiers["DATA_SET_ID"] == "MSSSO-J-CASPIR-3-RDR-SL9-STDS-V1.0":
        return True, formats.ground.mssso_cal_start_byte(name, hdulist)
    if "MEX-M-VMC-3-RDR" in identifiers["DATA_SET_ID"]:
        return True, formats.mex.vmc_rdr_hdu_selection(name, hdulist)
    if (
        identifiers["DATA_SET_ID"] == "LRO-L-LAMP-2-EDR-V1.0" 
        and "TABLE" in name
    ):
        return formats.lro.lamp_edr_hdu_exceptions(name, hdulist)
    if (
        identifiers["DATA_SET_ID"] == "LRO-L-LAMP-3-RDR-V1.0" 
    ):
        return formats.lro.lamp_rdr_hdu_start_byte(name, hdulist)
    return False, None
