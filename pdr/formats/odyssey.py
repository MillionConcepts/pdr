def map_table_loader(filename, fmtdef_dt):
    """
    A few products open fine from their labels, but most do not. Seems like
    a byte counting issue in the labels.

    HITS
    * mars_odyssey
        * maps
    """
    import pandas as pd
    names = [c for c in fmtdef_dt[0]['NAME'] if 'PLACEHOLDER' not in c]
    # Some tables use tabs as column delimiters, others use spaces.
    table = pd.read_csv(filename, header=None, sep=r"\s+")
    assert len(table.columns) == len(names), "Mismatched column count"
    table.columns = names
    return table
