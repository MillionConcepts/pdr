from pdr.pd_utils import insert_sample_types_into_df


def get_structure(pointer, data):
    fmtdef = data.read_table_structure(pointer)
    fmtdef.at[7, "BYTES"] = 2
    fmtdef[f'ROW_BYTES'] = data.metaget(pointer).get(f'ROW_BYTES')
    fmtdef, dt = insert_sample_types_into_df(fmtdef, data)
    return True, fmtdef, dt


def get_sample_type(sample_type, sample_bytes):
    if sample_type == "IEEE REAL":
        _float = "d" if sample_bytes == 8 else "f"
        return True, f">{_float}"
    return False, None
