def seis_table_loader(filepath, fmtdef_dt):
    """
    The Viking 2 seismometer tables have mangled labels. The raw data tables
    are variable length CSVs, and labels for the summary tables count column
    bytes wrong. Half the labels define columns that do not match the data.

    HITS
    * viking
        * seis_raw
        * seis_summary
    """
    import pandas as pd

    col_names = [c for c in fmtdef_dt[0].NAME if "PLACEHOLDER" not in c]
    filename = filepath.split("/")[-1]
    # The summary tables have miscounted bytes in their labels. The columns are
    # separated by whitespace, so can be read by read_csv() instead. Also, both
    # labels define a SEISMIC_TIME_SOLS column that doesn't exist in the data.
    if "summary" in filename.lower():
        table = pd.read_csv(filepath, header=None, sep=r"\s+")
        col_names.remove("SEISMIC_TIME_SOLS")
        if "event_wind_summary" in filename.lower():
            # event_wind_summary.tab has a column not included in the label. It
            # is listed in: https://pds-geosciences.wustl.edu/viking/vl2-m-seis-5-rdr-v1/vl_9020/document/vpds_event_winds_format.txt
            col_names.insert(7, "ORIGINAL_LINES_COUNT")
    # The raw event tables are variable-length CSVs. Their labels include a
    # SEISMIC_SOL column that doesn't exist in the data.
    elif "event" in filename.lower():
        table = pd.read_csv(filepath, header=None, sep=",")
        col_names.remove("SEISMIC_SOL")
    # The raw high-rate tables are variable-length CSVs. Their labels list the
    # correct number of columns.
    elif "high" in filename.lower():
        table = pd.read_csv(filepath, header=None, sep=",")
    else:
        raise ValueError("Unknown Viking 2 SEIS table format.")
    assert len(table.columns) == len(col_names), "mismatched column count"
    table.columns = col_names
    return table
