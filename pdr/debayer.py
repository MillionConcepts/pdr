from types import MappingProxyType
from typing import Mapping, Sequence, Union

import numpy as np

# bayer pattern definitions

RGGB_PATTERN = MappingProxyType(
    {
        "red": (0, 0),
        "green_1": (0, 1),
        "green_2": (1, 0),
        "blue": (1, 1),
    }
)


def bilinear_interpolate_subgrid(
    rows: np.ndarray,
    columns: np.ndarray,
    input_array: np.ndarray,
    output_shape: tuple[int, int],
) -> np.ndarray:
    """
    interpolate 2D values to a 2D array, gridding those values
    according to a regular pattern. input array must be of an
    integer or float dtype.

    this is a special case for pixel classes that are defined as unique
    positions within m x n subgrids that tile the coordinate space.
    in particular, it will work for any conventional Bayer pattern,
    when each pattern cell is treated as a separate pixel 'class' (even if
    pixels are of the 'same' color), as well as a variety of more complex
    patterns. use the slower bilinear_interpolate() for general gridded-data
    cases.
    """
    horizontal = np.empty(output_shape, dtype=input_array.dtype)
    vertical = np.empty(output_shape, dtype=input_array.dtype)
    # because of the 'subgrid' assumption, in any row that contains pixels,
    # their column indices are the same (and vice versa)
    for row_ix, row in enumerate(rows):
        horizontal[row] = np.interp(
            np.arange(output_shape[1]),
            columns,
            input_array[row_ix, :],
        )
    for output_column in np.arange(output_shape[1]):
        vertical[:, output_column] = np.interp(
            np.arange(output_shape[0]), rows, horizontal[rows, output_column]
        )
    return vertical


def make_pattern_masks(
    array_shape: Sequence[int],
    bayer_pattern: Mapping[str, Sequence[int]],
    pattern_shape: Sequence[int] = (2, 2),
) -> dict[str, tuple]:
    """
    given (y, x) array shape and a dict of tuples defining grid class names
    and positions,
    generate a dict of array pairs containing y, x coordinates for each
    named grid class in a m x n pattern beginning at the upper-left-hand corner
    of an array of shape shape and extending across the entirety of that array

    supports only m x n patterns (like conventional bayer patterns); not a
    'generalized n-d discrete frequency class sorter' or whatever
    """
    y_coord, x_coord = np.meshgrid(
        np.arange(array_shape[0]), np.arange(array_shape[1])
    )
    masks = {}
    for name, position in bayer_pattern.items():
        y_slice = slice(position[0], None, pattern_shape[0])
        x_slice = slice(position[1], None, pattern_shape[1])
        masks[name] = (
            np.ravel(y_coord[y_slice, x_slice]),
            np.ravel(x_coord[y_slice, x_slice]),
        )
    return masks


def debayer_upsample(
    image: np.ndarray,
    pixel: Union[str, Sequence[str]],
    pattern: Mapping[str, tuple] = RGGB_PATTERN,
    masks: Mapping[str, tuple] = None,
    row_column: Mapping[str, tuple] = None,
) -> np.ndarray:
    """
    debayer and upsample an image, given a bayer pixel name or names and
    either a bayer pattern or explicitly precalculated sets of absolute (and
    optionally relative) coordinates for those pixels. averages arrays if
    more than one pixel name is given.
    TODO: the preamble to this may be excessively convoluted.
    """
    assert not (pattern is None and masks is None), (
        "debayer_upsample() must be passed either a bayer pattern or "
        "precalculated bayer masks."
    )
    if isinstance(pixel, str):
        pixel = [pixel]
    if masks is None:
        # TODO: allow passthrough / autodetection for larger bayer patterns
        masks = make_pattern_masks(image.shape, pattern)
    if row_column is None:
        row_column = {
            pixel: (np.unique(mask[0]), np.unique(mask[1]))
            for pixel, mask in masks.items()
        }
    upsampled_images = []
    for pix in pixel:
        mask = masks[pix]
        if row_column is None:
            rows, columns = np.unique(mask[0]), np.unique(mask[1])
        else:
            rows, columns = row_column[pix]
        subframe = image[mask].reshape(rows.size, columns.size, order="F")
        upsampled_images.append(
            bilinear_interpolate_subgrid(rows, columns, subframe, image.shape)
        )
    if len(upsampled_images) == 1:
        return upsampled_images[0]
    return np.mean(np.dstack(upsampled_images), axis=-1)
