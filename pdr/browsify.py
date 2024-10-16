"""functions for producing browse versions of products"""
from numbers import Number
from pathlib import Path
import pickle
from typing import Any, Optional, Sequence, TYPE_CHECKING, Union
import warnings

from dustgoggles.func import naturals
import numpy as np
import pandas as pd

if TYPE_CHECKING:
    from PIL import Image


def find_masked_bounds(
    image: np.ma.MaskedArray, cheat_low: int, cheat_high: int
) -> tuple[Optional[Number], Optional[Number]]:
    """
    relatively memory-efficient way to perform bound calculations for
    normalize_range on a masked array.
    """
    valid = image[~image.mask].data
    if valid.size == 0:
        return None, None
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
def find_unmasked_bounds(
    image: np.ndarray, cheat_low: int, cheat_high: int
) -> tuple[Number, Number]:
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


# NOTE: the following two functions are sort-of-vendored from
# marslab.imgops.imgutils.
def normalize_range(
    image: np.ndarray,
    bounds: Sequence[int] = (0, 1),
    clip: Union[float, tuple[float, float]] = 0,
    inplace: bool = False,
    nice_clip: bool = False
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
        if minimum is None:
            return image
    else:
        minimum, maximum = find_unmasked_bounds(image, cheat_low, cheat_high)
    if nice_clip is True and minimum == maximum:  # scaling was too intense
        return image
    if not ((cheat_high is None) and (cheat_low is None)):
        if inplace is True:
            image = np.clip(image, minimum, maximum, out=image)
        else:
            image = np.clip(image, minimum, maximum)
    if inplace is True:
        # perform the operation in-place
        image -= minimum
        image *= range_max - range_min
        if image.dtype.char in np.typecodes["AllInteger"]:
            # this loss of precision is probably better than
            # automatically typecasting it.
            # TODO: detect rollover cases, etc.
            image //= maximum - minimum
        else:
            image /= maximum - minimum
        image += range_min
        return image
    return (
        (image - minimum) *
        ((range_max - range_min) / (maximum - minimum))
        + range_min
    )


def eightbit(
    array: np.array,
    clip: Union[float, tuple[float, float]] = 0,
    inplace: bool = False,
    nice_clip: bool = False
) -> np.ndarray:
    """
    return an eight-bit version of an array, optionally clipped at min/max
    percentiles. if inplace is True, normalization may transform the original
    array, with attendant memory savings and destructiveness.
    """
    with warnings.catch_warnings():
        # we do not care about masked out-of-bounds values; it's why we masked
        warnings.filterwarnings(action="ignore", message=".*invalid value en*")
        return np.round(
            normalize_range(array, (0, 255), clip, inplace, nice_clip)
        ).astype(np.uint8)


def colorfill_maskedarray(
    masked_array: np.ma.MaskedArray,
    color: Union[int, tuple[int, int, int]] = (0, 255, 255),
) -> np.ndarray:
    """
    masked_array: 2-D masked array or a 3-D masked array with last axis of
    length 3. for likely uses, this should probably be 8-bit unsigned integer.
    color: optionally-specified RGB color (default cyan)
    return a 2-D or 3-D array with masked values filled with color.
    """
    if isinstance(color, int):
        return masked_array.filled(color)
    if len(masked_array.shape) == 2:
        return np.dstack([masked_array.filled(color[ix]) for ix in range(3)])
    if masked_array.shape[-1] != 3:
        raise ValueError("3-D arrays must have last axis of length = 3")
    return np.dstack(
        [masked_array[:, :, ix].filled(color[ix]) for ix in range(3)]
    )


def browsify(obj: Any, outbase: Union[str, Path], **dump_kwargs) -> None:
    """
    attempts to dump a browse version of a data object, writing it into a file
    type that can be opened with desktop software: .jpg for most arrays, .csv
    for tables, .txt for most other things. if it can't find a reasonable
    translation, it attempts to dump it as .pkl (a serialized binary 'blob').
    """
    outbase = str(outbase)
    if isinstance(obj, np.recarray):
        _browsify_recarray(obj, outbase, **dump_kwargs)
    elif isinstance(obj, np.ndarray):
        if len(obj.shape) == 1:
            pd.DataFrame(obj).to_csv(outbase + ".csv", index=False)
        else:
            _browsify_array(obj, outbase, **dump_kwargs)
    elif isinstance(obj, pd.DataFrame):
        if len(obj) == 1:
            # noinspection PyTypeChecker
            obj.T.to_csv(outbase + ".csv"),
        else:
            obj.to_csv(outbase + ".csv")
    elif obj is None:
        return
    elif "to_string" in dir(obj):  # probably an XML ElementTree interface
        with open(outbase + ".xml", "w") as stream:
            stream.write(obj.to_string())
    else:
        # this should usually work. it may need another backup binary blob
        # pickler for really weird binary objects.
        with open(outbase + ".txt", "w") as stream:
            stream.write(str(obj))


# TODO: this needs to be like 'browsify_structured_array' to handle some
#  nested dtypes that aren't recarrays.
def _browsify_recarray(obj: np.recarray, outbase: str, **_):
    """
    Some tabular data with column groups ends up as numpy recarray, which is
    challenging to turn into a useful .csv file in some cases. This _tries_ to
    save it as a CSV file, and if it fails, punts and pickles it.
    """
    try:
        obj = pd.DataFrame.from_records(obj)
        # noinspection PyTypeChecker
        obj.to_csv(outbase + ".csv")
    except ValueError:
        pickle.dump(obj, open(outbase + "_nested_recarray.pkl", "wb"))


def _browsify_array(
    obj: np.ndarray,
    outbase: str,
    purge: bool = False,
    image_clip: Union[float, tuple[float, float], None] = None,
    mask_color: Optional[tuple[int, int, int]] = (0, 255, 255),
    band_ix: Optional[int] = None,
    save: bool = True,
    override_rgba: bool = False,
    image_format: str = "jpg",
    slice_axis: int = 0,
    **_,
) -> 'Union[Image.Image, list[Optional[Image.Image]]]':
    """
    Attempt to render (and optionally save) an ndarray as one or more
    images.
    """
    nice_clip = image_clip is None
    image_clip = (1, 1) if image_clip is None else image_clip
    if len(obj.shape) == 3:
        obj = _format_multiband_image(obj, band_ix, override_rgba, slice_axis)
    if not isinstance(obj, tuple):
        return _render_array(
            obj,
            outbase,
            purge,
            image_clip,
            mask_color,
            save,
            image_format,
            nice_clip
        )
    results = []
    for ix, band in enumerate(obj):
        result = _render_array(
            band,
            f"{outbase}_{ix}",
            purge,
            image_clip,
            mask_color,
            save,
            image_format,
            nice_clip
        )
        results.append(result)
    return results


def _render_array(
    obj: np.ndarray,
    outbase: str,
    purge: bool,
    image_clip: Union[float, tuple[float, float]],
    mask_color: Union[int, tuple[int, int, int]],
    save: bool,
    image_format: str,
    nice_clip: bool
) -> 'Optional[Image.Image]':
    """
    Handler function for array-rendering pipeline, used by `browsify()` on
    most ndarrays and by `show()` always. Render an ndarray as a PIL Image,
    optionally clipping and masking it. If `save` is True, save it to disk;
    if False, return it.
    """
    try:
        from PIL import Image
    except ImportError:
        raise ModuleNotFoundError(
            "Rendering browse images requires the optional pillow dependency."
        )

    # upcast integer data types < 32-bit to prevent unhelpful wraparound
    if (obj.dtype.char in np.typecodes["AllInteger"]) and (obj.itemsize <= 2):
        obj = obj.astype(np.int32)
    # convert to unsigned eight-bit integer to make it easy to write
    obj = eightbit(obj, image_clip, purge, nice_clip)
    # unless color_fill is set to None, fill masked elements -- probably
    # special constants -- with RGB value defined by mask_color
    if isinstance(obj, np.ma.MaskedArray) and (mask_color is not None):
        obj = colorfill_maskedarray(obj, mask_color)
    image = Image.fromarray(obj)
    # TODO: this might be an excessively hacky way to implement Data.show(),
    #  probably split off the image-generating stuff above into a separate
    #  function
    if save is False:
        return image
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
    image.save(f"{outbase}.{image_format}")


def _format_as_rgb(obj):
    """"""
    if isinstance(obj, np.ma.MaskedArray):
        return np.ma.dstack([channel for channel in obj[0:3]])
    else:
        return np.dstack([channel for channel in obj[0:3]])


def _format_multiband_image(obj, band_ix, override_rgba, slice_axis):
    """
    helper function for _browsify_array -- truncate, stack, or burst
    multiband images and send for further processing.
    """
    if slice_axis != 0:
        obj = obj.swapaxes(0, slice_axis)
    if (obj.shape[0] not in (3, 4)) or (override_rgba is True):
        if band_ix == "burst":
            return tuple([obj[ix] for ix in range(obj.shape[0])])
        return _format_as_single_band(band_ix, obj)
    # treat 3/4 band arrays as rgb(a) images
    if band_ix is not None:
        warnings.warn(
            "treating image as RGB & ignoring band_ix argument; "
            "pass override_rgba=True to override this behavior"
        )
    if obj.shape[0] == 4:
        warnings.warn(
            "transparency not supported, removing 4th (alpha) channel"
        )
    return _format_as_rgb(obj)


def _format_as_single_band(band_ix, obj):
    """
    for multiband arrays that are not presumably rgb(a), or if we have been
    instructed to by the override_rgba argument, only export a single band.
    """
    middle_ix = round(obj.shape[0] / 2)
    if band_ix is None:
        # by default, dump the middle band.
        warnings.warn(f"dumping only band {middle_ix} of this image")
        return obj[middle_ix]
    # if the band_ix argument has been passed, dump that band if possible
    try:
        return obj[band_ix]
    except IndexError:
        warnings.warn(
            f"band_ix={band_ix} does not exist, dumping band {middle_ix}"
        )
        return obj[middle_ix]
