import gzip
import os

import numpy as np

from pdr.np_utils import (
    make_c_contiguous,
    casting_to_float,
    np_from_buffered_io,
    ibm32_to_np_f32,
    ibm64_to_np_f64,
    enforce_order_and_object,
)

RNG = np.random.default_rng()


def test_make_c_contiguous():
    arr = np.arange(0, 100, 5)
    arr = arr[0:-1:2]
    assert arr.flags["C_CONTIGUOUS"] is False
    arr = make_c_contiguous(arr)
    assert arr.flags["C_CONTIGUOUS"] is True


def test_casting_to_float():
    uint8 = np.arange(0, 100, dtype=np.uint8)
    assert casting_to_float(uint8, 1.1)
    assert not casting_to_float(uint8, 1)


def test_np_from_buffered_io(tmp_path):
    arr = RNG.poisson(20, (100, 100)).astype(np.uint8)
    fpath = tmp_path / "arr.img.gz"
    with gzip.open(fpath, "wb") as stream:
        stream.write(arr.tobytes())
    with gzip.open(fpath, "rb") as buf:
        in1 = np_from_buffered_io(buf, np.dtype("b"))
        assert np.all(in1.reshape(arr.shape) == arr)
        in2 = np_from_buffered_io(buf, np.dtype("b"), 10, 10)
        assert np.all(in2 == arr.ravel()[10:20])


def test_enforce_order_and_object():
    gross = np.dtype([("f1", "V4"), ("f2", "i2"), ("f3", ">i2")])
    grossarray = np.array([(b"\x00\x00\x00\x01", 12, 12)], dtype=gross)
    enforced = enforce_order_and_object(grossarray)
    assert np.all(enforced == grossarray)
    assert enforced.dtype[0] == np.dtype("O")
    assert enforced.dtype[2] == np.dtype("i2")
    enforced2 = enforce_order_and_object(np.array([b"\x00"], dtype="V"))
    assert enforced2[0] == b"\x00"
    assert enforced2.dtype == np.dtype("O")
    enforced3 = enforce_order_and_object(np.array([3], dtype=">i2"))
    assert enforced3[0] == 3
    assert enforced3.dtype == np.dtype("i2")
    enforced4 = enforce_order_and_object(np.array([3], dtype=">i2"))
    assert enforced4[0] == 3
    assert enforced4.dtype == np.dtype("i2")


def test_ibm_to_np():
    assert ibm32_to_np_f32(np.frombuffer(b"\x00\x00\x01\xc2", "i4")) == -1
    assert (
        ibm64_to_np_f64(
            np.frombuffer(b"\x00\x00\x00\x00\x00\x00\x01\xc2", "i8")
        )
        == -1
    )
