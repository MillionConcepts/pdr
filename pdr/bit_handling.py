"""utilities for parsing BIT_COLUMN objects in tables."""
from __future__ import annotations
from functools import partial, reduce
from operator import add
from typing import Any, Mapping, Sequence, TYPE_CHECKING

import numpy as np
import pandas as pd

from pdr.datatypes import determine_byte_order, sample_types
from pdr.formats import (
    check_special_bit_column_case, check_special_bit_start_case
)
import warnings

if TYPE_CHECKING:
    from multidict import MultiDict
    from pdr.pdrtypes import ByteOrder, DataIdentifiers


def expand_bit_strings(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    """
    Top-level handler function for the bit column workflow. Converts a binary
    table's bit string columns (if any) from raw bytes to lists of strings
    (e.g. ['0010, 0011']).
    """
    # bit_handling.get_bit_start_and_size() defines this column, and
    # handlers.add_bit_column_info() adds it.
    if "start_bit_list" not in fmtdef.columns:
        return table
    table = convert_to_full_bit_string(table, fmtdef)
    return splice_bit_string(table, fmtdef)


def convert_to_full_bit_string(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    """
    Converts the elements of a DataFrame's bit string columns from bytes to
    binary strings (e.g. '00100011').
    """
    for column in fmtdef.start_bit_list.dropna().index:
        # if it's not a list, that means the table column represented by this
        # fmtdef row isn't a bit string.
        if isinstance(fmtdef.start_bit_list[column], list):
            byte_column = table[fmtdef.NAME[column]]
            byte_order = determine_byte_order(fmtdef.DATA_TYPE[column])
            bit_str_column = convert_byte_column_to_bits(
                byte_column, byte_order
            )
            table[fmtdef.NAME[column]] = bit_str_column
    return table


def factor_to_dtype(field_length: int, byte_order: ByteOrder) -> np.dtype:
    """
    Determine the smallest (in terms of length) structured dtype composed of
    unsigned integer dtypes that can parse binary blob of a particular length
    and byteorder into a list of bytes. Optimizing the dtype length here
    reduces the number of times we have to call `bin()` in
    `convert_byte_column_to_bits()`, which is one of the biggest performance
    bottlenecks in this module.
    """
    lengths = [1, 2, 4, 8]
    if field_length in lengths:
        # if it fits within a simple dtype, great
        return np.dtype([("0", f"{byte_order}u{field_length}")])
    dtype, remaining_length = [], field_length
    n = 0
    while remaining_length > 0:
        if remaining_length - lengths[-1] < 0:
            lengths.pop()
            continue
        dtype.append((str(n), f"{byte_order}u{lengths[-1]}"))
        n += 1
        remaining_length -= lengths[-1]
    return np.dtype(dtype)


def convert_byte_column_to_bits(
    byte_column: pd.Series, byte_order: ByteOrder
) -> pd.Series:
    """
    Converts byte strings in a Series into binary strings
    (e.g. b"\x02" -> "10"). All elements of the Series must be byte strings,
    and all of them must have the same length.
    """
    dtype = factor_to_dtype(len(byte_column.iloc[0]), byte_order)
    # jam the byte strings together and construct an integer ndarray from them
    byte_array = np.frombuffer(b"".join(byte_column.tolist()), dtype=dtype)
    bytedf = pd.DataFrame.from_records(byte_array)
    bit_series = []
    # noinspection PyTypeChecker
    for rec_ix in range(len(dtype)):
        bit_series.append(
            bytedf[str(rec_ix)]
            # convert to bin
            .map(bin)
            # cut off the '0b'
            .str.slice(2, None)
            # make sure they're fixed-length
            .str.zfill(dtype[rec_ix].itemsize * 8)
        )
    # TODO: should probably be a single pd.concat operation
    bits = reduce(add, bit_series)
    return bits


# TODO: this name is kind of misleading -- it does the opposite of splicing
def splice_bit_string(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    """
    Split the elements of a table's bit string columns into lists of binary
    strings according to the bit boundaries specified in the label. This
    function expects to be called after convert_to_full_bit_string(), because
    the columns must already have been converted into binary strings.
    """
    for column in fmtdef.start_bit_list.dropna().index:
        if isinstance(fmtdef.start_bit_list[column], list):
            bit_column = table[fmtdef.NAME[column]]
            start_bit_list = [
                val - 1 for val in fmtdef.start_bit_list[column]
            ]  # python zero indexing
            bit_size_list = fmtdef.bit_size_list[column]
            bit_list_column = bit_column.map(
                partial(
                    split_bits,
                    start_bit_list=start_bit_list,
                    bit_size_list=bit_size_list,
                )
            )
            table[fmtdef.NAME[column]] = bit_list_column
    return table


# TODO, maybe: we have accelerated C code for this elsewhere
def split_bits(
    bit_string: Sequence,
    start_bit_list: Sequence[int],
    bit_size_list: Sequence[int]
) -> list:
    """
    Split a sequence into a list of subsequences based on start and size
    specifications. Intended here to be used on binary strings.
    """
    end_bit_list = [
        start + size for start, size in zip(start_bit_list, bit_size_list)
    ]
    return [
        bit_string[start:end]
        for start, end in zip(start_bit_list, end_bit_list)
    ]


def set_bit_string_data_type(
    obj: dict, identifiers: Mapping[str, Any]
) -> dict:
    """
    Infer a bit string column's data type and add it to `obj` (a parsed column
    definition). A subcomponent of the `queries.read_format_block()` workflow.
    """
    is_special, special_dtype = check_special_bit_column_case(identifiers)
    if is_special is False:
        try:
            byteorder = sample_types(
                obj["BIT_COLUMN"]["BIT_DATA_TYPE"], 1, True
            )[0]
        except (KeyError, ValueError):
            raise ValueError("Incompatible data type for bit columns.")
        if byteorder == ">":
            warnings.warn(
                f"Data type {obj['DATA_TYPE']} incompatible for bit column. "
                f"Changing to MSB_BIT_STRING."
            )
            obj["DATA_TYPE"] = "MSB_BIT_STRING"
        elif byteorder == "<":
            warnings.warn(
                f"Data type {obj['DATA_TYPE']} incompatible for bit column. "
                f"Changing to LSB_BIT_STRING."
            )
            obj["DATA_TYPE"] = "LSB_BIT_STRING"
    else:
        obj["DATA_TYPE"] = special_dtype
    return obj


def get_bit_start_and_size(
    obj: dict, definition: MultiDict, identifiers: DataIdentifiers
) -> dict:
    """
    Parse the BIT_COLUMN information from a MultiDict that represents a COLUMN
    definition into lists of bit string start positions and sizes that can
    later be used to parse byte strings into bit strings, then add that
    information to a parsed column definition. A subcomponent of the
    `queries.read_format_block()` workflow.
    """
    start_bit_list = []
    bit_size_list = []
    list_of_pvl_objects_for_bit_columns = definition.getall("BIT_COLUMN")
    for pvl_obj in list_of_pvl_objects_for_bit_columns:
        if pvl_obj.get("ITEMS"):
            items = pvl_obj.get("ITEMS")
            item_bits = pvl_obj.get("ITEM_BITS")
            first_item_start_bit = pvl_obj.get("START_BIT")
            for item_index in range(items):
                start_bit = first_item_start_bit + item_index * item_bits
                start_bit_list.append(start_bit)
                bit_size_list.append(item_bits)
        else:
            start_bit = pvl_obj.get("START_BIT")
            bit_size = pvl_obj.get("BITS")
            start_bit_list.append(start_bit)
            bit_size_list.append(bit_size)
    is_also_special, special_start_bit_list = check_special_bit_start_case(
        identifiers, list_of_pvl_objects_for_bit_columns, start_bit_list
    )
    if is_also_special:
        obj["start_bit_list"] = special_start_bit_list
    else:
        obj["start_bit_list"] = start_bit_list
    obj["bit_size_list"] = bit_size_list
    return obj

