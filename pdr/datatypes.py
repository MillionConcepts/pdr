"""
definitions of sample types / data types / dtypes / ctypes, file formats
and extensions, associated special constants, and so on.
"""
from itertools import product
from types import MappingProxyType

from pdr.utils import read_hex


def sample_types(sample_type: str, sample_bytes: int) -> str:
    """
    Defines a translation from PDS data types to Python struct format strings,
    using both the type and bytes specified (because the mapping to type alone
    is not consistent across PDS3).
    """
    return {
        "MSB_INTEGER": ">h",
        "INTEGER": ">h",
        "MAC_INTEGER": ">h",
        "SUN_INTEGER": ">h",
        "MSB_UNSIGNED_INTEGER": ">h" if sample_bytes == 2 else ">B",
        "UNSIGNED_INTEGER": ">B",
        "MAC_UNSIGNED_INTEGER": ">B",
        "SUN_UNSIGNED_INTEGER": ">B",
        "LSB_INTEGER": "<h" if sample_bytes == 2 else "<B",
        "PC_INTEGER": "<h",
        "VAX_INTEGER": "<h",
        "LSB_UNSIGNED_INTEGER": "<h" if sample_bytes == 2 else "<B",
        "PC_UNSIGNED_INTEGER": "<B",
        "VAX_UNSIGNED_INTEGER": "<B",
        "IEEE_REAL": ">f",
        "PC_REAL": "<d" if sample_bytes == 8 else "<f",
        "FLOAT": ">f",
        "REAL": ">f",
        "MAC_REAL": ">f",
        "SUN_REAL": ">f",
        "MSB_BIT_STRING": ">B",
        # "Character string representing a real number"
        "ASCII_REAL": f"S{sample_bytes}",
        # ASCII character string representing an integer
        "ASCII_INTEGER": f"S{sample_bytes}",
        # "ASCII character string representing a date in PDS standard format"
        # (e.g. 1990-08-01T23:59:59)
        "DATE": f"S{sample_bytes}",
        "CHARACTER": f"S{sample_bytes}",  # ASCII character string
    }[sample_type]


def generic_image_constants(data):
    consts = {}
    if data.LABEL.get("INSTRUMENT_ID") == "CRISM":
        consts["NULL"] = 65535
    return consts

# TODO: super incomplete, although hopefully not often needed


# special constants

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
        # TODO: these are simply ignored atm; too problematic in too many cases
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
        # TODO: signed 32-bit integers don't seem to be considered in ISIS?
        "int32": {
            "N/A": -214743648,
            "UNK": 2147483647,
        },
        # TODO: dubious. not sure when we read 64-bit integers out of PDS3
        #  objects anyway?
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
