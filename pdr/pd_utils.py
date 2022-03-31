"""
methods for working with pandas objects, primarily intended as components of
pdr.Data's processing pipelines. some may require a Data object as an
argument.
"""
from typing import Hashable

import numpy as np
import pandas.api.types
import pandas as pd

from pdr.datatypes import sample_types
from pdr.formats import check_special_sample_type


def numeric_columns(df: pd.DataFrame) -> list[Hashable]:
    return [
        col
        for col, dtype in df.dtypes.iteritems()
        if pandas.api.types.is_numeric_dtype(dtype)
    ]


def reindex_df_values(df: pd.DataFrame, column="NAME") -> pd.DataFrame:
    """
    give unique string identifiers to every value in a particular column of
    a DataFrame by appending an underscore and an incrementing number if
    necessary.

    include START_BYTE in string for values marked as RESERVED.
    """
    namegroups = df.groupby(column)
    for name, field_group in namegroups:
        if len(field_group) == 1:
            continue
        if name == "RESERVED":
            name = f"RESERVED_{field_group['START_BYTE'].iloc[0]}"
        names = [f"{name}_{ix}" for ix in range(len(field_group))]
        df.loc[field_group.index, column] = names
    return df


def insert_sample_types_into_df(fmtdef, data):
    """
    given a DataFrame containing PDS3 binary table structure specifications,
    insert numpy-compatible data type strings into that DataFrame;
    return that DataFrame along with a numpy dtype object generated from it.
    used in the Data.read_table pipeline.
    """
    fmtdef['dt'] = None
    if 'ITEM_BYTES' not in fmtdef.columns:
        fmtdef['ITEM_BYTES'] = np.nan
    data_types = tuple(
        fmtdef.groupby(['DATA_TYPE', 'ITEM_BYTES', 'BYTES'], dropna=False)
    )
    for data_type, group in data_types:
        dt, item_bytes, total_bytes = data_type
        sample_bytes = total_bytes if np.isnan(item_bytes) else item_bytes
        try:
            is_special, special_type = check_special_sample_type(
                dt, int(sample_bytes), data, for_numpy=True
            )
            if is_special:
                fmtdef.loc[group.index, 'dt'] = special_type
            else:
                fmtdef.loc[group.index, 'dt'] = sample_types(
                    dt, int(sample_bytes), for_numpy=True
                )
        except KeyError:
            raise KeyError(
                f"{data_type} is not a currently-supported data type."
            )
    return (
        fmtdef,
        np.dtype(fmtdef[['NAME', 'dt']].to_records(index=False).tolist())
    )


def booleanize_booleans(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    boolean_columns = fmtdef.loc[fmtdef["DATA_TYPE"] == "BOOLEAN", "NAME"]
    table[boolean_columns] = table[boolean_columns].astype(bool)
    return table
