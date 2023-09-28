from itertools import product, starmap

from pdr.datatypes import sample_types


def test_sample_types():
    pds3_data_types = (
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
    )
    bit_depths = [1, 2, 4, 8]
    numpy_dtype_strings = tuple(
        starmap(sample_types, product(pds3_data_types, bit_depths, (True,)))
    )
    expected_dtype_strings = (
        # CHARACTER
        "S1",
        "S2",
        "S4",
        "S8",
        # IEEE_REAL
        # we don't actually support minifloat or half-float,
        # so these are expected to be >f
        ">f",
        ">f",
        ">f",
        ">d",
        # LSB_INTEGER
        "<b",
        "<h",
        "<i4",
        "<i8",
        # LSB_UNSIGNED_INTEGER
        "<B",
        "<H",
        "<u4",
        "<u8",
        # MSB_INTEGER
        ">b",
        ">h",
        ">i4",
        ">i8",
        # MSB_UNSIGNED_INTEGER
        ">B",
        ">H",
        ">u4",
        ">u8",
        # PC_REAL
        "<f",
        "<f",
        "<f",
        "<d",
        # UNSIGNED_INTEGER
        ">B",
        ">H",
        ">u4",
        ">u8",
        # VAX_UNSIGNED_INTEGER
        "<B",
        "<H",
        "<u4",
        "<u8",
        # ASCII_REAL
        "S1",
        "S2",
        "S4",
        "S8",
    )
    assert numpy_dtype_strings == expected_dtype_strings


test_sample_types()