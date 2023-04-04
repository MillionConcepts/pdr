import warnings
from pathlib import Path

import os
import re

from pdr.pd_utils import insert_sample_types_into_df
from pdr.datatypes import sample_types


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
    # it works as is. (added HUY if block after this comment)
    fmtdef = data.read_table_structure(pointer)
    if "HUY_DTWG_ENTRY_AERO" in data.filename:
        fmtdef.at[5, "NAME"] = "KNUDSEN FREESTR. HARD SPHERE NR. [=2.8351E-8/RHO]"
        fmtdef.at[6, "NAME"] = "KNUDSEN NR. [=1.2533*SQRT(2)*Ma/Re]"
        fmtdef.at[7, "NAME"] = "REYNOLD NR. [=RHO*VREL*D/Mu]"
        dt = None
        return True, fmtdef, dt
    fmtdef, dt = insert_sample_types_into_df(fmtdef, data)
    return True, fmtdef, dt


def looks_like_ascii(data, pointer):
    return (
        ("SPREADSHEET" in pointer)
        or ("ASCII" in pointer)
        or (data.metablock(pointer).get('INTERCHANGE_FORMAT') == 'ASCII')
    )


def get_position(start, length, as_rows, data, object_name):
    if "IR_" in data.filename:
        data.tbd(object_name)
    n_records = data.metaget_("ROWS")
    if any(sub in data.filename for sub in ["ULVS_DDP", "DLIS_AZ_DDP", "DLV_DDP"]):
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
    if any(sub in data.filename for sub in ["ULVS_DDP", "DLIS_AZ_DDP", "DLV_DDP"]):
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


# TODO: find a way to point find_special_constants at this so we can write
#  scaled versions of these images
def xdr_loader(pointer, data):
    def read_xdr_image(*_, **__):
        object_name = "IMAGE"
        block = data.metablock_(object_name)
        props = {"BYTES_PER_PIXEL": int(block["SAMPLE_BITS"] / 8)}
        props["sample_type"] = sample_types(
                block["SAMPLE_TYPE"], props["BYTES_PER_PIXEL"], for_numpy=True
            )
        props["nrows"] = block["LINES"]
        props["ncols"] = block["LINE_SAMPLES"]
        props |= {'rowpad': 0, 'colpad': 0, 'bandpad': 0, 'linepad': 0}
        props["nbands"] = 1
        props["band_storage_type"] = None
        props["pixels"] = props['nrows'] * props['ncols'] * props['nbands']
        props["start_byte"] = 0
        return data.read_image(object_name=pointer, special_properties=props)
    return read_xdr_image


def hasi_loader(pointer, data):
    def read_hasi_table(*_, **__):
        fn = data.file_mapping[pointer]
        fmtdef = data.read_table_structure(pointer)
        import pandas as pd
        return pd.read_csv(fn, sep=";", header=None, names=fmtdef["NAME"])
    return read_hasi_table


def get_special_qube_props(block):
    props = {}
    props["BYTES_PER_PIXEL"] = int(block["CORE_ITEM_BYTES"])  # / 8)
    props["sample_type"] = sample_types(
        block["CORE_ITEM_TYPE"], props["BYTES_PER_PIXEL"]
    )
    axnames = block.get('AXIS_NAME')
    props['axnames'] = tuple(re.sub(r'[)( ]', '', axnames).split(","))
    ax_map = {'LINE': 'nrows', 'SAMPLE': 'ncols', 'BAND': 'nbands'}
    for ax, count in zip(props['axnames'], block['CORE_ITEMS']):
        props[ax_map[ax]] = count
    props['band_storage_type'] = 'BAND_SEQUENTIAL'
    #props |= extract_axplane_metadata(use_block, props)
    # TODO: unclear whether lower-level linefixes ever appear on qubes
    return True, props, block #props | extract_linefix_metadata(use_block, props)

def radar_asum_loader(pointer, data):
    def read_asum_table(*_, **__):
        fmtdef = data.read_table_structure(pointer)
        import pandas as pd
        return pd.read_csv(data.file_mapping[pointer], sep=",", header=None, names=fmtdef["NAME"])
    return read_asum_table
