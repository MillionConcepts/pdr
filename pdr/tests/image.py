import numpy as np

from pdr.np_utils import make_c_contiguous


def make_contiguous():
    arr = np.arange(0, 100, 5)
    arr = arr[0:-1:2]
    assert arr.flags['C_CONTIGUOUS'] is False
    arr = make_c_contiguous(arr)
    assert arr.flags['C_CONTIGUOUS'] is True
