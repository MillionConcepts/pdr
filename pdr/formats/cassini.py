import warnings
from pathlib import Path

import os

import pdr.loaders.queries
from pdr.loaders.utility import tbd
from pdr.loaders._helpers import count_from_bottom_of_file
from pdr.loaders.queries import table_position


def spreadsheet_loader(filename, fmtdef_dt, data_set_id):
    """
    HITS:
    * cassini_mimi
        * edr_lemms (partial)
        * rdr_chems_avg
        * rdr_chems_fullres
        * rdr_inca
        * rdr_lemms_avg
        * rdr_lemms_fullres
    * cassini_radar
        * asum
    * cassini_rpws
        * refdr_wbr
        * refdr_wfr
    """
    import pandas as pd

    if "UNCALIB" in data_set_id:
        return pd.read_csv(filename)
    fmtdef, dt = fmtdef_dt
    names = fmtdef.NAME
    header = None
    if "FULL" in filename:
        skiprows = 4
        if data_set_id == "CO-S-MIMI-4-CHEMS-CALIB-V1.0":
            header = 0
            names = None
            skiprows = range(1, 4)
    elif data_set_id == "CO-SSA-RADAR-3-ABDR-SUMMARY-V1.0":
        skiprows = 0
    else:
        skiprows = 7
    table = pd.read_csv(
        filename, header=header, skiprows=skiprows, names=names
    )
    return table


def get_structure(block, name, filename, data, identifiers):
    """
    the data type that goes here double defines the 32 byte prefix/offset.
    By skipping the parse_table_structure we never add the prefix bytes so
    it works as is.

    HITS:
    * cassini_hp
        * hasi_acc
        * hasi_ppi
        * hasi_pwa
        * hasi_tem
        * hasi_dpu
        * hasi_prof
    """
    # (added HASI/HUY if block after this comment)
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    if ("HASI" in filename) or ("HUY_DTWG_ENTRY_AERO" in filename):
        if "HUY_DTWG_ENTRY_AERO" in filename:
            fmtdef.at[
                5, "NAME"
            ] = "KNUDSEN FREESTR. HARD SPHERE NR. [=2.8351E-8/RHO]"
            fmtdef.at[6, "NAME"] = "KNUDSEN NR. [=1.2533*SQRT(2)*Ma/Re]"
            fmtdef.at[7, "NAME"] = "REYNOLD NR. [=RHO*VREL*D/Mu]"
        dt = None
    else:
        from pdr.pd_utils import insert_sample_types_into_df, compute_offsets

        fmtdef = compute_offsets(fmtdef)
        fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt


def looks_like_ascii(data, pointer):
    """"""
    return (
        ("SPREADSHEET" in pointer)
        or ("ASCII" in pointer)
        or (data.metablock(pointer).get("INTERCHANGE_FORMAT") == "ASCII")
    )


def get_position(identifiers, block, target, name, filename, start_byte):
    """
    HITS:
    * cassini_hp
        * dark
        * ddr
        * misc_img_text
        * img_table
        * strip
        * solar
        * sun
        * time
        * vis_extra
        * vis
    """
    if "IR_" in filename:
        tbd(name, block)
    table_props = table_position(identifiers, block, target, name, start_byte)
    n_records = identifiers["ROWS"]
    if any(sub in filename for sub in ["ULVS_DDP", "DLIS_AZ_DDP", "DLV_DDP"]):
        record_bytes = identifiers["ROW_BYTES"]
    else:
        record_bytes = identifiers["ROW_BYTES"] + 1
    length = n_records * record_bytes
    if name == "HEADER":
        tab_size = length
        if isinstance(filename, list):
            filename = filename[0]
        file = Path(filename)
        file_size = os.path.getsize(file)
        length = file_size - tab_size
        start = 0
        table_props["start"] = start
    table_props["length"] = length
    return table_props


def get_offset(filename, identifiers):
    """
    HITS:
    * cassini_hp
        * ddr
        * img_table
        * strip
        * solar
        * sun
        * time
        * vis
    """
    if any(sub in filename for sub in ["ULVS_DDP", "DLIS_AZ_DDP", "DLV_DDP"]):
        row_bytes = identifiers["ROW_BYTES"]
    else:
        row_bytes = identifiers["ROW_BYTES"] + 1
    rows = identifiers["ROWS"]
    start_byte = count_from_bottom_of_file(
        filename, rows, row_bytes=row_bytes
    )
    return True, start_byte


def trivial_loader(pointer):
    """
    HITS
    * cassini_iss
        * calib
        * edr_evj
        * edr_sat
    """
    warnings.warn(
        f"The Cassini ISS EDR/calibration {pointer} tables are not currently "
        f"supported."
    )
    return True


def cda_table_filename(data):
    """
    HITS:
    * cassini_cda
        * cda_area
        * cda_stat
        * cda_events
        * cda_spectra
        * cda_settings
        * cda_counter
        * cda_signals
    """
    label = Path(data.labelname)
    return True, Path(label.parent, f"{label.stem}.TAB")


# TODO: find a way to point find_special_constants at this so we can write
#  scaled versions of these images
def xdr_redirect_to_image_block(data):
    """
    HITS:
    * cassini_hp
        * img_xdr
    """
    object_name = "IMAGE"
    block = data.metablock_(object_name)
    return block


def get_special_qube_band_storage():
    """
    HITS:
    * cassini_uvis
        * fuv
        * euv
    """
    band_storage_type = "BAND_SEQUENTIAL"
    return True, band_storage_type


def iss_telemetry_bit_col_format(obj, definition):
    """
    The format file for Cassini ISS telemetry tables incorrectly uses 
    BIT_DATA_TYPE instead of DATA_TYPE when defining its top-level COLUMN 
    (causing a key error in add_bit_column_info()). It also says the data type 
    is BINARY instead of (presumably) MSB_BIT_STRING. 

    HITS:
    * cassini_iss
        * calib
        * calib_atm
        * edr_evj
        * edr_sat
    """
    # modify and return `obj`
    obj["DATA_TYPE"] = "MSB_BIT_STRING"
    # may as well fix it in `definition` too
    definition["DATA_TYPE"] = "MSB_BIT_STRING"

    return True, obj


def iss_calib_da_special_block(data, name):
    """
    The labels for some Cassini ISS calibration images with a .DA filename 
    extension incorrectly use ROW_PREFIX_BYTES.

    HITS
    * cassini_iss
        * calib_da
    """
    block = data.metablock_(name)
    if "LINE_PREFIX_BYTES" in block:
        del block["LINE_PREFIX_BYTES"]
        return True, block
    return False, block
