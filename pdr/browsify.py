"""functions for producing browse versions of products"""
from pathlib import Path
import pickle
from typing import Any, Sequence, Union, Optional
import warnings

import numpy as np
import pandas as pd
from PIL import Image
import pvl
from pvl.grammar import OmniGrammar, PVLGrammar, ODLGrammar


# noinspection PyArgumentList
def normalize_range(
    image: np.ndarray,
    bounds: Sequence[int] = (0, 1),
    clip: Union[float, tuple[float, float]] = 0,
) -> np.ndarray:
    """
    simple linear min-max scaler that optionally percentile-clips the input at
    clip = (low_percentile, 100 - high_percentile)
    """
    working = image.copy()
    if isinstance(working, np.ma.MaskedArray):
        valid = working[~working.mask]
    else:
        valid = working
    if isinstance(clip, Sequence):
        cheat_low, cheat_high = clip
    else:
        cheat_low, cheat_high = (clip, clip)
    range_min, range_max = bounds
    if cheat_low is not None:
        minimum = np.percentile(valid, cheat_low).astype(image.dtype)
    else:
        minimum = valid.min()
    if cheat_high is not None:
        maximum = np.percentile(valid, 100 - cheat_high).astype(image.dtype)
    else:
        maximum = valid.max()
    if not ((cheat_high is None) and (cheat_low is None)):
        working = np.clip(working, minimum, maximum)
    return range_min + (working - minimum) * (range_max - range_min) / (
        maximum - minimum
    )


def eightbit(
    array: np.array, clip: Union[float, tuple[float, float]] = 0
) -> np.ndarray:
    """
    return an eight-bit version of an array, optionally clipped at min/max
    percentiles
    """
    return np.round(normalize_range(array, (0, 255), clip)).astype(np.uint8)


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
    image_clip: Union[float, tuple[float, float]] = (1, 1),
    mask_color: Optional[tuple[int, int, int]] = (0, 255, 255),
):
    """
    attempts to dump a browse version of a data object, writing it into a file
    type that can be opened with desktop software: .jpg for most arrays, .csv
    for tables, .txt for most other things. if it can't find a reasonable
    translation, it dumps as .pkl (pickled binary blob).
    """
    if isinstance(obj, pvl.collections.OrderedMultiDict):
        _browsify_pds3_label(obj, outbase)
    elif isinstance(obj, np.recarray):
        _browsify_recarray(obj, outbase)
    elif isinstance(obj, np.ndarray):
        _browsify_array(obj, outbase, image_clip, mask_color)
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
        # warnings.warn(
        #     f"pvl will not dump; {e}; writing to {outbase}.badpvl.txt"
        # )
        # # if that fails, just dump them as text
        # with open(outbase + ".badpvl.txt", "w") as file:
        #     file.write(str(obj))
        pass


def _browsify_array(
    obj: np.ndarray,
    outbase: str,
    image_clip: Union[float, tuple[float, float]] = (1, 1),
    mask_color: Optional[tuple[int, int, int]] = (0, 255, 255),
):
    # attempt to turn arrays into .jpg image files
    if len(obj.shape) == 3:
        # for multiband arrays that are not three-band, only export a
        # single band, the "middle" one
        if obj.shape[0] != 3:
            warnings.warn("dumping only middle band of this image")
            middle_band_index = round(obj.shape[0] / 2)
            obj = obj[middle_band_index]
        # treat three-band arrays as RGB images
        else:
            obj = np.dstack([channel for channel in obj])
    # upcast integer data types < 32-bit to prevent unhelpful wraparound
    if obj.dtype in (np.uint8, np.int16):
        obj = obj.astype(np.int32)
    # convert to unsigned eight-bit integer to make it easy to write
    uint_array = eightbit(obj, image_clip)
    # unless color_fill is set to None, fill masked elements -- probably
    # special constants -- with RGB value defined by mask_color
    if isinstance(uint_array, np.ma.MaskedArray) and (mask_color is not None):
        uint_array = colorfill_maskedarray(uint_array, mask_color)
    Image.fromarray(uint_array).save(outbase + ".jpg")
