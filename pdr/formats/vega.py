import pdr.loaders.queries


def get_structure(block, name, filename, data, identifiers):
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    # The "encounter data" tables miscount the last column's START_BYTE by 1
    if "encounter data" in block['DESCRIPTION']:
        fmtdef.at[10, "START_BYTE"] = 62
    return fmtdef, None
