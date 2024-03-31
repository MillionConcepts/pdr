import pdr.loaders.queries


def get_odf_structure(block, name, filename, data, identifiers):
    """"""
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[7, "BYTES"] = 2
    fmtdef[f"ROW_BYTES"] = block.get(f"ROW_BYTES")
    from pdr.pd_utils import insert_sample_types_into_df

    fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt


def get_ecs_structure(block, name, filename, data, identifiers):
    """
    HITS
    * mgs_rss_raw
        * ecs
    """
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[5, "START_BYTE"] = 80
    fmtdef[f"ROW_BYTES"] = block.get(f"ROW_BYTES")
    from pdr.pd_utils import insert_sample_types_into_df, compute_offsets

    fmtdef = compute_offsets(fmtdef)
    fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt
