from pdr.datatypes import sample_types
from pdr.loaders.queries import read_table_structure, check_array_for_subobject


def get_structure(block, name, filename, data, identifiers):
    """The "encounter data" tables miscount the last column's START_BYTE by 1"""
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )

    if "encounter data" in block['DESCRIPTION']:
        fmtdef.at[10, "START_BYTE"] = 62
    return fmtdef, None


def fix_array_structure(name, block, fn, data, identifiers):
    """"""
    if not block.get("INTERCHANGE_FORMAT") == "BINARY":
        return None, None
    has_sub = check_array_for_subobject(block)
    if not has_sub:
        dt = sample_types(block["DATA_TYPE"], block["BYTES"], True)
        return None, dt
    fmtdef = read_table_structure(block, name, fn, data, identifiers)
    fmtdef.loc[fmtdef['NAME'] == 'PLACEHOLDER_SPECTRUM', "AXIS_ITEMS"] = \
        (block.get("COLLECTION").get("BYTES") -
            (fmtdef[fmtdef['NAME'] == 'PLACEHOLDER_SPECTRUM']["START_BYTE"].values[0] - 1)) / \
        len(fmtdef.loc[fmtdef['BLOCK_NAME'].str.contains('SPECTRUM')].index)
    # Sometimes arrays define start_byte, sometimes their elements do
    if "START_BYTE" in fmtdef.columns:
        fmtdef['START_BYTE'].fillna(1, inplace=True)

    from pdr.pd_utils import insert_sample_types_into_df
    return insert_sample_types_into_df(fmtdef, identifiers)