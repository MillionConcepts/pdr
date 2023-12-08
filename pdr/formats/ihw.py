def curve_table_loader(filename, fmtdef_dt):
    """ The labels do not always count column bytes correctly. """
    import pandas as pd
    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=None, delim_whitespace=True)
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table
