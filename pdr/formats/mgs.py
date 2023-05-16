import pdr.loaders.queries
from pdr.pd_utils import insert_sample_types_into_df


def get_structure(pointer, data):
    fmtdef = pdr.loaders.queries.read_table_structure(pointer)
    fmtdef.at[7, "BYTES"] = 2
    fmtdef[f'ROW_BYTES'] = data.metaget(pointer).get(f'ROW_BYTES')
    fmtdef, dt = insert_sample_types_into_df(fmtdef, data)
    return True, fmtdef, dt
