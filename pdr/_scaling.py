import warnings
from functools import wraps
from itertools import product
from numbers import Integral, Number, Real
from typing import Optional, Sequence, Union

import numpy as np

from pdr.formats.checkers import specialblock
from pdr.datatypes import PDS3_CONSTANT_NAMES, IMPLICIT_PDS3_CONSTANTS
from pdr.np_utils import casting_to_float
from pdr.pdrtypes import PDRLike


def find_special_constants(
    data: PDRLike, obj: np.ndarray, name: str
) -> dict[str, Number]:
    """
    attempts to find special constants in an ndarray associated with a PDS3
    object by referencing the label and "standard" special constant values.
    """
    # NOTE: doesn't do anything for PDS4 products at present, although this
    #  may not be important; usually pds4_tools handles it.

    block = specialblock(data, name)
    # check for explicitly-defined special constants
    specials = {
        name: block[name]
        for name in PDS3_CONSTANT_NAMES
        if (name in block.keys()) and not (block[name] == "N/A")
    }
    for k in specials.keys():
        if isinstance(specials[k], Sequence):
            specials[k] = specials[k][0]
    # ignore uint8 implicit constants (0, 255) for now -- too problematic
    # TODO: maybe add an override
    if obj.dtype.name == "uint8":
        return specials
    # check for implicit constants appropriate to the sample type
    implicit_possibilities = IMPLICIT_PDS3_CONSTANTS[obj.dtype.name]
    # can't check for nans with "in" because it's an equality check, so
    # we don't intend this to be used, just want to make the key and put
    # in a value that won't conflict later
    if np.any(~np.isfinite(obj.data)):
        specials["INVALIDS"] = np.nan
    return specials | {
        possibility: constant
        for possibility, constant in implicit_possibilities.items()
        if constant in obj
    }


def mask_specials(obj, specials):
    """"""
    obj = np.ma.masked_array(obj)
    if np.nan in specials:
        # masks infs and nans as well
        obj.mask = np.ma.mask_or(np.isin(obj.data, specials),
                                 ~np.isfinite(obj.data))
    else:
        obj.mask = np.isin(obj.data, specials)
    return obj


def fit_to_scale(
    arr: np.ndarray,
    scale: Union[Integral, Real],
    offset: Union[Integral, Real]
) -> np.ndarray:
    """
    Return a version of `arr` cast to the minimum dtype that will hold its
    range of values after multiplying by `offset` and adding `scale`.

    Supports:

    float32, float64, uint8, int8, uint16, int16, uint32, int32, uint64, int64.
    """
    if arr.dtype.char not in 'bBhHiIlLqQnNpPf':
        raise TypeError(f"This function does not support {arr.dtype.name}")
    if arr.dtype.char in 'fd' or int(scale + offset) != scale + offset:
        bases, widths, infofunc = ('f',), (4, 8), np.finfo
    else:
        bases, widths, infofunc = ('u', 'i'), (1, 2, 4, 8), np.iinfo
    amin, amax = map(int, (arr.min(), arr.max()))
    smin, smax = amin * scale + offset, amax * scale + offset
    for base, width in product(bases, widths):
        candidate = np.dtype(f'{base}{width}')
        cinfo = infofunc(candidate)
        if smin >= cinfo.min and smax <= cinfo.max:
            return arr.astype(candidate)
    raise TypeError("Unable to find a suitable data type for scaling.")


def overflow_wrap(array_func):
    @wraps(array_func)
    def with_upcasting(arr, scale, offset, *args, **kwargs):
        with warnings.catch_warnings():
            warnings.filterwarnings("error", message=".*overflow enc.*")
            try:
                return array_func(arr, scale, offset, *args, **kwargs)
            except (OverflowError, RuntimeWarning):
                arr = fit_to_scale(arr, scale, offset)
                return array_func(arr, scale, offset, *args, **kwargs)

    return with_upcasting


def _copy_scale(obj, offset, scale):
    try:
        # TODO: we should also be doing this per-plane scaling in inplace case
        if len(obj) == len(scale) == len(offset) > 1:
            planes = [
                obj[ix] * scale[ix] + offset[ix] for ix in range(len(scale))
            ]
            stacked = np.rollaxis(np.ma.dstack(planes), 2)
            return stacked
    except TypeError:
        pass  # len() is not usable on a float object
    return obj * scale + offset


def _inplace_scale(obj, offset, scale):
    if len(obj) == len(scale) == len(offset) > 1:
        for ix, _ in enumerate(scale):
            obj[ix] = obj[ix] * scale[ix] + offset[ix]
    else:
        obj *= scale
        obj += offset
    return obj


def scale_array(
    meta: PDRLike,
    obj: np.ndarray,
    object_name: str,
    inplace: bool = False,
    float_dtype: Optional["np.dtype"] = None,
):
    """"""
    from pdr.formats.checkers import specialblock

    block = specialblock(meta, object_name)
    scale, offset = 1, 0
    if "SCALING_FACTOR" in block.keys():
        scale = block["SCALING_FACTOR"]
        if isinstance(scale, dict):
            scale = scale["value"]
    if "OFFSET" in block.keys():
        offset = block["OFFSET"]
        if isinstance(offset, dict):
            offset = offset["value"]
    # meaningfully better for enormous unscaled arrays
    if (scale == 1) and (offset == 0):
        return obj
    # try to perform the operation in-place if requested, although if
    # we're casting to float, we can't
    # TODO: detect rollover cases, etc.
    if inplace is True and not casting_to_float(obj, scale, offset):
        return overflow_wrap(_inplace_scale)(obj, offset, scale)
    # if we're casting to float, permit specification of dtype
    # prior to operation (float64 is numpy's default and often excessive)
    if casting_to_float(obj, scale, offset):
        if float_dtype is not None:
            obj = obj.astype(float_dtype)
    return overflow_wrap(_copy_scale)(obj, offset, scale)


# TODO: shake this out much more vigorously
# noinspection PyUnresolvedReferences
def scale_pds4_tools_struct(struct: object) -> np.ndarray:
    """see pds4_tools.reader.read_arrays.new_array"""
    # TODO: apply bit_mask
    from pdr.pds4_tools.reader.data_types import apply_scaling_and_value_offset

    array = struct.data
    element_array = struct.meta_data["Element_Array"]
    scale_kwargs = {
        "scaling_factor": element_array.get("scaling_factor"),
        "value_offset": element_array.get("value_offset"),
    }
    # TODO: is this important?
    #     dtype = pds_to_numpy_type(struct.meta_data.data_type(),
    #     data=array, **scale_kwargs)
    special_constants = struct.meta_data.get("Special_Constants")
    array = apply_scaling_and_value_offset(
        array, special_constants=special_constants, **scale_kwargs
    )
    if hasattr(array, "mask"):
        return np.ma.masked_array(np.asarray(array.data), array.mask)
    return np.asarray(array)
