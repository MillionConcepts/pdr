"""functions for producing browse versions of products"""
import pickle
import warnings
from pathlib import Path
from typing import Any, Sequence, Union, Optional

import numpy as np
import pandas as pd
import pvl
from PIL import Image
from dustgoggles.func import naturals
from pvl.grammar import OmniGrammar


# noinspection PyArgumentList
def find_masked_bounds(image, cheat_low, cheat_high):
    """
    relatively memory-efficient way to perform bound calculations for
    normalize_range on a masked array.
    """
    valid = image[~image.mask]
    if (cheat_low != 0) and (cheat_high != 0):
        minimum, maximum = np.percentile(
            valid, [cheat_low, 100 - cheat_high], overwrite_input=True
        ).astype(image.dtype)
    elif cheat_low != 0:
        maximum = valid.max()
        minimum = np.percentile(valid, cheat_low, overwrite_input=True).astype(
            image.dtype
        )
    elif cheat_high != 0:
        minimum = valid.min()
        maximum = np.percentile(
            valid, 100 - cheat_high, overwrite_input=True
        ).astype(image.dtype)
    else:
        minimum = valid.min()
        maximum = valid.max()
    return minimum, maximum


# noinspection PyArgumentList
def find_unmasked_bounds(image, cheat_low, cheat_high):
    """straightforward way to find unmasked array bounds for normalize_range"""
    if cheat_low != 0:
        minimum = np.percentile(image, cheat_low).astype(image.dtype)
    else:
        minimum = image.min()
    if cheat_high != 0:
        maximum = np.percentile(image, 100 - cheat_high).astype(image.dtype)
    else:
        maximum = image.max()
    return minimum, maximum


def normalize_range(
    image: np.ndarray,
    bounds: Sequence[int] = (0, 1),
    clip: Union[float, tuple[float, float]] = 0,
    inplace: bool = False,
) -> np.ndarray:
    """
    simple linear min-max scaler that optionally percentile-clips the input at
    clip = (low_percentile, 100 - high_percentile). if inplace is True,
    may transform the original array, with attendant memory savings and
    destructive effects.
    """
    if isinstance(clip, Sequence):
        cheat_low, cheat_high = clip
    else:
        cheat_low, cheat_high = (clip, clip)
    range_min, range_max = bounds
    if isinstance(image, np.ma.MaskedArray):
        minimum, maximum = find_masked_bounds(image, cheat_low, cheat_high)
    else:
        minimum, maximum = find_unmasked_bounds(image, cheat_low, cheat_high)
    if not ((cheat_high is None) and (cheat_low is None)):
        if inplace is True:
            image = np.clip(image, minimum, maximum, out=image)
        else:
            image = np.clip(image, minimum, maximum)
    if inplace is True:
        # perform the operation in-place
        image -= minimum
        image *= (range_max - range_min)
        if image.dtype.char in np.typecodes['AllInteger']:
            # this loss of precision is probably better than
            # automatically typecasting it.
            # TODO: detect rollover cases, etc.
            image //= (maximum - minimum)
        else:
            image /= (maximum - minimum)
        image += range_min
        return image
    return (image - minimum) * (range_max - range_min) / (
        maximum - minimum
    ) + range_min


def eightbit(
    array: np.array,
    clip: Union[float, tuple[float, float]] = 0,
    inplace: bool = False,
) -> np.ndarray:
    """
    return an eight-bit version of an array, optionally clipped at min/max
    percentiles. if inplace is True, normalization may transform the original
    array, with attendant memory savings and destructiveness.
    """
    return np.round(normalize_range(array, (0, 255), clip, inplace)).astype(
        np.uint8
    )


def colorfill_maskedarray(
    masked_array: np.ma.MaskedArray,
    color: tuple[int, int, int] = (0, 255, 255),
):
    """
    masked_array: 2-D masked array or a 3-D masked array with last axis of
    length 3. for likely uses, this should probably be 8-bit unsigned integer.
    color: optionally-specified RGB color (default cyan)
    return a 3-D array with masked values filled with color.
    """
    if len(masked_array.shape) == 2:
        return np.dstack([masked_array.filled(color[ix]) for ix in range(3)])
    if masked_array.shape[-1] != 3:
        raise ValueError("3-D arrays must have last axis of length = 3")
    return np.dstack(
        [masked_array[:, :, ix].filled(color[ix]) for ix in range(3)]
    )


