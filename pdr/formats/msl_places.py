def spreadsheet_loader(filename, fmtdef_dt):
    """
    HITS
    * msl_places
        * localizations
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, sep=",")
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table
