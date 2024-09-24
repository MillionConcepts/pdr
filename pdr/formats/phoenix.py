from pdr.loaders.queries import read_table_structure, _extract_table_records
from pdr.loaders._helpers import count_from_bottom_of_file
from pdr.pd_utils import insert_sample_types_into_df, compute_offsets


def elec_em6_structure(block, name, filename, data, identifiers):
    """
    ELEC EDR em6/TBL tables: All the START_BYTEs in TBL_0_STATE_DATA.FMT
    are off by 36 bytes.

    HITS
    * phoenix
        * elec_edr (partial)
    """
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    for line in range(0, len(fmtdef)):
        if fmtdef.at[line, "BLOCK_NAME"] == "TBL0 DATA":
            fmtdef.at[line, "START_BYTE"] -= 36
    fmtdef = compute_offsets(fmtdef)
    return insert_sample_types_into_df(fmtdef, identifiers)


def afm_rdr_structure(block, name, filename, data, identifiers):
    """
    AFM RDR header tables: Several columns' NAME fields start with lowercase
    letters, which is_an_assignment_line() in /parselabel/pds3.py evaluates as
    NOT an assignment statement.

    HITS
    * phoenix
        * afm_rdr
    """
    fmtdef = read_table_structure(block, name, filename, data, identifiers)
    fmtdef.insert(1, 'NAME', fmtdef.pop('NAME'))
    for line in range(0, len(fmtdef)):
        col_number_text = fmtdef.at[line, "COLUMN_NUMBER"]
        if (
            isinstance(col_number_text, str)
            and "NAME" in col_number_text
        ):
            fmtdef.at[
                line, "COLUMN_NUMBER"
            ] = col_number_text.split("NAME = ")[0]
            fmtdef.at[line, "NAME"] = col_number_text.split("NAME = ")[1]
    return fmtdef, None


def afm_table_loader(filename, fmtdef_dt, name):
    """
    AFM RDR tables: Several labels miscount bytes somewhere in the tables

    HITS
    * phoenix
        * afm_rdr
    """
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


def phxao_header_position(identifiers, block, target, name, start_byte):
    """
    PHXAO tables: Some table headers have lost trailing whitespace
    assumed to be present by the label.  Treat as newline-delimited
    instead; the record count is correct.

    HITS
    * phoenix
       * atm_phxao
    """
    
    return {
        "as_rows": True,
        "start": 0,
        "length": _extract_table_records(block),
    }


def phxao_table_offset(filename, identifiers):
    """
    PHXAO tables: Some table headers have lost trailing whitespace
    assumed to be present by the label.  Recalculate the table offset
    assuming that the table itself is still fixed-width.

    HITS
    * phoenix
       * atm_phxao
    """
    
    rows = identifiers["ROWS"]
    row_bytes = identifiers["ROW_BYTES"]
    start_byte = count_from_bottom_of_file(
        filename, rows, row_bytes=row_bytes
    )
    return True, start_byte


def wcl_edr_special_block(data, name):
    """
    WCL EDR ema/emb/emc tables: the START_BYTE for columns 13 and 14 are
    off by 1 and 2 bytes respectively. (The em8/em9/emf tables are fine.)

    HITS
    * phoenix
        * wcl_edr (partial)
    """
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

def led_edr_structure(block, name, filename, data, identifiers):
    """
    TEGA_LED.FMT: the CONTAINER's REPETITIONS should be 1000, not 1010

    HITS
    * phoenix
        * lededr
    """
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    real_repetitions = 1000
    real_fmtdef_len = 5 + (real_repetitions * 3)
    fmtdef = fmtdef.iloc[0:real_fmtdef_len, :]

    for line in range(0, len(fmtdef)):
        if fmtdef.at[line, "BLOCK_NAME"] == "LED_RECORDS":
            fmtdef.at[line, "BLOCK_REPETITIONS"] = 1000

    fmtdef = compute_offsets(fmtdef)
    return insert_sample_types_into_df(fmtdef, identifiers)

def sc_rdr_structure(block, name, filename, data, identifiers):
    """
    TEGA_SCRDR.FMT: most of the START_BYTEs are off by 4 because column 2 
    ("TEGA_TIME") is actually 8 bytes, not 4

    HITS
    * phoenix
        * scrdr
    """
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    for line in range(0, len(fmtdef)):
        if fmtdef.at[line, "COLUMN_NUMBER"] == 2:
            fmtdef.at[line, "BYTES"] = 8
        if fmtdef.at[line, "COLUMN_NUMBER"] >= 3:
            fmtdef.at[line, "START_BYTE"] += 4
    
    fmtdef = compute_offsets(fmtdef)
    return insert_sample_types_into_df(fmtdef, identifiers)
