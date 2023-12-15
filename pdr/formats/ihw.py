def curve_table_loader(filename, fmtdef_dt):
    """ The labels do not always count column bytes correctly. """
    import pandas as pd
    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=None, delim_whitespace=True)
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table

def add_newlines_table_loader(fmtdef_dt, block, filename, start_byte):
    """ Some Halley V1.0 tables (MSN, PPN, and IRSN datasets) are missing 
    newline characters between rows. """
    from io import StringIO
    from pdr.utils import head_file
    from pdr.pd_utils import compute_offsets
    import pandas as pd
    
    with head_file(filename) as f:
        f.read(start_byte)
        newlines_added = bytearray()
        for row in range(0, block["ROWS"]):
            bytes_ = f.read(block["ROW_BYTES"])
            newlines_added += bytes_ + b"\n" #Adds a newline at the end of the row
    string_buffer = StringIO(newlines_added.decode())

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

def get_special_block(data, name):
    """A handful of MSN Radar tables have column names that were not reading 
    correctly and were ending up as "NaN". Which also caused an AttributeError 
    when running ix check."""
    block = data.metablock_(name)
    for item in iter(block.items()):
        if "COLUMN" in item:
            if item[1]["START_BYTE"] == 17 and "NAME" not in item[1]:
                item[1].add("NAME", ">=1SEC")
            if item[1]["START_BYTE"] == 21 and "NAME" not in item[1]:
                item[1].add("NAME", ">=8SEC")
    return block
