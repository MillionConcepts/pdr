from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from pdr.browsify import (
    find_masked_bounds,
    find_unmasked_bounds,
    normalize_range,
    eightbit,
    colorfill_maskedarray,
    browsify,
)

RNG = np.random.default_rng()
# NOTE: all these tests have miniscule chances of randomly failing.


def test_find_masked_bounds():
    array = np.ma.masked_outside(RNG.poisson(10, (1024, 1024)), 1, 20)
    bounds = find_masked_bounds(array, 0, 0)
    assert bounds == (1, 20)
    bounds2 = find_masked_bounds(array, 10, 10)
    assert bounds2[0] > 1
    assert bounds2[1] < 20


def test_find_unmasked_bounds():
    array, _ = np.indices((100, 100))
    bounds = find_unmasked_bounds(array, 0, 0)
    assert bounds == (0, 99)
    bounds2 = find_unmasked_bounds(array, 10, 10)
    assert bounds2[0] == 9
    assert bounds2[1] == 89


def test_normalize_range():
    array = RNG.poisson(50, (1024, 1024))
    norm = normalize_range(array)
    assert norm.min() == 0
    assert norm.max() == 1
    norm2 = normalize_range(array, clip=10)
    assert norm2.std() > norm.std()


def test_eightbit():
    array = RNG.poisson(100, (1024, 1024))
    eight = eightbit(array, 10)
    assert eight.min() == 0
    assert eight.max() == 255
    assert eight.dtype == np.dtype("uint8")
    assert eight.std() / eight.mean() > array.std() / array.mean()


def test_colorfill_maskedarray():
    arr = RNG.poisson(100, (1024, 1024))
    masked = np.ma.masked_outside(arr, 10, 90)
    filled = colorfill_maskedarray(masked)
    assert np.equal(filled[masked.mask], np.array([0, 255, 255])).all()


def test_browsify_df():
    obj = pd.DataFrame({"a": [1, 2], "b": ["cat", "dog"]})
    try:
        browsify(obj, "temp")
        df = pd.read_csv("temp.csv")
        assert (df["a"] == [1, 2]).all()
        assert (df["b"] == ["cat", "dog"]).all()
    finally:
        Path("temp.csv").unlink(missing_ok=True)


def test_browsify_array():
    arr = np.ma.masked_outside(RNG.poisson(100, (1024, 1024)), 10, 90)
    try:
        browsify(arr, "temp")
        im = Image.open("temp.jpg")
        assert im.size == (1024, 1024)
        # compression artifacts etc. mean it's not precisely equal
        assert (
            np.abs(
                np.subtract(
                    np.asarray(im)[arr.mask], np.array([0, 255, 255])
                ).mean()
            )
            < 5
        )
    finally:
        Path("temp.jpg").unlink(missing_ok=True)
