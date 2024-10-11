"""
definitions of sample types / data types / dtypes / ctypes, file formats
and extensions, associated special constants, and so on.
"""
from __future__ import annotations
from itertools import product
import re
from types import MappingProxyType
from typing import TYPE_CHECKING

from pdr.utils import read_hex

if TYPE_CHECKING:
    from pdr.pdrtypes import ByteOrder


def integer_code(
    byteorder: ByteOrder,
    signed: bool,
    sample_bytes: int,
    for_numpy: bool = False
) -> str:
    """
    Translation from integer width, signedness, and byteorder to struct or
    numpy dtype string.
    """
    # TODO: add struct letter for longlong
    if sample_bytes == 4:
        letter = "l"
    elif sample_bytes == 2:
        letter = "h"
    else:
        letter = "b"
    if signed is False:
        letter = letter.upper()
    if for_numpy is True and sample_bytes in (4, 8):
        letter = f"i{sample_bytes}" if signed is True else f"u{sample_bytes}"

    return f"{byteorder}{letter}"


def determine_byte_order(sample_type: str) -> ByteOrder:
    """defines generic byte order for PDS3 physical data types"""
    if any(sample_type.startswith(s) for s in ("PC", "LSB", "VAX")):
        return "<"
    return ">"


def sample_types(
    sample_type: str, sample_bytes: int, for_numpy: bool = False
) -> str:
    """
    Defines a translation from PDS3 physical data types to Python struct or
    numpy dtype format strings, using both the type and byte width specified
    (because the mapping to type alone is not consistent across PDS3).
    """
    sample_type = sample_type.replace(" ", "_")
    if (("INTEGER" in sample_type) or (sample_type == "BOOLEAN")) and (
        "ASCII" not in sample_type
    ):
        endian = determine_byte_order(sample_type)
        signed = "UNSIGNED" not in sample_type
        return integer_code(endian, signed, sample_bytes, for_numpy)
    void = "V" if for_numpy is True else "s"
    if sample_bytes == 8:
        _float = "d"
    elif sample_bytes == 4:
        _float = "f"
    elif "ASCII" in sample_type:
        _float = ""
    elif re.search("REAL|FLOAT", sample_type):
        raise NotImplementedError(
            f"{sample_bytes}-byte floats are not supported."
        )
    else:
        _float = ""
    if sample_type == "VAX_REAL" and sample_bytes != 4:
        raise NotImplementedError(
            "VAX reals that are not 4 bytes wide are not supported."
        )
    # noinspection PyUnboundLocalVariable
    return {
        "IEEE_REAL": f">{_float}",
        "PC_REAL": f"<{_float}",
        "FLOAT": f">{_float}",
        "REAL": f">{_float}",
        "MAC_REAL": f">{_float}",
        "SUN_REAL": f">{_float}",
        "MSB_BIT_STRING": f"{void}{sample_bytes}",
        "LSB_BIT_STRING": f"{void}{sample_bytes}",
        # "Character string representing a real number"
        "ASCII_REAL": f"S{sample_bytes}",
        # ASCII character string representing an integer
        "ASCII_INTEGER": f"S{sample_bytes}",
        # "ASCII character string representing a date in PDS standard format"
        # (e.g. 1990-08-01T23:59:59)
        "DATE": f"S{sample_bytes}",
        "CHARACTER": f"S{sample_bytes}",  # ASCII character string
        "TIME": f"S{sample_bytes}",
        "VOID": f"{void}{sample_bytes}",
        "BCD": f"{void}{sample_bytes}",
        "BINARY_CODED_DECIMAL": f"{void}{sample_bytes}",
        # these two (VAX_REAL and IBM_REAL) unfortunately don't work perfectly
        # cleanly -- numpy doesn't have built-in support for them, so we just
        # get the byte width/order correct here and add additional checks to
        # transform it after load. the data type used here is mostly arbitrary
        # apart from byte width and order, but it shouldn't be a float type in
        # case of platform-specific differences, numpy being excessively
        # clever, etc.
        "VAX_REAL": f"<u{sample_bytes}",
        "IBM_REAL": f">u{sample_bytes}",
        "EBCDIC": f"V{sample_bytes}",
        "EBCDIC_CHARACTER": f"V{sample_bytes}",
    }[sample_type]


PDS3_CONSTANT_NAMES = (
    "INVALID_CONSTANT",
    "MISSING_CONSTANT",
    "INFINITY_CONSTANT",
    "NOT_APPLICABLE_CONSTANT",
    "NULL_CONSTANT",
    "UNKNOWN_CONSTANT",
)
"""basic" PDS3 special constant parameter names"""

PDS3_ISIS_CONSTANT_NAMES = tuple(
    [
        f"{category}{direction}{entity}{prop}"
        for category, direction, entity, prop in product(
            ("CORE_", "BAND_SUFFIX_", "SAMPLE_SUFFIX_", "LINE_SUFFIX_", ""),
            ("HIGH_", "LOW_", ""),
            ("INST_", "REPR_", ""),
            ("NULL", "SATURATION", "SAT"),
        )
    ]
)
"""
some (all?) of these special constants are derived from ISIS properties; these 
are names they take on when they are made explicit in a PDS3 label
"""

# noinspection PyTypeChecker
PDS3_CONSTANT_NAMES = tuple(PDS3_ISIS_CONSTANT_NAMES + PDS3_CONSTANT_NAMES)


# TODO: make all the dicts nested in this into MappingProxyTypes
IMPLICIT_PDS3_CONSTANTS = MappingProxyType(
    {
        # we define the uint8 constants but do not by default use them: they
        # are simply too problematic in too many cases.
        "uint8": {"NULL": 0, "ISIS_SAT_HIGH": 255},
        # ISIS doesn't seem to use this dtype and it's not mentioned in the SR
        "int8": {},
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
"""
This constant defines common "implicit" (not specified in the label) PDS3
special constants. Its keys are bits per array element.
Some of these constants are derived from ISIS (although sometimes used in 
products that were not generated by ISIS!); others are suggested in the PDS3 
Standards.

Note that the Standards specifically permit other special constants to exist, 
undefined in the label, and determined only by the operating environment of 
the data provider, so there can be no guarantee that other special constants 
do not exist in any particular product.

The "implicit" use of ISIS constants may in fact be illegal, but appears
common. also note that some ISIS values collide with Standards-specified N/A / 
UNK / NULL values -- again, we have no way to automatically distinguish them, 
and interpret them as the Standards values when we find them unless a label
specifically states otherwise.

References:
PDS3 Standards Reference v3.8, p.172
(https://pds.nasa.gov/datastandards/pds3/standards/sr/StdRef_20090227_v3.8.pdf)
GDAL PDS3 driver
TODO: -32768 is noted in this driver as NULL but defined in the Standards as
  an N/A value -- should clarify
(https://github.com/OSGeo/gdal/blob/master/frmts/pds/pdsdataset.cpp)
ISIS special pixel values
(https://isis.astrogeology.usgs.gov/Object/Developer/_special_pixel_8h_source.html)
"""
