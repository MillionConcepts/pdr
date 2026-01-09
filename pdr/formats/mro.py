from io import StringIO

from pdr.loaders.queries import read_table_structure
from pdr.utils import head_file


def get_structure(block, name, filename, data, identifiers):
    """
    The first column in the MCS (EDR/RDR/DDR) format files are just named "1"
    which is being read as 'int'. This was causing problems in read_table
    during the table.drop call

    HITS
    * mro
        * mcs_edr
        * mcs_rdr
    """
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef["NAME"] = fmtdef["NAME"].values.astype(str)
    return fmtdef, None


def mcs_ddr_oldformat_trivial():
    """
    These files are outdated and have formatting issues that make the current
    table reader (mcs_ddr_table_loader below) not work.

    HITS:
    * mro
        * mcs_ddr_v1
    """
    import warnings
    warnings.warn('The V1.0 MRO MCS DDR tables (from MCSDDRV1) are not '
                  'supported by PDR, use a more recent version of the DDR'
                  ' Tables on the PDS.')
    return True


def mcs_ddr_table_loader(block, filename, start_byte):
    """
    The newer (V6.0 and above) DDR files can be opened into a dataframe with
    some massaging. The dataset records have a metadata block (described by
    MCS_DDR1.FMT) followed by 105 lines of data (each described by
    MCS_DDR2.FMT, the 105 is "repetitions" in the label). This continues until
    the end of the file.

    For the purposes of outputting a single table, the metadata block info is
    added to each row of 105 data rows that follow it. So per record block, 105
    lines are added to the dataframe. This is because the metadata and data
    rows have different columns, so they can't be in the same table as
    alternating rows as in the .tab file structure.

    HITS:
    * mro
        * mcs_ddr
    """
    import numpy as np
    import pandas as pd
    import warnings

    # Combined column and dtypes as described in the two format files
    # "QUAL" was called "1" but that is confusing and not meaningful re: how
    # the format label described it.
    columns = [
        "QUAL", "DATE", "UTC", "SCLK", "L_S", "SOLAR_DIST", "ORB_NUM", "GQUAL",
        "SOLAR_LAT", "SOLAR_LON", "SOLAR_ZEN", "LTST", "PROFILE_LAT",
        "PROFILE_LON", "PROFILE_RAD", "PROFILE_ALT", "LIMB_ANG", "ARE_RAD",
        "SURF_LAT", "SURF_LON", "SURF_RAD", "T_SURF", "T_SURF_ERR",
        "T_NEAR_SURF", "T_NEAR_SURF_ERR", "DUST_COLUMN", "DUST_COLUMN_ERR",
        "H2OVAP_COLUMN", "H2OVAP_COLUMN_ERR", "H2OICE_COLUMN",
        "H2OICE_COLUMN_ERR", "CO2ICE_COLUMN", "CO2ICE_COLUMN_ERR", "P_SURF",
        "P_SURF_ERR", "P_RET_ALT", "P_RET", "P_RET_ERR", "RQUAL", "P_QUAL",
        "T_QUAL", "DUST_QUAL", "H2OVAP_QUAL", "H2OICE_QUAL", "CO2ICE_QUAL",
        "SURF_QUAL", "OBS_QUAL", "REF_SCLK_0", "REF_SCLK_1", "REF_SCLK_2",
        "REF_SCLK_3", "REF_SCLK_4", "REF_SCLK_5", "REF_SCLK_6", "REF_SCLK_7",
        "REF_SCLK_8", "REF_SCLK_9", "REF_DATE_0", "REF_UTC_0", "REF_DATE_1",
        "REF_UTC_1", "REF_DATE_2", "REF_UTC_2", "REF_DATE_3", "REF_UTC_3",
        "REF_DATE_4", "REF_UTC_4", "REF_DATE_5", "REF_UTC_5", "REF_DATE_6",
        "REF_UTC_6", "REF_DATE_7", "REF_UTC_7", "REF_DATE_8", "REF_UTC_8",
        "REF_DATE_9", "REF_UTC_9","1_layer", "PRES", "T", "T_ERR", "DUST",
        "DUST_ERR", "H2OVAP", "H2OVAP_ERR", "H2OICE", "H2OICE_ERR", "CO2ICE",
        "CO2ICE_ERR", "ALT", "LAT", "LON"
    ]
    dtypes = [
        "string", "string", "string", "float64", "float64", "float64",
        "Int64", "Int64", "float64", "float64", "float64", "float64",
        "float64", "float64", "float64", "float64", "float64", "float64",
        "float64", "float64", "float64", "float64", "float64", "float64",
        "float64", "float64", "float64", "float64", "float64", "float64",
        "float64", "float64", "float64", "float64", "float64", "float64",
        "float64", "float64", "Int64", "Int64", "Int64", "Int64", "Int64",
        "Int64", "Int64", "float64", "float64", "float64", "float64",
        "float64", "float64", "float64", "float64", "float64", "float64",
        "float64", "string", "string", "string", "string", "string",
        "string", "string", "string", "string", "string", "string", "string",
        "string", "string", "string", "string", "string", "string", "string",
        "string", "string", "string", "float64", "float64", "float64",
        "float64", "float64", "float64", "float64","float64", "float64",
        "float64", "float64", "float64", "float64", "float64"
    ]
    dtype_map = dict(zip(columns, dtypes))
    block_size = block['CONTAINER']['REPETITIONS']  # data rows per record

    with open(filename, "rb") as f:
        f.seek(start_byte)
        data = f.read()
    # record and metadata rows are divided by new line
    rows = [row.decode("ascii", errors="replace") for row in data.split(b"\n")]
    combined_rows = []
    i = 0
    while i < len(rows) - 1:
        # there are also random huge spaces between each record block. we strip
        # those out, along with extra quotation marks
        meta_fields = [f.strip().strip('"').strip('             ') for f in
                       rows[i].split(",")]
        if len(meta_fields) != 77:
            # standard length of a metadata row
            print(meta_fields)
            warnings.warn("Metadata block missing from expected location in "
                          "the DDR file.")
            raise TypeError("Expected metadata row not found")
        i += 1
        for r in rows[i: i + block_size]:
            # iterate all data rows after each metadata block, add metadata
            # info to each data row
            data_fields = [f.strip().strip('"').strip('             ') for f in
                           r.split(",")]
            if len(data_fields) != 15:
                # standard length of a data row
                warnings.warn("DDR file has incomplete record blocks. "
                              "Searching for next metadata block.")
                i -= 1
                continue
            combined_rows.append(meta_fields + data_fields)
        i += block_size
    result = pd.DataFrame(combined_rows, columns=columns)
    result = result.astype(dtype=dtype_map)

    return result


def crism_mrdr_ancill_position(identifiers, block, target, name, start_byte):
    """
    ROW_BYTES = 14 in the labels, but it should be 16 (the RECORD_BYTES)

    HITS
    * crism
        * ancil_mrdr
    """
    from pdr.loaders.queries import table_position
    
    table_props = table_position(identifiers, block, target, name, start_byte)
    n_rows = block["ROWS"]
    row_bytes = identifiers["RECORD_BYTES"]
    table_props["length"] = n_rows * row_bytes
    return table_props

def ancil_table_loader(filename, fmtdef_dt):
    """
    In the CRISM ancillary OBS tables, missing values are variations of "N/A", 
    which causes mixed dtype warnings when the first row contains N/A's.

    HITS
    * crism
        * extras_obs
    """
    import pandas as pd

    missing_const = ['N/A  ', 'N/A   ', 'N/A             ', 
                     'N/A                       ',]
    table = pd.read_csv(filename, header=None,
                        na_values=missing_const,
                        dtype={0:str, 44:str, 46:str, 47:str, 48:str})

    col_names = [c for c in fmtdef_dt[0]['NAME'] if "PLACEHOLDER" not in c]
    assert len(table.columns) == len(col_names), "mismatched column count"
    table.columns = col_names
    return table
