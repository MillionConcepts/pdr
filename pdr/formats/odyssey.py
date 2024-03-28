def map_table_loader(filename, fmtdef_dt):
    """A few products open fine from their labels, but most do not. Seems like
    a byte counting issue in the labels."""
    import pandas as pd
    names = [c for c in fmtdef_dt[0]['NAME'] if 'PLACEHOLDER' not in c]
    # Some tables use tabs as column deliminators, others use spaces.
    table = pd.read_csv(filename, header=None, delim_whitespace=True)
    assert len(table.columns) == len(names)
    table.columns = names
    return table
