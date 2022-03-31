"""
methods for working with numpy objects, primarily intended as components of
pdr.Data's processing pipelines.
"""
from numbers import Number
from typing import Collection

import numpy as np


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
        if "V" in str(array.dtype[0]):
            # if we don't slice the field out explicitly, numpy will transform
            # it into an array of tuples
            return array[tuple(array.dtype.fields.keys())[0]].astype("O")
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


def casting_to_float(array: np.ndarray, *operands: Collection[Number]) -> bool:
    """
    check: will this operation cast the array to float?
    return True if array is integer-valued and any operands are not integers.
    """
    return (array.dtype.char in np.typecodes["AllInteger"]) and not all(
        [isinstance(operand, int) for operand in operands]
    )