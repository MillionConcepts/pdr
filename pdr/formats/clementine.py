import re

from pdr.pd_utils import insert_sample_types_into_df


def get_offset(data, pointer):
    start_row = int(re.split(r',|[(|)]', data.metadata[f'^{pointer}'])[2])
    return True, (start_row - 1) * data.metadata['RECORD_BYTES']


def get_fn(data, object_name):
    target = re.split(r',|[(|)]', data.metadata[f'^{object_name}'])[1]
    return True, target


def get_structure(pointer, data):
    fmtdef = data.read_table_structure(pointer)
    fmtdef.ITEM_OFFSET = 16
    fmtdef.ITEM_BYTES = 16
    fmtdef, dt = insert_sample_types_into_df(fmtdef, data)
    return True, fmtdef, dt
