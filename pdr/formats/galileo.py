import warnings

import pdr.loaders.queries


def mdis_hdu_name(name):
    """the MDIS cal labels do not include file size information."""
    if name in ("IMAGE", "HEADER"):
        return 0
    raise NotImplementedError("Unknown MDIS extension name")


def galileo_table_loader():
    warnings.warn("Galileo EDR binary tables are not yet supported.")
    return True


def ssi_cubes_header_loader():
    # The Ida and Gaspra cubes have HEADER pointers but no defined HEADER
    # objects
    return True


def nims_edr_sample_type(base_samp_info):
    from pdr.datatypes import sample_types

    # Each time byte order is specified for these products it is LSB, so this
    # assumes BIT_STRING refers to LSB_BIT_STRING
    sample_type = base_samp_info["SAMPLE_TYPE"]
    sample_bytes = base_samp_info["BYTES_PER_PIXEL"]
    if "BIT_STRING" == sample_type:
        sample_type = "LSB_BIT_STRING"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    if "N/A" in sample_type:
        sample_type = "CHARACTER"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    return False, None


def probe_structure(block, name, filename, data, identifiers):
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    # Several NMS products have an incorrect BYTES value in one column
    if fmtdef.at[1, "NAME"] == "COUNTS":
        fmtdef.at[1, "BYTES"] = 8
    # One ASI product has incorrect BYTES values in multiple columns
    elif identifiers["PRODUCT_ID"] == "HK01AD.TAB":
        fmtdef.at[1, "BYTES"] = 4
        fmtdef.at[3, "BYTES"] = 2
        fmtdef.at[5, "BYTES"] = 2
    return fmtdef, None


def epd_special_block(data, name):
    # All 'E1' EPD SUMM products incorrectly say ROW_BYTES = 90; changing them
    # to the RECORD_BYTES values.
    block = data.metablock_(name)
    block["ROW_BYTES"] = data.metaget_("RECORD_BYTES")
    return block


def epd_structure(block, name, filename, data, identifiers):
    # E1PAD_7.TAB has an extra/unaccounted for byte at the start of each row
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    for row in range(0, 9):
        fmtdef.at[row, "START_BYTE"] += 1
    return fmtdef, None


def pws_special_block(data, name):
    # The PWS SUMM products sometimes undercount ROW_BYTES by 2
    block = data.metablock_(name)
    product_id = data.metaget_("PRODUCT_ID")
    if "B.TAB" in product_id:
        block["ROW_BYTES"] = 366
    if "E.TAB" in product_id:
        block["ROW_BYTES"] = 516
    return block


def pws_table_loader(filename, fmtdef_dt):
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=1, sep=";")
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table
