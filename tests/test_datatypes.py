from itertools import product

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
    numpy_dtype_strings = []
    for dt, depth in product(pds3_data_types, bit_depths):
        try:
            numpy_dtype_strings.append(sample_types(dt, depth, True))
        except NotImplementedError:
            assert ("REAL" in dt) and (depth in (1, 2))
    expected_dtype_strings = [
        # CHARACTER
        "S1",
        "S2",
        "S4",
        "S8",
        # IEEE_REAL
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
    ]
    assert numpy_dtype_strings == expected_dtype_strings
