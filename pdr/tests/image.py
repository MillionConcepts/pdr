import gzip
import os

import numpy as np

from pdr.np_utils import (
    make_c_contiguous,
    casting_to_float,
    np_from_buffered_io,
    ibm32_to_np_f32,
    ibm64_to_np_f64, enforce_order_and_object
)

RNG = np.random.default_rng()


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
    arr = RNG.poisson(20, (100, 100)).astype(np.uint8)
    with gzip.open("arr.img.gz", "wb") as stream:
        stream.write(arr.tobytes())
    buf = gzip.open("arr.img.gz", "rb")
    in1 = np_from_buffered_io(buf, np.dtype('b'))
    assert np.all(in1.reshape(arr.shape) == arr)
    in2 = np_from_buffered_io(buf, np.dtype('b'), 10, 10)
    assert np.all(in2 == arr.ravel()[10:20])
    buf.close()
    os.unlink("arr.img.gz")


def test_enforce_order_and_object():
    gross = np.dtype([('f1', 'V4'), ('f2', 'i2'), ('f3', '>i2')])
    grossarray = np.array([(b'\x00\x00\x00\x01', 12, 12)], dtype=gross)
    enforced = enforce_order_and_object(grossarray)
    assert np.all(enforced == grossarray)
    assert enforced.dtype[0] == np.dtype('O')
    assert enforced.dtype[2] == np.dtype('i2')


def test_ibm_to_np():
    assert ibm32_to_np_f32(np.frombuffer(b"\x00\x00\x01\xc2", 'i4')) == -1
    assert ibm64_to_np_f64(
        np.frombuffer(b"\x00\x00\x00\x00\x00\x00\x01\xc2", 'i8')
    ) == -1


test_ibm_to_np()
test_np_from_buffered_io()
make_contiguous()
is_casting_to_float()
test_enforce_order_and_object()
