"""
Methods for working with pandas objects, primarily intended for use in
TABLE/ARRAY/SPREADSHEET/HISTOGRAM-loading workflows.
"""
from __future__ import annotations
from itertools import chain
import re
from typing import Hashable, TYPE_CHECKING
import warnings

from more_itertools import divide
import numpy as np
import pandas as pd
import pandas.api.types
from pandas.errors import SettingWithCopyWarning
import vax

from pdr.datatypes import sample_types
from pdr.formats import check_special_sample_type
from pdr.np_utils import (
    enforce_order_and_object, ibm32_to_np_f32, ibm64_to_np_f64
)

if TYPE_CHECKING:
    from pdr.pdrtypes import DataIdentifiers


def numeric_columns(df: pd.DataFrame) -> list[Hashable]:
    """Return names of all 'numeric' columns in a DataFrame."""
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
        # TODO: check what this is hitting.
        if name == "RESERVED":
            name = f"RESERVED_{field_group['START_BYTE'].iloc[0]}"
        names = [f"{name}_{ix}" for ix in range(len(field_group))]
        df.loc[field_group.index, column] = names
    return df


def _apply_item_offsets(fmtdef: pd.DataFrame) -> pd.Series:
    """
    Select item offsets (for a column or container with multiple items). If
    the specification didn't give item offsets, just assume they're equal to
    the byte width (i.e. there's no variable padding between fields).
    """
    item_offsets = fmtdef["ITEM_BYTES"].copy()
    if "ITEM_OFFSET" not in fmtdef.columns:
        return item_offsets
    offset = fmtdef.loc[fmtdef["ITEM_OFFSET"].notna()]
    if (offset["ITEM_OFFSET"] < offset["ITEM_BYTES"]).any():
        raise ValueError(
            "Don't know how to intepret a field narrower than its value."
        )
    item_offsets.loc[offset.index] = offset["ITEM_OFFSET"]
    return item_offsets


def compute_offsets(fmtdef: pd.DataFrame) -> pd.DataFrame:
    """
    PDS3 TABLE/SPREADSHEET/ARRAY specifications do not explicitly give the
    correct byte offsets for CONTAINERs, COLLECTIONs, anything loaded in by
    reference from a STRUCTURE, or repeated elements of a COLUMN. Byte offsets
    in these cases always refer to their parent containers, which can repeat,
    have children with their own repetitions, etc., etc. This function
    'unpacks' a format definition as necessary and adds an SB_OFFSET column
    giving the correct byte offsets (from record start) for each field of the
    data table/array.
    """
    # START_BYTE is 1-indexed, but we're preparing these offsets for
    # numpy, which 0-indexes
    fmtdef["SB_OFFSET"] = fmtdef["START_BYTE"].astype(int) - 1
    if "ROW_PREFIX_BYTES" in fmtdef.columns:
        fmtdef["SB_OFFSET"] += fmtdef["ROW_PREFIX_BYTES"]
    block_names = fmtdef.loc[
        fmtdef['NAME'] != "PLACEHOLDER_0", "BLOCK_NAME"
    ].unique()
    # calculate offsets for formats loaded in by reference
    for block_name in block_names[1:]:
        if block_name in ("PLACEHOLDER_None", f"PLACEHOLDER_{block_names[0]}"):
            continue
        fmt_block = fmtdef.loc[fmtdef["BLOCK_NAME"] == block_name]
        if "PLACEHOLDER" in block_name:
            prior = fmtdef[fmtdef["NAME"] == block_name].squeeze()
        else:
            prior = fmtdef.loc[fmt_block.index[0] - 1]
        fmtdef.loc[fmt_block.index, "SB_OFFSET"] += (
            prior["SB_OFFSET"] + prior["BYTES"]
        )
        if "ROW_PREFIX_BYTES" in fmtdef.columns:
            fmtdef.loc[fmt_block.index, "SB_OFFSET"] -= fmtdef["ROW_PREFIX_BYTES"]
        count = fmt_block["BLOCK_REPETITIONS"].iloc[0]
        if (reps := prior["BLOCK_REPETITIONS"]) > 1:
            if "PLACEHOLDER" in block_name:
                fmtdef.loc[fmt_block.index, "BLOCK_REPETITIONS"] *= reps
            else:
                count *= reps
        if count == 1:
            continue
        chunks = tuple(map(list, divide(count, fmt_block.index)))
        block_size = fmt_block['BLOCK_BYTES'].iloc[0]
        if block_size != int(block_size):
            raise NotImplementedError("irregular repeated container size.")
        block_size = int(block_size)
        offset_chain = chain(
            *[[i for _ in c] for (i, c) in enumerate(chunks)]
        )
        fmtdef.loc[
            fmt_block.index, "SB_OFFSET"
        ] += np.array(list(offset_chain)) * block_size
    # correctly compute offsets within columns w/multiple items
    if "ITEM_BYTES" in fmtdef.columns:
        fmtdef["ITEM_SIZE"] = _apply_item_offsets(fmtdef)
        column_groups = fmtdef.loc[fmtdef["ITEM_SIZE"].notna()]
        group_offs = column_groups['SB_OFFSET'].value_counts().sort_index()
        gix_list, position = [], 0
        for off, gl in zip(group_offs.index, group_offs.values):
            itemsize = int(column_groups['ITEM_SIZE'].iloc[position])
            gix_list += [(i * itemsize) + off for i in range(gl)]
            position += gl
        fmtdef.loc[column_groups.index, 'SB_OFFSET'] = gix_list
    pad_length = 0
    end_byte = fmtdef["SB_OFFSET"].iloc[-1] + fmtdef["BYTES"].iloc[-1]
    if "ROW_BYTES" in fmtdef.columns:
        pad_length += fmtdef["ROW_BYTES"].iloc[0] - end_byte
    if "ROW_SUFFIX_BYTES" in fmtdef.columns:
        pad_length += fmtdef["ROW_SUFFIX_BYTES"].iloc[0]
    if pad_length > 0:
        placeholder_rec = {
            "NAME": "PLACEHOLDER_0",
            "DATA_TYPE": "VOID",
            "BYTES": pad_length,
            "START_BYTE": end_byte,
            "SB_OFFSET": end_byte,
        }
        fmtdef = pd.concat(
            [fmtdef, pd.DataFrame([placeholder_rec])]
        ).reset_index(drop=True)
    return fmtdef


