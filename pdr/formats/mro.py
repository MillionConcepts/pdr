from io import StringIO

from pdr.loaders.queries import read_table_structure
from pdr.utils import head_file


def get_structure(block, name, filename, data, identifiers):
    """
    The first column in the MCS (EDR/RDR/DDR) format files are just named "1"
    which is being read as 'int'. This was causing problems in read_table
    during the table.drop call

    HITS
    * mro
        * mcs_edr
        * mcs_rdr
    """
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef["NAME"] = fmtdef["NAME"].values.astype(str)
    return fmtdef, None


def mcs_ddr_table_loader(fmtdef_dt, block, filename, start_byte):
    """Reads each row of the table and removes extra newline characters.
    Adapted from _interpret_as_ascii()."""
    with head_file(filename) as f:
        f.read(start_byte)
        newlines_removed = bytearray()
        for row in range(0, block["ROWS"]):
            bytes_ = f.read(block["ROW_BYTES"])
            newlines_removed += bytes_.replace(b"\n", b"") + b"\n"
    string_buffer = StringIO(newlines_removed.decode())
    import pandas as pd
    from pdr.pd_utils import compute_offsets

    # Adapted from _interpret_as_ascii()
    fmtdef, dt = fmtdef_dt
    colspecs = []
    position_records = compute_offsets(fmtdef).to_dict("records")
    for record in position_records:
        col_length = record["BYTES"]
        colspecs.append((record["SB_OFFSET"], record["SB_OFFSET"] + col_length))
    string_buffer.seek(0)
    table = pd.read_fwf(string_buffer, header=None, colspecs=colspecs)
    string_buffer.close()

    table.columns = fmtdef.NAME.tolist()
    return table

def crism_mrdr_ancill_position(identifiers, block, target, name, start_byte):
    """
    ROW_BYTES = 14 in the labels, but it should be 16 (the RECORD_BYTES)

    HITS
    * crism
        * ancil_mrdr
    """
    from pdr.loaders.queries import table_position
    
    table_props = table_position(identifiers, block, target, name, start_byte)
    n_rows = block["ROWS"]
    row_bytes = identifiers["RECORD_BYTES"]
    table_props["length"] = n_rows * row_bytes
    return table_props

