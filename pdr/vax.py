"""
This module is a modified version of vax.py from pds_tools 
(https://github.com/SETI/pds-tools).

It was originally authored by Mark Showalter and released under the Apache-2.0
license, copyright SETI. As such, it carries all terms of that license
and copyright in addition to the terms of the BSD-3 Clause license, copyright
Million Concepts, that apply to pdr as a whole, including our Contributions
to this module.

Million Concepts explicitly makes no claim to the SETI name or trademarks.

############################################################################
# vax.py: Conversions between Vax single-precision floats and IEEE floats
############################################################################
"""

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


# TODO: VAX_REAL_CONVERTERS = {4: vax32_to_np_float32, 8: vax64_to_np_float64}
#  def vax_real_to_np(bytestream, bytewidth):
#     return VAX_REAL_CONVERTERS[bytewidth](bytestream)
