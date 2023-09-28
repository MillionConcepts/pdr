import gzip
import os
from gzip import GzipFile

import numpy as np

from pdr.np_utils import make_c_contiguous, casting_to_float, np_from_buffered_io


def make_contiguous():
    arr = np.arange(0, 100, 5)
    arr = arr[0:-1:2]
    assert arr.flags['C_CONTIGUOUS'] is False
    arr = make_c_contiguous(arr)
    assert arr.flags['C_CONTIGUOUS'] is True


def is_casting_to_float():
    uint8 = np.arange(0, 100, dtype=np.uint8)
    assert casting_to_float(uint8, 1.1)
    assert not casting_to_float(uint8, 1)


def test_np_from_buffered_io():
    arr = np.random.poisson(20, (100, 100)).astype(np.uint8)
    with gzip.open("arr.img.gz", "wb") as stream:
        stream.write(arr.tobytes())
    buf = gzip.open("arr.img.gz", "rb")
    in1 = np_from_buffered_io(buf, np.dtype('b'))
    assert np.all(in1.reshape(arr.shape) == arr)
    in2 = np_from_buffered_io(buf, np.dtype('b'), 10, 10)
    assert np.all(in2 == arr.ravel()[10:20])
    buf.close()
    os.unlink("arr.img.gz")


test_np_from_buffered_io()
make_contiguous()
is_casting_to_float()
