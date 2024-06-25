def curve_table_loader(filename, fmtdef_dt):
    """
    The labels do not always count column bytes correctly.

    HITS
    * ihw_isrn
        * curve
    """
    import pandas as pd
    names = [c for c in fmtdef_dt[0].NAME if "PLACEHOLDER" not in c]
    table = pd.read_csv(filename, header=None, sep=r"\s+")
    assert len(table.columns) == len(names), "mismatched column count"
    table.columns = names
    return table


def add_newlines_table_loader(fmtdef_dt, block, filename, start_byte):
    """
    Some Halley V1.0 tables (MSN, PPN, and IRSN datasets) are missing
    newline characters between rows. (Also applies to some ICE ephemeris tables)

    HITS
    * ihw
        * ms_radar
        * ms_vis
    * ice
        * ephem_tbl
    """
    from io import StringIO
    import pandas as pd
    from pdr.utils import head_file

    with head_file(filename) as f:
        f.read(start_byte)
        newlines_added = bytearray()
        for row in range(0, block["ROWS"]):
            bytes_ = f.read(block["ROW_BYTES"])
            newlines_added += bytes_ + b"\n" # Add a newline to each row
    string_buffer = StringIO(newlines_added.decode())

    # Adapted from _interpret_as_ascii()
    fmtdef, dt = fmtdef_dt
    colspecs = []
    for record in fmtdef.to_dict("records"):
        col_length = int(record["BYTES"])
        colspecs.append((record["SB_OFFSET"], record["SB_OFFSET"] + col_length))
    string_buffer.seek(0)
    table = pd.read_fwf(string_buffer, header=None, colspecs=colspecs)
    string_buffer.close()
    table.columns = fmtdef.NAME.tolist()
    table = table.drop([k for k in table.keys() if "PLACEHOLDER" in k], axis=1)
    return table


def get_special_block(data, name):
    """
    A handful of MSN Radar tables have column names that were not reading
    correctly and were ending up as "NaN". Which also caused an AttributeError 
    when running ix check.

    HITS
    * ihw
        * ms_radar
    """
    block = data.metablock_(name)
    for item in iter(block.items()):
        if "COLUMN" in item:
            if item[1]["START_BYTE"] == 17 and "NAME" not in item[1]:
                item[1].add("NAME", ">=1SEC")
            if item[1]["START_BYTE"] == 21 and "NAME" not in item[1]:
                item[1].add("NAME", ">=8SEC")
    return block


def get_structure(block, name, filename, data, identifiers):
    """
    SSN products with a SPECTRUM pointer were opening with an incorrect
    column name.

    HITS
    * ihw
        * spec_hal_cal
    """
    from pdr.loaders.queries import read_table_structure
    from pdr.pd_utils import insert_sample_types_into_df
    
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[0, "NAME"] = fmtdef.at[0, "COLUMN_NAME"]
    
    fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt
