"""
methods for working with numpy objects, primarily intended as components of
pdr.Data's processing pipelines.
"""
from bz2 import BZ2File
from gzip import GzipFile
from io import BufferedIOBase, BytesIO
from numbers import Number
from typing import Collection, Optional, Union
from zipfile import ZipFile

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
    if len(array.dtype) < 2:
        if len(array.dtype) == 0:
            dtype = array.dtype
            void_return = array
        else:
            dtype = array.dtype[0]
            # if we don't slice the field out explicitly, numpy will transform
            # it into an array of tuples
            void_return = array[tuple(array.dtype.fields.keys())[0]]
        if "V" in str(dtype):
            return void_return.astype("O")
        if dtype.isnative:
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
    # TODO: this may work unreliably for small integer types
    return np.array(array, dtype=swapped_dtype)


def casting_to_float(array: np.ndarray, *operands: Collection[Number]) -> bool:
    """
    check: will this operation cast the array to float?
    return True if array is integer-valued and any operands are not integers.
    """
    return (array.dtype.char in np.typecodes["AllInteger"]) and not all(
        [isinstance(operand, int) for operand in operands]
    )


# TODO: shake this out with a bunch of different compression type examples,
#  including specific compressions on band/line/single-plane/etc. images,
#  compressed binary tables, etc.
def np_from_buffered_io(
    buffered_io: BufferedIOBase,
    dtype: Union[np.dtype, str],
    offset: Optional[int] = None,
    count: Optional[int] = None,
):
    """
    return a numpy array from a buffered IO object, first decompressing it in
    memory if it's a compressed buffer, and just using np.fromfile if it's not
    """
    if offset is not None:
        buffered_io.seek(offset)
    if isinstance(buffered_io, (BZ2File, ZipFile, GzipFile, BytesIO)):
        n_bytes = None if count is None else count * dtype.itemsize
        stream = BytesIO(buffered_io.read(n_bytes))
        return np.frombuffer(stream.getbuffer(), dtype=dtype)
    count = -1 if count is None else count
    return np.fromfile(buffered_io, dtype=dtype, count=count)


def make_c_contiguous(arr: np.ndarray) -> np.ndarray:
    if arr.flags["C_CONTIGUOUS"] is False:
        return np.ascontiguousarray(arr)
    return arr


# TODO: really all arguments but ibm/sreg are redundant for basic S/360 formats
def ibm_to_np(ibm, sreg, ereg, mmask):
    # dtype conversion: this field must be signed
    ibm_sign = (ibm >> sreg & 0x01).astype('int8')
    # dtype_conversion: largest values possible will overfloat int64 or float32
    ibm_exponent = (ibm >> ereg & 0x7f).astype('float64')
    ibm_mantissa = ibm & mmask
    mantissa = ibm_mantissa / (2 ** ereg)
    exponent = 16 ** (ibm_exponent - 64)
    sign = 1 - (2 * ibm_sign).astype('int8')
    return sign * mantissa * exponent


def ibm32_to_np_f32(ibm):
    return ibm_to_np(ibm, 31, 24, 0x00ffffff)


def ibm64_to_np_f64(ibm):
    return ibm_to_np(ibm, 63, 56, 0x00ffffffffffffff)
