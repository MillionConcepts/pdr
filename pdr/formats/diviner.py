# because these can contain the value "NaN", combined with the fact that they
# are space-padded, pd.read_csv sometimes casts some columns to object,
# turning some of their values into strings and some into float, throwing
# warnings and making it obnoxious to work with them (users will randomly not
# be able to, e.g., add two columns together without a data cleaning step).
def diviner_l4_table_loader(fmtdef_dt, filename):
    """
    because these can contain the value "NaN", combined with the fact that they
    are space-padded, pd.read_csv sometimes casts some columns to object,
    turning some of their values into strings and some into float, throwing
    warnings and making it obnoxious to work with them (users will randomly not
    be able to, e.g., add two columns together without a data cleaning step).

    HITS
    * diviner
        * l4
    """
    import numpy as np
    import pandas as pd

    table = pd.DataFrame(
        np.loadtxt(filename, delimiter=",", skiprows=1),
        columns=[c for c in fmtdef_dt[0]["NAME"] if "PLACEHOLDER" not in c],
    )
    return table
