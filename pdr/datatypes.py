"""
definitions of sample types / data types / dtypes / ctypes, file formats
and extensions, associated special constants, and so on.
"""
from itertools import product
from types import MappingProxyType

from pdr.utils import read_hex


def integer_bytes(
    endian: str, signed: bool, sample_bytes: int, for_numpy: bool = False
) -> str:
    """
    translation for inconsistent integer types
    """
    if sample_bytes == 4:
        letter = "l"
    elif sample_bytes == 2:
        letter = "h"
    else:
        letter = "b"
    if signed is False:
        letter = letter.upper()
    if for_numpy is True and sample_bytes == 4:
        letter = "i4" if signed is True else "u4"
    return f"{endian}{letter}"


def determine_byte_order(sample_type):
    if any(sample_type.startswith(s) for s in ("PC", "LSB", "VAX")):
        endian = "<"
    else:
        endian = ">"
    return endian


def sample_types(
    sample_type: str, sample_bytes: int, for_numpy: bool = False
) -> str:
    """
    Defines a translation from PDS data types to Python struct or numpy dtype
    format strings, using both the type and bytes specified (because the
    mapping to type alone is not consistent across PDS3).
    """
    if (("INTEGER" in sample_type) or (sample_type == "BOOLEAN")) and (
        "ASCII" not in sample_type
    ):
        endian = determine_byte_order(sample_type)
        signed = "UNSIGNED" not in sample_type
        return integer_bytes(endian, signed, sample_bytes, for_numpy)
    void = "V" if for_numpy is True else "s"
    _float = "d" if sample_bytes == 8 else "f"
    return {
        "IEEE_REAL": f">{_float}",
        "PC_REAL": f"<{_float}",
        "FLOAT":  f">{_float}",
        "REAL":  f">{_float}",
        "MAC_REAL":  f">{_float}",
        "SUN_REAL":  f">{_float}",
        "MSB_BIT_STRING": f"{void}{sample_bytes}",
        # "Character string representing a real number"
        "ASCII_REAL": f"S{sample_bytes}",
        # ASCII character string representing an integer
        "ASCII_INTEGER": f"S{sample_bytes}",
        # "ASCII character string representing a date in PDS standard format"
        # (e.g. 1990-08-01T23:59:59)
        "DATE": f"S{sample_bytes}",
        "CHARACTER": f"S{sample_bytes}",  # ASCII character string
    }[sample_type]


# "basic" PDS3 special constants
PDS3_CONSTANT_NAMES = (
    "INVALID_CONSTANT",
    "MISSING_CONSTANT",
    "INFINITY_CONSTANT",
    "NOT_APPLICABLE_CONSTANT",
    "NULL_CONSTANT",
    "UNKNOWN_CONSTANT",
)
# some (all?) of these are derived from ISIS properties; these are names they
# take on when they are made explicit in a PDS3 label
PDS3_ISIS_CONSTANT_NAMES = tuple(
    [
        f"{category}{direction}{entity}{prop}"
        for category, direction, entity, prop in product(
            ("CORE_", "BAND_SUFFIX_", "SAMPLE_SUFFIX", "LINE_SUFFIX", ""),
            ("HIGH_", "LOW_"),
            ("INST_", "REPR_"),
            ("NULL", "SATURATION", "SAT"),
        )
    ]
)
# noinspection PyTypeChecker
PDS3_CONSTANT_NAMES = tuple(PDS3_ISIS_CONSTANT_NAMES + PDS3_CONSTANT_NAMES)
# this dictionary contains common "implicit" (not specified in the label)
# special constants. the keys of the dictionary are bits per array element.
# some of these constants are derived from ISIS, others are suggested in the
# PDS3 Standards.
# note that the Standards allow other special constants to exist, undefined in
# the label, determined only by the operating environment of the data provider,
# so there can be no guarantee that other special constants do not exist in
# any particular product.
# the "implicit" use of ISIS constants may in fact be illegal, but appears
# common. also note that some ISIS values collide with Standards-specified
# N/A / UNK / NULL values -- again, we have no way to automatically
# distinguish them, and interpret them as the Standards values when found.
# References:
# PDS3 Standards Reference v3.8, p.172
# (https://pds.nasa.gov/datastandards/pds3/standards/sr/StdRef_20090227_v3.8.pdf)
# GDAL PDS3 driver
# TODO: -32768 is noted in this driver as NULL but defined in the Standards as
#   an N/A value -- should clarify
# (https://github.com/OSGeo/gdal/blob/master/frmts/pds/pdsdataset.cpp)
# ISIS special pixel values
# (https://isis.astrogeology.usgs.gov/Object/Developer/_special_pixel_8h_source.html)


IMPLICIT_PDS3_CONSTANTS = MappingProxyType(
    {
        # we define the uint8 constants but do not by default use them: they
        # are simply too problematic in too many cases.
        "uint8": {"NULL": 0, "ISIS_SAT_HIGH": 255},
        "int16": {
            "N/A": -32768,
            "UNK": 32767,
            "ISIS_LOW_INST_SAT": -32766,
            "ISIS_LOW_REPR_SAT": -32767,
            "ISIS_HIGH_INST_SAT": -32765,
            "ISIS_HIGH_REPR_SAT": -32764,
        },
        "uint16": {
            "NULL": 0,
            "N/A": 65533,
            "UNK": 65534,
            "ISIS_LOW_INST_SAT": 2,
            "ISIS_LOW_REPR_SAT": 1,
            "ISIS_HIGH_INST_SAT": 65534,
            "ISIS_HIGH_REPR_SAT": 65535,
        },
        # note that signed 32-bit integers don't seem to be considered in ISIS
        "int32": {
            "N/A": -214743648,
            "UNK": 2147483647,
        },
        # TODO: dubious. when do we read 64-bit integers out of PDS3
        #  arrays anyway?
        "int64": {"N/A": -214743648, "UNK": 2147483647},
        "uint32": {
            "N/A": 4294967293,
            "UNK": 4294967294,
            "ISIS_NULL": read_hex("FF7FFFFB", ">I"),
            "ISIS_LOW_INST_SAT": read_hex("FF7FFFFD", ">I"),
            "ISIS_LOW_REPR_SAT": read_hex("FF7FFFFC", ">I"),
            "ISIS_HIGH_INST_SAT": read_hex("FF7FFFFE", ">I"),
            "ISIS_HIGH_REPR_SAT": read_hex("FF7FFFFF", ">I"),
        },
        "float32": {
            # also ISIS_NULL, but it's specified in the GDAL driver...
            "NULL": -3.4028226550889044521e38,
            "N/A": -1e32,
            "UNK": 1e32,
            "ISIS_LOW_INST_SAT": read_hex("FF7FFFFD", ">f"),
            "ISIS_LOW_REPR_SAT": read_hex("FF7FFFFC", ">f"),
            "ISIS_HIGH_INST_SAT": read_hex("FF7FFFFE", ">f"),
            "ISIS_HIGH_REPR_SAT": read_hex("FF7FFFFF", ">f"),
        },
        # TODO: something funny is happening here in ISIS re:
        #  a "special kludge for double precision initialization" -- there
        #  are additional values defined here, and I'm not sure how to
        #  interpret the DBL_UNION / DBL_INIT calls.
        #  I'm not sure when we explicitly read doubles out
        #  of PDS3 objects anyway?
        "float64": {
            "NULL": -3.4028226550889044521e38,
        },
    }
)
