from pdr.loaders.queries import read_table_structure


def get_odf_structure(block, name, filename, data, identifiers):
    """"""
    from pdr.pd_utils import insert_sample_types_into_df
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[7, "BYTES"] = 2
    fmtdef[f"ROW_BYTES"] = block.get(f"ROW_BYTES")

    fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt


def get_ecs_structure(block, name, filename, data, identifiers):
    """
    HITS
    * mgs_rss_raw
        * ecs
    """
    from pdr.pd_utils import insert_sample_types_into_df, compute_offsets
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[5, "START_BYTE"] = 80
    fmtdef[f"ROW_BYTES"] = block.get(f"ROW_BYTES")

    fmtdef = compute_offsets(fmtdef)
    fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt


def mola_pedr_special_block(data, name, identifiers):
    """
    Fix for FILE_RECORDS = "UNK" and ROWS = "UNK" in the MOLA PEDR labels.
    This special case calculates ROWS using the count_from_bottom_of_file()
    logic in reverse.

    HITS
    * mgs_mola
        * pedr
    * mgs_sampler
        * pedr
    """
    import os
    from pathlib import Path
    from pdr.loaders.queries import data_start_byte

    block = data.metablock_(name)
    target = data.metaget_("^"+name)
    start_byte = data_start_byte(identifiers, block, target, data.filename)

    table_bytes = os.path.getsize(Path(data.filename)) - start_byte
    block["ROWS"] = int(table_bytes / block["ROW_BYTES"])

    return block