def insert_sample_types_into_df(
    fmtdef: pd.DataFrame, identifiers: DataIdentifiers
) -> tuple[pd.DataFrame, np.dtype]:
    """
    Insert numpy-compatible data type strings into a TABLE/ARRAY format
    definition DataFrame. Also generate a numpy dtype object from that
    DataFrame.
    """
    fmtdef["dt"] = None
    if "ITEM_BYTES" not in fmtdef.columns:
        fmtdef["ITEM_BYTES"] = np.nan
    data_types = tuple(
        fmtdef.groupby(["DATA_TYPE", "ITEM_BYTES", "BYTES"], dropna=False)
    )
    for data_type, group in data_types:
        dt, item_bytes, total_bytes = data_type
        sample_bytes = total_bytes if np.isnan(item_bytes) else item_bytes
        try:
            samp_info = {"SAMPLE_TYPE": dt, "BYTES_PER_PIXEL": sample_bytes}
            is_special, special_type = check_special_sample_type(
                identifiers, samp_info
            )
            if is_special:
                fmtdef.loc[group.index, "dt"] = special_type
            else:
                fmtdef.loc[group.index, "dt"] = sample_types(
                    dt, int(sample_bytes), for_numpy=True
                )
        except KeyError:
            raise KeyError(
                f"{data_type} is not a currently-supported data type."
            )
    if "BLOCK_NAME" in fmtdef.columns:
        fmtdef = construct_nested_array_format(fmtdef)
    dt = fmtdef_to_dtype(fmtdef)
    return fmtdef, dt


def fmtdef_to_dtype(fmtdef: pd.DataFrame) -> np.dtype:
    """
    Construct a structured (but ideally never nested, see
    `construct_nested_array_format()` below) dtype from a format definition.
    """
    dtype_spec = fmtdef[
        [c for c in ("NAME", "dt", "SB_OFFSET") if c in fmtdef.columns]
    ].to_dict("list")
    spec_keys = ("names", "formats", "offsets")[: len(dtype_spec)]
    return np.dtype({k: v for k, v in zip(spec_keys, dtype_spec.values())})


def construct_nested_array_format(fmtdef: pd.DataFrame) -> pd.DataFrame:
    """
    ARRAY objects can be deeply nested. This function computes the correct
    byte offsets and dtypes (including array shape) for any nested subelements.
    """
    for block_name in fmtdef.loc[
        fmtdef["NAME"] != "PLACEHOLDER_0", "BLOCK_NAME"
    ].unique()[1:]:
        if block_name == "":
            continue
        fmt_block = fmtdef.loc[fmtdef["BLOCK_NAME"] == block_name]
        prior = fmtdef.loc[fmt_block.index[0] - 1]
        if "AXIS_ITEMS" not in prior.keys():
            continue
        if np.isnan(axis_items := prior["AXIS_ITEMS"]):
            continue
        with warnings.catch_warnings():
            # TODO: We are intentionally setting with copy here. However, it
            #  will start hard-failing in pandas 3.x and needs to be changed.
            warnings.filterwarnings("ignore", category=SettingWithCopyWarning)
            fmt_block[
                "SB_OFFSET"
            ] = fmt_block["SB_OFFSET"] - prior["SB_OFFSET"]
        if isinstance(axis_items, float):
            axis_items = int(axis_items)
        dt = fmtdef_to_dtype(fmt_block)
        fmtdef.at[fmt_block.index[0] - 1, "dt"] = (dt, axis_items)
        fmtdef = fmtdef[~fmtdef.NAME.isin(fmt_block.NAME)]
    return fmtdef


