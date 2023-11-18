import pdr.loaders.queries


def get_structure(block, name, filename, data, identifiers):
    """"""
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[7, "BYTES"] = 2
    fmtdef[f"ROW_BYTES"] = block.get(f"ROW_BYTES")
    from pdr.pd_utils import insert_sample_types_into_df

    fmtdef, dt = insert_sample_types_into_df(fmtdef, data)
    return fmtdef, dt
