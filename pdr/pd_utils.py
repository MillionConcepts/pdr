"""
methods for working with pandas objects, primarily intended as components of
pdr.Data's processing pipelines. some may require a Data object as an
argument.
"""
import warnings
from typing import Hashable

import numpy as np
import pandas.api.types
import pandas as pd

from pdr.datatypes import sample_types
from pdr.formats import check_special_sample_type
from pdr.np_utils import enforce_order_and_object


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


def _apply_item_offsets(fmtdef):
    item_offsets = fmtdef['ITEM_BYTES'].copy()
    if "ITEM_OFFSET" not in fmtdef.columns:
        return item_offsets
    offset = fmtdef.loc[fmtdef['ITEM_OFFSET'].notna()]
    if (offset['ITEM_OFFSET'] < offset['ITEM_BYTES']).any():
        raise ValueError(
            "Don't know how to intepret a field narrower than its value."
        )
    item_offsets.loc[offset.index] = offset['ITEM_OFFSET']
    return item_offsets


def compute_offsets(fmtdef):
    """
    given a DataFrame containing PDS3 binary table structure specifications,
    including a START_BYTE column, add an OFFSET column, unpacking objects
    if necessary
    """
    # START_BYTE is 1-indexed, but we're preparing these offsets for
    # numpy, which 0-indexes
    fmtdef['OFFSET'] = fmtdef['START_BYTE'] - 1
    if 'ROW_PREFIX_BYTES' in fmtdef.columns:
        fmtdef['OFFSET'] += fmtdef['ROW_PREFIX_BYTES']
    block_names = fmtdef['BLOCK_NAME'].unique()
    # calculate offsets for formats loaded in by reference
    for block_name in block_names[1:]:
        fmt_block = fmtdef.loc[fmtdef['BLOCK_NAME'] == block_name]
        prior = fmtdef.loc[fmt_block.index[0] - 1]
        fmtdef.loc[
            fmt_block.index, 'OFFSET'
        ] += prior['OFFSET'] + prior['BYTES']
    # correctly compute offsets within columns w/multiple items
    if 'ITEM_BYTES' in fmtdef:
        fmtdef['ITEM_SIZE'] = _apply_item_offsets(fmtdef)
        column_groups = fmtdef.loc[fmtdef['ITEM_SIZE'].notna()]
        for _, group in column_groups.groupby('OFFSET'):
            fmtdef.loc[group.index, 'OFFSET'] = (
                group['OFFSET']
                + int(group['ITEM_SIZE'].iloc[0])
                * np.arange(len(group))
            )
    pad_length = 0
    end_byte = fmtdef['OFFSET'].iloc[-1] + fmtdef['BYTES'].iloc[-1]
    if 'ROW_BYTES' in fmtdef.columns:
        pad_length += fmtdef['ROW_BYTES'].iloc[0] - end_byte
    if 'ROW_SUFFIX_BYTES' in fmtdef.columns:
        pad_length += fmtdef['ROW_SUFFIX_BYTES'].iloc[0]
    if pad_length > 0:
        placeholder_rec = {
            'NAME': 'PLACEHOLDER_0',
            'DATA_TYPE': 'VOID',
            'BYTES': pad_length,
            'START_BYTE': end_byte,
            'OFFSET': end_byte
        }
        fmtdef = pd.concat(
            [fmtdef, pd.DataFrame([placeholder_rec])]
        ).reset_index(drop=True)
    return fmtdef


def _fill_empty_byte_rows(fmtdef):
    nobytes = fmtdef['BYTES'].isna()
    with warnings.catch_warnings():
        # we do not care that loc will set items inplace later. at all.
        warnings.simplefilter("ignore", category=FutureWarning)
        fmtdef.loc[nobytes, 'BYTES'] = (
            # TODO, maybe: update with ITEM_OFFSET should we implement that
            fmtdef.loc[nobytes, 'ITEMS'] * fmtdef.loc[nobytes, 'ITEM_BYTES']
        )
    fmtdef['BYTES'] = fmtdef['BYTES'].astype(int)
    return fmtdef


def insert_sample_types_into_df(fmtdef, data):
    """
    given a DataFrame containing PDS3 binary table structure specifications,
    insert numpy-compatible data type strings into that DataFrame;
    return that DataFrame along with a numpy dtype object generated from it.
    used in the Data.read_table pipeline.
    """
    fmtdef['dt'] = None
    if 'BYTES' not in fmtdef.columns:
        fmtdef['BYTES'] = np.nan
    if fmtdef['BYTES'].isna().any():
        try:
            fmtdef = _fill_empty_byte_rows(fmtdef)
        except (KeyError, TypeError, IndexError):
            raise ValueError("This table's byte sizes are underspecified.")
    if 'ITEM_BYTES' not in fmtdef.columns:
        fmtdef['ITEM_BYTES'] = np.nan
    if 'START_BYTE' in fmtdef.columns:
        fmtdef = compute_offsets(fmtdef)
    data_types = tuple(
        fmtdef.groupby(['DATA_TYPE', 'ITEM_BYTES', 'BYTES'], dropna=False)
    )
    for data_type, group in data_types:
        dt, item_bytes, total_bytes = data_type
        sample_bytes = total_bytes if np.isnan(item_bytes) else item_bytes
        try:
            is_special, special_type = check_special_sample_type(
                data, dt, int(sample_bytes), for_numpy=True
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
    dtype_spec = fmtdef[
        [c for c in ('NAME', 'dt', 'OFFSET') if c in fmtdef.columns]
    ].to_dict('list')
    spec_keys = ('names', 'formats', 'offsets')[:len(dtype_spec)]
    return(
        fmtdef,
        np.dtype({k: v for k, v in zip(spec_keys, dtype_spec.values())})
    )


def booleanize_booleans(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    boolean_columns = fmtdef.loc[fmtdef["DATA_TYPE"] == "BOOLEAN", "NAME"]
    table[boolean_columns] = table[boolean_columns].astype(bool)
    return table


def rectified_rec_df(array: np.ndarray) -> pd.DataFrame:
    return pd.DataFrame.from_records(enforce_order_and_object(array))


def structured_array_to_df(array: np.ndarray) -> pd.DataFrame:
    sub_dfs = []
    name_buffer = []
    for field in array.dtype.descr:
        if len(field) == 2:
            name_buffer.append(field[0])
        else:
            if len(name_buffer) > 0:
                sub_dfs.append(rectified_rec_df(array[name_buffer]))
                name_buffer = []
            sub_df = rectified_rec_df(array[field[0]])
            sub_df.columns = [
                f"{field[0]}_{ix}" for ix in range(len(sub_df.columns))
            ]
            sub_dfs.append(sub_df)
    if len(name_buffer) > 0:
        sub_dfs.append(rectified_rec_df(array[name_buffer]))
    if len(sub_dfs) == 0:
        return sub_dfs[0]
    df = pd.concat(sub_dfs, axis=1)
    return df