def booleanize_booleans(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    """
    We generally load boolean columns from binary tables as uint8 of value 0
    or 1. This converts all such columns of a DataFrame to np.bool.
    """
    boolean_columns = fmtdef.loc[fmtdef["DATA_TYPE"] == "BOOLEAN", "NAME"]
    table[boolean_columns] = table[boolean_columns].astype(bool)
    return table


def convert_ebcdic(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    """
    Decode any columns of a DataFrame that contain bytestrings constructed from
    IBM S/360-style EBCDIC-encoded text to Python strings.
    """
    ebcdic_columns = fmtdef.loc[
        fmtdef["DATA_TYPE"].str.contains("EBCDIC"), "NAME"
    ]
    for col in ebcdic_columns:
        # TODO: why do we copy table[col] twice?
        series = pd.Series(table[col])
        table[col] = series.str.decode('cp500')
    return table


def rectified_rec_df(array: np.ndarray) -> pd.DataFrame:
    """
    Attempt to 'flatten' a 1- or 2D ndarray, possibly with a structured dtype
    but with no nested arrays, into a DataFrame, typecasting as necessary for
    pandas compatibility.
    """
    if len(array.shape) == 3:
        # it's possible to pack 2D arrays into individual records. this
        # obviously does not work for pandas. if we encounter > 2D elements,
        # we can generalize this.
        array = array.reshape(array.shape[0], array.shape[1] * array.shape[2])
    elif len(array.shape) > 3:
        raise NotImplementedError("dtypes with >2D elements are not supported")
    if len(array.dtype) == 0:
        # if it doesn't have a structured dtype, don't call from_records --
        # it's slow and acts weird
        return pd.DataFrame(enforce_order_and_object(array))
    # but if it does, do
    return pd.DataFrame.from_records(enforce_order_and_object(array))


def structured_array_to_df(array: np.ndarray) -> pd.DataFrame:
    """
    Attempt to convert an ndarray with a structured dtype to a DataFrame,
    flattening any nested 1- or 2-D arrays into blocks of columns and
    typecasting as necessary for pandas compatibility. This does not attempt
    to flatten nested elements with dimensionality > 2, and will raise a
    NotImplementedError if it encounters them.
    """
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
    if len(sub_dfs) == 1:
        return sub_dfs[0]
    return pd.concat(sub_dfs, axis=1)


def convert_ibm_reals(df: pd.DataFrame, fmtdef: pd.DataFrame) -> pd.DataFrame:
    """
    Converts all IBM reals in a dataframe from packed 32- or 64-bit integer
    form to np.float32 or np.float64.
    """
    if not fmtdef['DATA_TYPE'].str.contains('IBM').any():
        return df
    reals = {}
    for _, field in fmtdef.iterrows():
        if not re.match(r'IBM.*REAL', field['DATA_TYPE']):
            continue
        func = ibm32_to_np_f32 if field['BYTES'] == 4 else ibm64_to_np_f64
        converted = func(df[field['NAME']].values)
        if field['BYTES'] == 4:
            # IBM shorts are wider-range than IEEE shorts; check if we can
            # safely cast them back down to float32
            absolute = abs(converted)
            big = absolute.max() > np.finfo(np.float32).max
            nonzero = absolute[absolute > 0]
            if len(nonzero) > 0:
                small = nonzero.min() < 1e-44
            else:
                small = False
            if not (big or small):
                converted = converted.astype(np.float32)
        reals[field['NAME']] = converted
        # IBM longs just get more precise, not wider-ranged, so we don't need
        # to check for longlong or anything like that
    for k, v in reals.items():
        df[k] = v
    return df


def convert_vax_reals(data: pd.DataFrame, properties: pd.DataFrame) -> pd.DataFrame:
    """If any columns in a DataFrame are in 32-bit VAX real format,
    convert them to 32-bit float."""
    if not properties['DATA_TYPE'].str.contains('VAX').any():
        return data
    reals = {}
    for _, field in properties.iterrows():
        if not re.match(r'VAX.*REAL', field['DATA_TYPE']):
            continue
        func = vax.from_vax32  # TODO: if field['BYTES'] == 4 else vax.from_vax64
        converted = func(data[field['NAME']].values)
        reals[field['NAME']] = converted
    for k, v in reals.items():
        data[k] = v
    return data
