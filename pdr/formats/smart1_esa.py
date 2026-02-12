

def spede_plasma40_table_reader(fn):
    """
    These are delimited .tab files with a few extra commas between some
    columns, creating more columns than column names in the format file.

    HITS
    * esa_smart
        * SPEDE_REFDR_SW_PD_40
        * SPEDE_REFDR_LEOP_CAL_PD_40
        * SPEDE_REFDR_EP_MONITOR_PD_40
        * SPEDE_REFDR_BKGRPLASMA_PD_40
    """
    import pandas as pd

    # col names from plasma 40 fmt file, if you don't have the file
    # that's ok because you don't need it with this:
    base_cols = [
        "DATE",
        "JULIAN_DATE",
        "SHADOW",
        "SC_MX_SUN_ANGLE",
        "SC_MY_SUN_ANGLE",
        "SC_MZ_SUN_ANGLE",
        "SC_SA_ANGLE",
        "GSE_X",
        "GSE_Y",
        "GSE_Z",
        "LSE_X",
        "LSE_Y",
        "LSE_Z",
        "TIME_INCREMENT",
    ]
    groups = {
        "BIAS": 40,
        "MEASUREMENT": 40,
        "FLAGS": 40,
    }
    group_cols = []
    for name, n in groups.items():
        group_cols.extend([f"{name}_{i + 0:02d}" for i in range(n)])
    cols = base_cols + group_cols

    # there are both , and ,, in the file, so we allow any # of commas as a
    # delimiter
    df = pd.read_csv(fn, sep=r",+", engine="python", skipinitialspace=True,
                     skiprows=64, names=cols)

    return df

