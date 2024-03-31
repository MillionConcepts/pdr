def rss_spreadsheet_loader(filename, fmtdef_dt):
    """
    The RSS UHFD labels have the wrong ROWS value for most products.

    HITS
    * mer_rss
        *uhfd
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=None, sep=",")
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table
