
def ancillary_table_loader(fn, fmtdef_dt):
    """
    The OUTAGES.TAB tables were being read as comma separated, which would be 
    fine except they have a missing comma between columns somewhere around row 
    300 that causes that row to read wrong

    HITS
    * lunar_prospector
        * er_ancillary (partial)
        * mag_ancillary (partial)
        * eng_ancillary
    """
    from pdr.utils import decompress
    from io import StringIO
    from pdr.loaders.table import _read_fwf_with_colspecs

    with decompress(fn) as f:
        stringbuf = StringIO(f.read().decode())
    stringbuf.seek(0)

    fmtdef, dt = fmtdef_dt
    table = _read_fwf_with_colspecs(fmtdef, stringbuf)

    table = table.iloc[:, 0:6]
    table.columns = [
        f for f in fmtdef['NAME'] if not f.startswith('PLACEHOLDER')
    ]
    return table
