"""
This test is a modified version of the `unittest` class
offered in vax.py from pds-tools
(https://github.com/SETI/pds-tools).

It was originally authored by Mark Showalter and released under the Apache-2.0
license, copyright SETI. As such, it carries all terms of that license
and copyright in addition to the terms of the BSD-3 Clause license, copyright
Million Concepts, that apply to pdr as a whole, including our Contributions
to this module.

Million Concepts explicitly makes no claim to the SETI name or trademarks.
"""


import numpy as np

from pdr.vax import from_vax32, to_vax32


def test_vax_things():
    BIGINT = 2**24  # all conversions should be good to at least 24 bits
    SCALE = 1.0 / BIGINT
    EXPMIN = -125
    EXPMAX = 127

    # Single-value inversion tests

    for k in range(1000):
        mantissa = np.random.randint(-BIGINT, BIGINT) * SCALE
        exponent = np.random.randint(EXPMIN, EXPMAX)
        ieee = mantissa * 2.0**exponent

        # Scalar
        result = from_vax32(to_vax32(ieee))
        assert result == ieee
        assert np.isscalar(result)
        assert isinstance(result, np.float32)

        # Shapeless array
        arg = np.array(ieee, dtype="<f4")
        result = from_vax32(to_vax32(arg))
        assert result == arg
        assert not np.isscalar(result)
        assert isinstance(result, np.ndarray)
        assert result.shape == ()
        assert result.dtype == np.dtype("<f4")

        # Array of shape (1,)
        arg = np.array([ieee], dtype="<f4")
        result = from_vax32(to_vax32(arg))
        assert np.all(result == arg)
        assert not np.isscalar(result)
        assert isinstance(result, np.ndarray)
        assert result.shape == (1,)
        assert result.dtype == np.dtype("<f4")

        # Array of shape (1,1)
        arg = np.array([[ieee]], dtype="<f4")
        result = from_vax32(to_vax32(arg))
        assert np.all(result == arg)
        assert not np.isscalar(result)
        assert isinstance(result, np.ndarray)
        assert result.shape == (1, 1)
        assert result.dtype == np.dtype("<f4")

    # Array inversion tests
    for k in range(10):
        for shape in [
            (7,),
            (7, 7),
            (7, 7, 7),
            (4, 1),
            (4, 2),
            (4, 3),
            (3,),
            (3, 1),
            (3, 1, 1),
            (1, 3),
            (1, 3, 1),
            (1, 1, 3),
            (1, 3, 1, 1, 1, 1),
        ]:
            mantissa = np.random.randint(-BIGINT, BIGINT, size=shape) * SCALE
            exponent = np.random.randint(EXPMIN, EXPMAX, size=shape)
            ieee = (mantissa * 2.0**exponent).astype("<f4")

            result = from_vax32(to_vax32(ieee))
            assert isinstance(result, np.ndarray)
            assert result.shape == ieee.shape
            assert result.dtype == np.dtype("<f4")
            assert np.all(result == ieee)

    # Single-value buffer, memoryview, bytes, bytearray, str
    for k in range(100):
        mantissa = np.random.randint(-BIGINT, BIGINT) * SCALE
        exponent = np.random.randint(EXPMIN, EXPMAX)
        ieee = mantissa * 2.0**exponent

        # memoryview
        vax32 = to_vax32(ieee)
        result = from_vax32(vax32.data)
        assert np.isscalar(result)
        assert result == ieee

        # bytes
        result = from_vax32(bytes(vax32.data))
        assert np.isscalar(result)
        assert result == ieee

        # bytearray
        result = from_vax32(bytearray(vax32.data))
        assert np.isscalar(result)
        assert result == ieee

        # string
        result = from_vax32(str(vax32.data, encoding="latin8"))
        assert np.isscalar(result)
        assert result == ieee

    # Multiple-value buffer, memoryview, bytes, bytearray, str
    for k in range(100):
        size = np.random.randint(2, 21)
        mantissa = np.random.randint(-BIGINT, BIGINT, size=size) * SCALE
        exponent = np.random.randint(EXPMIN, EXPMAX, size=size)
        ieee = (mantissa * 2.0**exponent).astype("<f4")

        # buffer (Python 2) or memoryview (Python 3)
        vax32 = to_vax32(ieee)
        result = from_vax32(vax32.data)
        assert result.shape == ieee.shape
        assert np.all(result == ieee)

        # bytes
        result = from_vax32(bytes(vax32.data))
        assert result.shape == ieee.shape
        assert np.all(result == ieee)

        # bytearray
        result = from_vax32(bytearray(vax32.data))
        assert result.shape == ieee.shape
        assert np.all(result == ieee)

        # string
        result = from_vax32(str(vax32.data, encoding="latin8"))
        assert result.shape == ieee.shape
        assert np.all(result == ieee)

    assert from_vax32(
        int('0b10000000010000000000000000000000', 2).to_bytes(4, 'big')
    ) == 1
