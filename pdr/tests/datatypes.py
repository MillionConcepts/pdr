from itertools import product, starmap

from pdr.datatypes import sample_types


def test_sample_types():
    pds3_data_types = {
        "CHARACTER",
        "IEEE_REAL",
        "LSB_INTEGER",
        "LSB_UNSIGNED_INTEGER",
        "MSB_INTEGER",
        "MSB_UNSIGNED_INTEGER",
        "PC_REAL",
        "UNSIGNED_INTEGER",
        "VAX_UNSIGNED_INTEGER",
        "ASCII_REAL",
    }
    bit_depths = [1, 2, 4, 8]
    numpy_dtype_strings = tuple(
        starmap(sample_types, product(pds3_data_types, bit_depths, (True,)))
    )
    assert numpy_dtype_strings == (
        ">f",
        ">f",
        ">f",
        ">d",
        "<B",
        "<H",
        "<u4",
        "<B",
        ">b",
        ">h",
        ">i4",
        ">b",
        "<b",
        "<h",
        "<i4",
        "<b",
        "S1",
        "S2",
        "S4",
        "S8",
        "<B",
        "<H",
        "<u4",
        "<B",
        "S1",
        "S2",
        "S4",
        "S8",
        ">B",
        ">H",
        ">u4",
        ">B",
        "<f",
        "<f",
        "<f",
        "<d",
        ">B",
        ">H",
        ">u4",
        ">B",
    )
