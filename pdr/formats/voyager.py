def mag_special_block(data, name):
    """
    ROW_BYTES are listed as 144 in the labels for Uranus and Neptune MAG RDRs.
    Their tables look the same, but the Neptune products open wrong. Setting
    ROW_BYTES to 145 fixes it.

    HITS
    * vg_mag
        * rdr_nep
    """
    block = data.metablock_(name)
    block["ROW_BYTES"] = 145 
    return block


def get_structure(block, name, filename, data, identifiers):
    """
    The VGR_PLS_HR_2017.FMT for PLS 1-hour averages undercounts the last column
    by 1 byte.

    HITS
    * vg_pls
        * sys_1hr_avg (partial)
    """
    from pdr.loaders.queries import read_table_structure
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[8, "BYTES"] = 6
    return fmtdef, None


def pls_avg_special_block(data, name):
    """
    Because VGR_PLS_HR_2017.FMT undercounts by 1 byte, the products that
    reference it also undercount their ROW_BYTES by 1.

    HITS
    * vg_pls
        * sys_1hr_avg
    """
    block = data.metablock_(name)
    if block["^STRUCTURE"] == "VGR_PLS_HR_2017.FMT":
        block["ROW_BYTES"] = 57 
        return True, block
    return False, None


def pls_fine_special_block(data, name):
    """
    Most of the PLS FINE RES labels undercount the ROW_BYTES. The most recent
    product (2007-241_2018-309) is formatted differently and opens correctly.

    HITS
    * vg_pls
        * sys_fine_res
    """
    block = data.metablock_(name)
    if block["ROW_BYTES"] == 57:
        block["ROW_BYTES"] = 64 
        return True, block
    return False, None


def pls_ionbr_special_block(data, name):
    """
    SUMRY.LBL references the wrong format file

    HITS
    * vg_pls
        * ur_ionbr (partial)
    """
    block = data.metablock_(name)
    block["^STRUCTURE"] = "SUMRY.FMT" 
    return True, block


def pra_special_block(data, name, identifiers):
    """
    PRA Lowband RDRs: The Jupiter labels use the wrong START_BYTE for columns
    in containers. The Saturn/Uranus/Neptune labels define columns with
    multiple ITEMS, but ITEM_BYTES is missing and the BYTES value is wrong.

    HITS
    * vg_pra
        * lowband_jup
        * lowband_other
    """
    block = data.metablock_(name)
    if identifiers["DATA_SET_ID"] in (
        "VG2-S-PRA-3-RDR-LOWBAND-6SEC-V1.0",
        "VG2-N-PRA-3-RDR-LOWBAND-6SEC-V1.0",
        "VG2-U-PRA-3-RDR-LOWBAND-6SEC-V1.0"
    ):
        for item in iter(block.items()):
            if "COLUMN" in item and "SWEEP" in item[1]["NAME"]:
                item[1].add("ITEM_BYTES", 4)  # The original BYTES value
                item[1]["BYTES"] = 284  # ITEM_BYTES * ITEMS
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
    The VG2 Uranus 12.8 minute step table (ascii version) was missing values 
    from some rows, not sure why. Reusing this special case fixes it.

    HITS
    vg_lecp
        * j_summ_sector_vg1
        * u_rdr_step_12.8 (partial)
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=None, sep=r"\s+")

    col_names = [c for c in fmtdef_dt[0]['NAME'] if "PLACEHOLDER" not in c]
    assert len(table.columns) == len(col_names), "mismatched column count"
    table.columns = col_names
    return table

def lecp_vg1_sat_table_loader(filename, fmtdef_dt):
    """
    VG1 Saturn RDR step products have an extra header row partway through their 
    tables. This special case skips those rows by treating them as comments. 
    PDS volume affected: VG1-S-LECP-3-RDR-STEP-6MIN-V1.0

    HITS
    vg_lecp
        * s_rdr_step (partial)
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    # Rows that start with "VOYAGER" are extra headers. "comment='V'" skips them
    table = pd.read_csv(filename, comment='V')

    col_names = [c for c in fmtdef_dt[0]['NAME'] if "PLACEHOLDER" not in c]
    assert len(table.columns) == len(col_names), "mismatched column count"
    table.columns = col_names
    return table
