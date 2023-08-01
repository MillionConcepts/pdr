"""
This module is a modified version of vax.py from pds_tools 
(https://github.com/SETI/pds-tools).

It was originally authored by Mark Showalter and released under the Apache-2.0
license, copyright SETI. As such, it carries all terms of that license
and copyright in addition to the terms of the BSD-3 Clause license, copyright
Million Concepts, that apply to pdr as a whole, including our Contributions
to this module.

Million Concepts explicitly makes no claim to the SETI name or trademarks.
"""

############################################################################
# vax.py: Conversions between Vax single-precision floats IEEE floats
############################################################################

import numpy as np


def from_vax32(data):
    """Interprets an arbitrary byte string or NumPy array as Vax
    single-precision floating-point binary values, and returns the equivalent
    array as IEEE values.
    """

    # Convert a string to bytes
    if isinstance(data, str):
        data = bytes(data, encoding='latin8')

    # Handle memoryview
    if isinstance(data, memoryview):
        data = bytes(data)

    # Convert the object to an even number of 2-byte elements
    if isinstance(data, (bytes, bytearray)):
        if len(data) % 4 != 0:
            raise ValueError('data size is not a multiple of 4 bytes')

        pairs = np.frombuffer(data, dtype='uint16')
        pairs = pairs.reshape(pairs.size//2, 2)
        newshape = (len(data) // 4,)    # array shape after conversion
        scalar = (len(data) == 4)       # True to convert to scalar at the end
        shapeless = False

    else:
        # Convert to array, or a single-element array for a scalar
        scalar = not isinstance(data, np.ndarray)
        if scalar:                      # True to convert back to scalar at end
            array = np.array([data], dtype='<f4')
        else:
            shapeless = data.shape == ()    # True to convert back to shape ()
            if shapeless:
                array = data.ravel().astype('<f4')
            else:
                array = data.astype('<f4')

        if (array.size * array.itemsize) % 4 != 0:
            raise ValueError('data size is not a multiple of 4 bytes')

        pairs = array.view('uint16')

        # Determine array shape after conversion
        if array.itemsize == 1:
            if array.shape[-1] % 4 != 0:
                raise ValueError('last axis size is not a multiple of 4 bytes')
            newshape = array.shape[:-1] + (array.shape[-1] // 4,)

        elif array.itemsize == 2:
            if array.shape[-1] % 2 != 0:
                raise ValueError('last axis size is not a multiple of 4 bytes')
            newshape = array.shape[:-1] + (array.shape[-1] // 2,)

        elif array.itemsize == 4:
            newshape = array.shape + (1,)

        else:
            newshape = array.shape + (array.itemsize//4,)

        if newshape[-1] == 1:
            newshape = newshape[:-1]

    # Perform a pairwise swap of the two-byte elements
    pairs = pairs.reshape(newshape + (2,))
    swapped = np.empty(pairs.shape, dtype='uint16')
    swapped[...,:] = pairs[...,::-1]

    # The results are in LSB IEEE format aside from a scale factor of four
    ieee = swapped.view('<f4') / 4.

    if scalar:
        return ieee[0,0]            # current shape is (1,1)
    elif shapeless:
        return ieee.reshape(())
    else:
        return ieee.reshape(newshape)


def to_vax32_bytes(array):
    """Converts an arbitrary array of numbers into Vax single precision and
    returns the resulting array as a byte string.
    """

    pre_swapped = (4. * array).ravel().astype('<f4')
    paired_view = pre_swapped.view('uint16')

    paired_view = paired_view.reshape((paired_view.size//2, 2))
    swapped = paired_view[:,::-1].copy()

    return swapped.tobytes()

def to_vax32(array):
    """Converts an arbitrary array of numbers into Vax single precision, and
    then returns an array of the same shape. Note that the numeric values in the
    array will not be usable.
    """

    scalar = not isinstance(array, np.ndarray)
    if scalar:                      # True to convert back to scalar at end
        array = np.array([array], dtype='<f4')
    else:
        array = array.astype('<f4')

    data = to_vax32_bytes(array)
    output = np.frombuffer(data, dtype='<f4')

    if scalar:
        return output[0]
    else:
        return output.reshape(array.shape)


################################################################################
# UNIT TESTS
################################################################################

import unittest


class Test_Vax(unittest.TestCase):

  def runTest(self):

    BIGINT = 2**24      # all conversions should be good to at least 24 bits
    SCALE = 1. / BIGINT
    EXPMIN = -125
    EXPMAX = 127

    # Single-value inversion tests

    for k in range(1000):
        mantissa = np.random.randint(-BIGINT, BIGINT) * SCALE
        exponent = np.random.randint(EXPMIN, EXPMAX)
        ieee = mantissa * 2.**exponent

        # Scalar
        result = from_vax32(to_vax32(ieee))
        self.assertEqual(result, ieee)
        self.assertTrue(np.isscalar(result))
        self.assertTrue(isinstance(result, np.float32))

        # Shapeless array
        arg = np.array(ieee, dtype='<f4')
        result = from_vax32(to_vax32(arg))
        self.assertEqual(result, arg)
        self.assertFalse(np.isscalar(result))
        self.assertTrue(isinstance(result, np.ndarray))
        self.assertTrue(result.shape == ())
        self.assertTrue(result.dtype == np.dtype('<f4'))

        # Array of shape (1,)
        arg = np.array([ieee], dtype='<f4')
        result = from_vax32(to_vax32(arg))
        self.assertTrue(np.all(result == arg))
        self.assertFalse(np.isscalar(result))
        self.assertTrue(isinstance(result, np.ndarray))
        self.assertTrue(result.shape == (1,))
        self.assertTrue(result.dtype == np.dtype('<f4'))

        # Array of shape (1,1)
        arg = np.array([[ieee]], dtype='<f4')
        result = from_vax32(to_vax32(arg))
        self.assertTrue(np.all(result == arg))
        self.assertFalse(np.isscalar(result))
        self.assertTrue(isinstance(result, np.ndarray))
        self.assertTrue(result.shape == (1,1))
        self.assertTrue(result.dtype == np.dtype('<f4'))

    # Array inversion tests
    for k in range(10):
        for shape in [(7,), (7,7), (7,7,7), (4,1), (4,2), (4,3),
                      (3,), (3,1), (3,1,1), (1,3), (1,3,1), (1,1,3),
                      (1,3,1,1,1,1)]:
            mantissa = np.random.randint(-BIGINT, BIGINT, size=shape) * SCALE
            exponent = np.random.randint(EXPMIN, EXPMAX, size=shape)
            ieee = (mantissa * 2.**exponent).astype('<f4')

            result = from_vax32(to_vax32(ieee))
            self.assertTrue(isinstance(result, np.ndarray))
            self.assertTrue(result.shape == ieee.shape)
            self.assertTrue(result.dtype == np.dtype('<f4'))
            self.assertTrue(np.all(result == ieee))

    # Single-value buffer, memoryview, bytes, bytearray, str
    for k in range(100):
        mantissa = np.random.randint(-BIGINT, BIGINT) * SCALE
        exponent = np.random.randint(EXPMIN, EXPMAX)
        ieee = mantissa * 2.**exponent

        # memoryview
        vax32 = to_vax32(ieee)
        result = from_vax32(vax32.data)
        self.assertTrue(np.isscalar(result))
        self.assertEqual(result, ieee)

        # bytes
        result = from_vax32(bytes(vax32.data))
        self.assertTrue(np.isscalar(result))
        self.assertEqual(result, ieee)

        # bytearray
        result = from_vax32(bytearray(vax32.data))
        self.assertTrue(np.isscalar(result))
        self.assertEqual(result, ieee)

        # string
        result = from_vax32(str(vax32.data, encoding='latin8'))
        self.assertTrue(np.isscalar(result))
        self.assertEqual(result, ieee)

    # Multiple-value buffer, memoryview, bytes, bytearray, str
    for k in range(100):
        size = np.random.randint(2,21)
        mantissa = np.random.randint(-BIGINT, BIGINT, size=size) * SCALE
        exponent = np.random.randint(EXPMIN, EXPMAX, size=size)
        ieee = (mantissa * 2.**exponent).astype('<f4')

        # buffer (Python 2) or memoryview (Python 3)
        vax32 = to_vax32(ieee)
        result = from_vax32(vax32.data)
        self.assertTrue(result.shape == ieee.shape)
        self.assertTrue(np.all(result == ieee))

        # bytes
        result = from_vax32(bytes(vax32.data))
        self.assertTrue(result.shape == ieee.shape)
        self.assertTrue(np.all(result == ieee))

        # bytearray
        result = from_vax32(bytearray(vax32.data))
        self.assertTrue(result.shape == ieee.shape)
        self.assertTrue(np.all(result == ieee))

        # string
        if PYTHON2:
            result = from_vax32(str(vax32.data))
        else:
            result = from_vax32(str(vax32.data, encoding='latin8'))
        self.assertTrue(result.shape == ieee.shape)
        self.assertTrue(np.all(result == ieee))

    # Try some real-world Vax data from
    #   VGISS_5xxx/VGISS_5214/CALIB/MIPL/VGRSCF.DAT
    #
    # array = np.fromfile('.../VGRSCF.DAT', dtype='uint8')[780:]

    uints = np.array([
       104,  64,  39,  49,  96,  64, 156, 196,  60,  64,   8, 172, 128,
        64,   0,   0, 125,  64,  27,  47, 128,  64,   0,   0, 131,  64,
        10, 215,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0, 110,  64,   4,  86,  77,  64,
       242, 210, 128,  64,   0,   0, 134,  64,  25,   4, 110,  64,   4,
        86, 132,  64,  88,  57, 132,  64,  88,  57,   8,  65, 176, 114,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,  32,  54,  47,  49,  53,  47,  56,  53,
       128,  64,   0,   0, 136,  64,  57, 180, 130,  64, 229, 208, 101,
        64, 203, 161, 128,  64,   0,   0, 128,  64,  78,  98, 128,  64,
         0,   0, 125,  64,  27,  47,  86,  65, 123,  20, 100,  65, 166,
       155,  90,  65, 131, 192,  64,  65,   0,   0, 128,  64,   0,   0,
        86,  65,  82, 184,  86,  65, 123,  20,  83,  65,  70, 182,  88,
        66,  53,  94, 103,  66, 111,  18,  93,  66, 184,  30,  66,  66,
       123,  20, 128,  64,   0,   0,  89,  66,  12,   2,  88,  66,  53,
        94,  85,  66, 231, 251,  88,  66,  53,  94, 103,  66, 111,  18,
        93,  66, 184,  30,  66,  66, 123,  20, 128,  64,   0,   0,  89,
        66,  12,   2,  88,  66,  53,  94,  85,  66, 231, 251, 105,  64,
        94, 186,  98,  64, 211,  77, 128,  64,   0,   0, 118,  64,  25,
         4, 105,  64,  94, 186, 129,  64, 252, 169, 129,  64, 252, 169,
        73,  65, 252, 169,  67,  65, 188, 116,  61,  65, 125,  63,  86,
        65, 123,  20,  77,  65, 143, 194,  67,  65, 188, 116,  88,  65,
       254, 212,  88,  65, 254, 212,  40,  66, 215, 163,  69,  66,  55,
       137,  63,  66, 150,  67,  88,  66,  53,  94,  79,  66, 231, 251,
        69,  66,  55, 137,  91,  66,   2,  43,  91,  66,   2,  43,  42,
        67, 170, 113,  69,  66,  55, 137,  63,  66, 150,  67,  88,  66,
        53,  94,  79,  66, 231, 251,  69,  66,  55, 137,  91,  66,   2,
        43,  91,  66,   2,  43,  42,  67, 170, 113, 128,  64,   0,   0,
       104,  64,  39,  49,  96,  64, 156, 196,  60,  64,   8, 172, 128,
        64,   0,   0, 125,  64,  27,  47, 128,  64,   0,   0, 131,  64,
        10, 215,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0, 110,  64,   4,  86,  77,  64,
       242, 210, 128,  64,   0,   0, 134,  64,  25,   4, 110,  64,   4,
        86, 132,  64,  88,  57, 132,  64,  88,  57,   8,  65, 176, 114,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,   0,
         0,   0,   0,   0,   0,  32,  50,  47,  48,  50,  47,  56,  54],
      dtype='uint8')

    ieee = from_vax32(uints)
    truth = np.array([1.   , 1.068, 1.022, 0.897, 1.   , 1.003, 1.   , 0.989])
    self.assertTrue(np.all(truth.astype('<f4') == ieee[65:73]))

    truth = np.array([3.345, 3.572, 3.418, 3.   , 1.   , 3.355, 3.345, 3.308])
    self.assertTrue(np.all(truth.astype('<f4') == ieee[73:81]))

    truth = np.array([13.523, 14.442, 13.82 , 12.13 ,  1.   , 13.563, 13.523, 13.374])
    self.assertTrue(np.all(truth.astype('<f4') == ieee[81:89]))
    self.assertTrue(np.all(truth.astype('<f4') == ieee[89:97]))

################################################################################
# Perform unit testing if executed from the command line
################################################################################

if __name__ == "__main__":
    unittest.main()

################################################################################
