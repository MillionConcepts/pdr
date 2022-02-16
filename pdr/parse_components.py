"""
objects intended principally as components of parsing pipelines for pdr.Data.
some may have other useful purposes.
"""
import warnings

import numpy as np
import pandas as pd

from pdr.datatypes import sample_types


def enforce_order_and_object(array: np.ndarray, inplace=True) -> np.ndarray:
    """
    determine which, if any, of an array's fields are in nonnative byteorder
    and swap them.

    furthermore:
    pandas does not support numpy void ('V') types, which are sometimes
    required to deal with unstructured padding containing null bytes, etc.,
    and are probably the appropriate representation for binary blobs like
    bit strings. cast them to object so it does not explode. doing this here
    is inelegant but is somewhat efficient.
    TODO: still not that efficient
    TODO: benchmark
    """
    if inplace is False:
        array = array.copy()
    if len(array.dtype) == 1:
        if array.dtype.isnative:
            return array
        return array.byteswap().newbyteorder("=")
    swap_targets = []
    swapped_dtype = []
    for name, field in array.dtype.fields.items():
        if field[0].isnative is False:
            swap_targets.append(name)
            swapped_dtype.append((name, field[0].newbyteorder("=")))
        elif "V" not in str(field[0]):
            swapped_dtype.append((name, field[0]))
        else:
            swapped_dtype.append((name, "O"))
    return np.array(array, dtype=swapped_dtype)


def booleanize_booleans(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    boolean_columns = fmtdef.loc[fmtdef["DATA_TYPE"] == "BOOLEAN", "NAME"]
    table[boolean_columns] = table[boolean_columns].astype(bool)
    return table


def filter_duplicate_pointers(pointers, pt_groups):
    for pointer, group in pt_groups.items():
        if (len(group) > 1) and (pointer != "^STRUCTURE"):
            warnings.warn(
                f"Duplicate handling for {pointer} not yet "
                f"implemented, ignoring"
            )
        else:
            pointers.append(group[0][0])
    return pointers


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


def insert_sample_types_into_df(fmtdef):
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
            fmtdef.loc[group.index, 'dt'] = sample_types(
                dt, sample_bytes, for_numpy=True
            )
        except KeyError:
            raise KeyError(
                f"{data_type} is not a currently-supported data type."
            )
    return (
        fmtdef,
        np.dtype(fmtdef[['NAME', 'dt']].to_records(index=False).tolist())
    )
