def edr_table_loader(filename, fmtdef_dt, block, start_byte):
    """
    The ROW_SUFFIX_BYTES are either miscounted by a few bytes, or we don't 
    handle them correctly. There appears to be a related issue with the tables' 
    start bytes as well. This special case bypasses both issues.

     HITS
    * msl_rems
        * edr_SP
    """
    import pandas as pd
    
    fmtdef, dt = fmtdef_dt

    # number of rows to skip (there are multiple table pointers per product)
    skips = int(start_byte / 399)
    table = pd.read_csv(filename, header=None, 
                        skiprows=skips,
                        nrows=block["ROWS"])

    col_names = [c for c in fmtdef_dt[0]['NAME'] if "PLACEHOLDER" not in c]
    assert len(table.columns) == len(col_names), "mismatched column count"
    table.columns = col_names
    return table

def edr_offset(data, name):
    """
    HITS:
    * msl_rems
        * edr_HSDEF
        # edr_HSREG
    """
    start_byte = data.metaget_("^"+name)[1] - 1
    return True, start_byte

def rdr_table_loader(filename, fmtdef_dt):
    """
    Missing values are variations of "UNK" and "NULL", which cause mixed dtype 
    warnings when using the default pd.read_csv() parameters. 

     HITS
    * msl_rems
        * rdr_rmd
        * rdr_rnv
        * rdr_rtl
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    
    missing_const = [' UNK', '    UNK', '     UNK', '      UNK',
                     '       UNK', '         UNK', 
                     '   NULL', '    NULL']
    table = pd.read_csv(filename, header=None,
                        na_values=missing_const)

    col_names = [c for c in fmtdef_dt[0]['NAME'] if "PLACEHOLDER" not in c]
    assert len(table.columns) == len(col_names), "mismatched column count"
    table.columns = col_names
    return table
