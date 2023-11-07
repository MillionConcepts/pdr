def mag_special_block(data, name):
    """ROW_BYTES are listed as 144 in the labels for Uranus and Neptune MAG RDRs.
    Their tables look the same, but the Neptune products open wrong. Setting
    ROW_BYTES to 145 fixes it."""
    block = data.metablock_(name)
    block["ROW_BYTES"] = 145 
    return block


def get_structure(block, name, filename, data, identifiers):
    """The VGR_PLS_HR_2017.FMT for PLS 1-hour averages undercounts the last
    column by 1 byte."""
    from pdr.loaders.queries import read_table_structure
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[8, "BYTES"] = 6
    return fmtdef, None


def pls_avg_special_block(data, name):
    """Because VGR_PLS_HR_2017.FMT undercounts by 1 byte, the products that
    reference it also undercount their ROW_BYTES by."""
    block = data.metablock_(name)
    if block["^STRUCTURE"] == "VGR_PLS_HR_2017.FMT":
        block["ROW_BYTES"] = 57 
        return True, block
    return False, None


def pls_fine_special_block(data, name):
    """Most of the PLS FINE RES labels undercount the ROW_BYES. The most recent
    product (2007-241_2018-309) is formatted differently and opens correctly."""
    block = data.metablock_(name)
    if block["ROW_BYTES"] == 57:
        block["ROW_BYTES"] = 64 
        return True, block
    return False, None


def pls_ionbr_special_block(data, name):
    """SUMRY.LBL references the wrong format file"""
    block = data.metablock_(name)
    block["^STRUCTURE"] = "SUMRY.FMT" 
    return True, block