def browsify(
    obj: Any,
    outbase: Union[str, Path],
    purge: bool = False,
    image_clip: Union[float, tuple[float, float]] = (1, 1),
    mask_color: Optional[tuple[int, int, int]] = (0, 255, 255),
    band_ix: Optional[int] = None,
):
    """
    attempts to dump a browse version of a data object, writing it into a file
    type that can be opened with desktop software: .jpg for most arrays, .csv
    for tables, .txt for most other things. if it can't find a reasonable
    translation, it dumps as .pkl (pickled binary blob).
    """
    outbase = str(outbase)
    if isinstance(obj, pvl.collections.OrderedMultiDict):
        _browsify_pds3_label(obj, outbase)
    elif isinstance(obj, np.recarray):
        _browsify_recarray(obj, outbase)
    elif isinstance(obj, np.ndarray):
        _browsify_array(obj, outbase, purge, image_clip, mask_color, band_ix)
    elif isinstance(obj, pd.DataFrame):
        # noinspection PyTypeChecker
        obj.to_csv(outbase + ".csv"),
    elif obj is None:
        return
    else:
        # this should usually work. it may need another backup binary blob
        # pickler for really weird binary objects.
        with open(outbase + ".txt", "w") as stream:
            stream.write(str(obj))


def _browsify_recarray(obj: np.recarray, outbase: str):
    # some tabular data with column groups ends up as numpy recarray, which is
    # challenging to turn into a useful .csv file in some cases
    try:
        obj = pd.DataFrame.from_records(obj)
        # noinspection PyTypeChecker
        obj.to_csv(outbase + ".csv")
    except ValueError:
        pickle.dump(obj, open(outbase + "_nested_recarray.pkl", "wb"))


def _browsify_pds3_label(obj: pvl.collections.OrderedMultiDict, outbase: str):
    # try to dump PDS3 labels as formal pvl
    try:
        pvl.dump(obj, open(outbase + ".lbl", "w"), grammar=OmniGrammar())
    except (ValueError, TypeError) as e:
        warnings.warn(
            f"pvl will not dump; {e}; writing to {outbase}.badpvl.txt"
        )
        # if that fails, just dump them as text
        with open(outbase + ".badpvl.txt", "w") as file:
            file.write(str(obj))
        pass


def _browsify_array(
    obj: np.ndarray,
    outbase: str,
    purge: bool = False,
    image_clip: Union[float, tuple[float, float]] = (1, 1),
    mask_color: Optional[tuple[int, int, int]] = (0, 255, 255),
    band_ix: Optional[int] = None,
):
    """
    attempt to save array as a jpeg
    """
    if len(obj.shape) == 3:
        # for multiband arrays that are not three-band, only export a
        # single band. this is by default the "middle" one, unless the band_ix
        # kwarg has been passed.
        if obj.shape[0] != 3:
            if band_ix is None:
                band_ix = round(obj.shape[0] / 2)
            warnings.warn(f"dumping only band {band_ix} of this image")
            try:
                obj = obj[band_ix]
            except IndexError:
                band_ix = round(obj.shape[0] / 2)
                obj = obj[band_ix]
        # treat three-band arrays as RGB images
        else:
            obj = np.dstack([channel for channel in obj])
    # upcast integer data types < 32-bit to prevent unhelpful wraparound
    if (obj.dtype.char in np.typecodes['AllInteger']) and (obj.itemsize <= 2):
        obj = obj.astype(np.int32)
    # convert to unsigned eight-bit integer to make it easy to write
    obj = eightbit(obj, image_clip, purge)
    # unless color_fill is set to None, fill masked elements -- probably
    # special constants -- with RGB value defined by mask_color
    if isinstance(obj, np.ma.MaskedArray) and (mask_color is not None):
        obj = colorfill_maskedarray(obj, mask_color)
    image = Image.fromarray(obj)
    if max(obj.shape) > 65500:
        scale = 1
        for n in naturals():
            scale = 1 / n
            if max(obj.shape) * scale <= 65500:
                break
        warnings.warn(
            f"Axis length {max(obj.shape)} > JPEG encoder threshold of "
            f"65500; downsampling browse image to {scale * 100}%."
        )
        image.thumbnail([int(axis * scale) for axis in image.size])
    image.save(outbase + ".jpg")
