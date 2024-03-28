from pdr.loaders.queries import read_table_structure
from pdr.pd_utils import insert_sample_types_into_df

def elec_em6_structure(block, name, filename, data, identifiers):
    """ELEC EDR em6/TBL tables: All the START_BYTEs in TBL_0_STATE_DATA.FMT
    are off by 36 bytes."""
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    for line in range(0, len(fmtdef)):
        if fmtdef.at[line, "BLOCK_NAME"] == "TBL0 DATA":
            fmtdef.at[line, "START_BYTE"] -= 36
    
    return insert_sample_types_into_df(fmtdef, identifiers)

def afm_rdr_structure(block, name, filename, data, identifiers):
    """AFM RDR header tables: Several columns' NAME fields start with lowercase
    letters, which is_an_assignment_line() in /parselabel/pds3.py evaluates as
    NOT an assignment statement."""
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.insert(1, 'NAME', fmtdef.pop('NAME'))
    for line in range(0, len(fmtdef)):
        col_number_text = fmtdef.at[line, "COLUMN_NUMBER"]
        if (type(col_number_text) == str
            and "NAME" in col_number_text):
            fmtdef.at[line, "COLUMN_NUMBER"] = col_number_text.split("NAME = ")[0]
            fmtdef.at[line, "NAME"] = col_number_text.split("NAME = ")[1]
    return fmtdef, None

def afm_table_loader(filename, fmtdef_dt, name):
    """AFM RDR tables: Several labels miscount bytes somewhere in the tables"""
    import pandas as pd
    
    if "HEADER_TABLE" in name:
        num_rows_skipped = 0
        num_rows = 4
    elif name == "AFM_F_ERROR_TABLE":
        num_rows_skipped = 4
        num_rows = 512
    elif name == "AFM_F_HEIGHT_TABLE":
        num_rows_skipped = 516
        num_rows = 512
    elif name == "AFM_B_ERROR_TABLE":
        num_rows_skipped = 1028
        num_rows = 512
    elif name == "AFM_B_HEIGHT_TABLE":
        num_rows_skipped = 1540
        num_rows = 512
    table = pd.read_csv(
        filename,
        header=None,
        sep=",",
        skiprows=num_rows_skipped, nrows=num_rows
    )
    names = [c for c in fmtdef_dt[0]['NAME'] if "PLACEHOLDER" not in c]
    assert len(table.columns) == len(names), "mismatched column count"
    table.columns = names
    return table

def wcl_edr_special_block(data, name):
    """WCL EDR ema/emb/emc tables: the START_BYTE for columns 13 and 14 are
    off by 1 and 2 bytes respectively. (The em8/em9/emf tables are fine.)"""
    block = data.metablock_(name)
    
    for item in iter(block.items()):
        if "COLUMN" in item:
            if item[1]["COLUMN_NUMBER"] == 13:
                item[1]["START_BYTE"] -= 1
            if item[1]["COLUMN_NUMBER"] == 14:
                item[1]["START_BYTE"] -= 2
    return block

def wcl_rdr_offset(data, name):
    """WCL RDR CP/CV tables: in the labels, each pointer's start byte is
    missing '<BYTES>' even though the units are bytes rather than file_records.
    This doesn't fix the header table though, they still need attention."""
    target = data.metaget_("^"+name)
    start_byte = target[-1] - 1
    return True, start_byte

