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

def pra_special_block(data, name, identifiers):
    """PRA Lowband RDRs: The Jupiter labels use the wrong START_BYTE for columns 
    in containers. The Saturn/Uranus/Neptune labels define columns with multiple 
    ITEMS, but ITEM_BYTES is missing and the BYTES value is wrong."""
    block = data.metablock_(name)
    if identifiers["DATA_SET_ID"] in ("VG2-S-PRA-3-RDR-LOWBAND-6SEC-V1.0",
                                      "VG2-N-PRA-3-RDR-LOWBAND-6SEC-V1.0",
                                      "VG2-U-PRA-3-RDR-LOWBAND-6SEC-V1.0"
                                      ):
      for item in iter(block.items()):
            if "COLUMN" in item and "SWEEP" in item[1]["NAME"]:
                item[1].add("ITEM_BYTES", 4) # The original BYTES value
                item[1]["BYTES"] = 284 # ITEM_BYTES * ITEMS
    elif identifiers["DATA_SET_ID"] == "VG2-J-PRA-3-RDR-LOWBAND-6SEC-V1.0":
        for item in iter(block["CONTAINER"].items()):
            if "COLUMN" in item:
                if item[1]["NAME"] == "STATUS_WORD":
                    item[1]["START_BYTE"] = 1
                if item[1]["NAME"] == "DATA_CHANNELS":
                    item[1]["START_BYTE"] = 5
    return True, block


def lecp_table_loader(filename, fmtdef_dt):
    """
    VG1 LECP Jupiter SUMM Sector tables reference a format file with incorrect
    START_BYTEs for columns within a CONTAINER. Columns are consistently
    separated by whitespace.
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=None, sep=r"\s+")
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table
