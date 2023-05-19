import warnings
from pathlib import Path

import os

import pdr.loaders.queries
from pdr.loaders.utility import tbd
from pdr.pd_utils import insert_sample_types_into_df
from pdr.loaders._helpers import _count_from_bottom_of_file, check_explicit_delimiter
from pdr.loaders.queries import table_position


def ppi_table_loader(data, pointer, data_set_id):

    def load_this_table(*_, **__):
        import pandas as pd

        if "UNCALIB" in data_set_id:
            return pd.read_csv(data.file_mapping[pointer])
        structure = pdr.loaders.queries.read_table_structure(pointer)
        names = structure.NAME
        header = None
        if "FULL" in data.file_mapping[pointer]:
            skiprows = 4
            if data_set_id == "CO-S-MIMI-4-CHEMS-CALIB-V1.0":
                header = 0
                names = None
                skiprows = range(1, 4)
        else:
            skiprows = 7
        table = pd.read_csv(data.file_mapping[pointer],
                            header=header,
                            skiprows=skiprows,
                            names=names)
        return table
    return load_this_table


def get_structure(block, name, filename, data):
    # the data type that goes here double defines the 32 byte prefix/offset.
    # By skipping the parse_table_structure we never add the prefix bytes so
    # it works as is. (added HUY if block after this comment)
    fmtdef = pdr.loaders.queries.read_table_structure(block, name, filename, data)
    if "HUY_DTWG_ENTRY_AERO" in data.filename:
        fmtdef.at[5, "NAME"] = "KNUDSEN FREESTR. HARD SPHERE NR. [=2.8351E-8/RHO]"
        fmtdef.at[6, "NAME"] = "KNUDSEN NR. [=1.2533*SQRT(2)*Ma/Re]"
        fmtdef.at[7, "NAME"] = "REYNOLD NR. [=RHO*VREL*D/Mu]"
        dt = None
        return fmtdef, dt
    fmtdef, dt = insert_sample_types_into_df(fmtdef, data)
    return fmtdef, dt


def looks_like_ascii(data, pointer):
    return (
        ("SPREADSHEET" in pointer)
        or ("ASCII" in pointer)
        or (data.metablock(pointer).get('INTERCHANGE_FORMAT') == 'ASCII')
    )


def get_position(identifiers, block, target, name, filename):
    if "IR_" in filename:
        tbd(name, block)
    table_props = table_position(identifiers, block, target, name, filename)
    n_records = identifiers["ROWS"]
    if any(sub in filename for sub in ["ULVS_DDP", "DLIS_AZ_DDP", "DLV_DDP"]):
        record_bytes = identifiers["ROW_BYTES"]
    else:
        record_bytes = identifiers["ROW_BYTES"]+1
    length = n_records * record_bytes
    if name == "HEADER":
        tab_size = length
        if isinstance(filename, list):
            filename = filename[0]
        file = Path(filename)
        file_size = os.path.getsize(file)
        length = file_size - tab_size
        start = 0
        table_props['start'] = start
    if name in ("TABLE", "HEADER"):
        table_props['length'] = length
        return True, table_props
    else:
        return False, None


def get_offset(filename, identifiers):
    if any(sub in filename for sub in ["ULVS_DDP", "DLIS_AZ_DDP", "DLV_DDP"]):
        row_bytes = identifiers["ROW_BYTES"]
    else:
        row_bytes = identifiers["ROW_BYTES"]+1
    rows = identifiers["ROWS"]
    start_byte = _count_from_bottom_of_file(filename, rows, row_bytes=row_bytes)
    return True, start_byte


def trivial_loader(pointer, data):
    warnings.warn(
        f"The Cassini ISS EDR/calibration {pointer} tables are not currently "
        f"supported."
    )
    return data.trivial


def cda_table_filename(data):
    label = Path(data.labelname)
    return True, Path(label.parent, f"{label.stem}.TAB")


# TODO: find a way to point find_special_constants at this so we can write
#  scaled versions of these images
def xdr_redirect_to_image_block(data):
    object_name = "IMAGE"
    block = data.metablock_(object_name)
    return block


def get_hasi_structure(block, name, filename, data):
    fmtdef = pdr.loaders.queries.read_table_structure(block, name, filename, data)
    dt = None
    fmtdef_dt = (fmtdef, dt)
    return fmtdef_dt


def get_special_qube_band_storage():
    band_storage_type = 'BAND_SEQUENTIAL'
    return True, band_storage_type
