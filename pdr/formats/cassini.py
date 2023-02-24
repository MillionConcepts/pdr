import warnings
from pathlib import Path

import os

from pdr.pd_utils import insert_sample_types_into_df


def ppi_table_loader(data, pointer, data_set_id):

    def load_this_table(*_, **__):
        import pandas as pd

        if "UNCALIB" in data_set_id:
            return pd.read_csv(data.file_mapping[pointer])
        structure = data.read_table_structure(pointer)
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


def get_structure(pointer, data):
    # the data type that goes here double defines the 32 byte prefix/offset.
    # By skipping the parse_table_structure we never add the prefix bytes so
    # it works as is.
    fmtdef = data.read_table_structure(pointer)
    fmtdef, dt = insert_sample_types_into_df(fmtdef, data)
    return True, fmtdef, dt


def looks_like_ascii(data, pointer):
    return (
        ("SPREADSHEET" in pointer)
        or ("ASCII" in pointer)
        or (data.metablock(pointer).get('INTERCHANGE_FORMAT') == 'ASCII')
    )


def get_position(start, length, as_rows, data, object_name):
    n_records = data.metaget_("ROWS")
    if "ULVS_DDP" in data.filename or "DLIS_AZ_DDP" in data.filename \
            or "DLV_DDP" in data.filename:
        record_bytes = data.metaget_("ROW_BYTES")
    else:
        record_bytes = data.metaget_("ROW_BYTES")+1
    length = n_records * record_bytes
    if object_name == "TABLE":
        return True, start, length, as_rows
    elif object_name == "HEADER":
        tab_size = length
        filename = data._object_to_filename(object_name)
        if isinstance(filename, list):
            filename = filename[0]
        file = Path(filename)
        file_size = os.path.getsize(file)
        length = file_size - tab_size
        start = 0
        return True, start, length, as_rows
    else:
        return False, None, None, None


def get_offset(data, pointer):
    if "ULVS_DDP" in data.filename or "DLIS_AZ_DDP" in data.filename \
            or "DLV_DDP" in data.filename:
        row_bytes = data.metaget_("ROW_BYTES")
    else:
        row_bytes = data.metaget_("ROW_BYTES")+1
    start_byte = data._count_from_bottom_of_file(pointer, row_bytes=row_bytes)
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
