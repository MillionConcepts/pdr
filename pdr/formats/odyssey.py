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

def grs_e_kernel_loader(name, fn):
    """
    The GRS Experimenter's Notebook products have two "FILE" objects with one 
    "TIME_SERIES" pointer each. The first object/pointer is for the time series 
    table, the other is for a .TXT notes file. Because the text file's pointer 
    has "SERIES" in it, pointer_to_loader() sends it to ReadTable(). 

    This special case reads it with read_text() instead.

    HITS
    * mars_odyssey
        * edr_e_kernel
    """
    from pdr.loaders.text import read_text

    return True, read_text(name, fn)

def grs_e_kernel_structure():
    """
    Handles the same files as grs_e_kernel_loader() above, and is needed to 
    avoid an error thrown before that special case can be called. Because the 
    second TIME_SERIES pointer is not actually a table, parse_table_structure() 
    fails when trying to make a fmtdef.

    HITS
    * mars_odyssey
        * edr_e_kernel
    """
    return True, None

