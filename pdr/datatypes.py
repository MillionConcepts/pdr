"""
definitions of sample types / data types / dtypes / ctypes, file formats
and extensions, associated special constants, and so on.
"""
from functools import partial
from itertools import product, chain
from numbers import Number
from operator import contains
from pathlib import Path
import struct
from types import MappingProxyType
from typing import Collection


# TODO: replace this with regularizing case of filenames upstream per Michael
#  Aye's recommendation
def in_both_cases(strings: Collection[str]) -> tuple[str]:
    """
    given a collection of strings, return a tuple containing each string in
    that collection in both upper and lower case.
    """
    return tuple(
        chain.from_iterable(
            [(string.upper(), string.lower()) for string in strings]
        )
    )


LABEL_EXTENSIONS = in_both_cases((".xml", ".lbl"))
DATA_EXTENSIONS = in_both_cases(
    (
        ".img",
        ".fit",
        ".fits",
        ".dat",
        ".tab",
        ".qub",
        # Compressed data... not PDS-compliant, but...
        ".gz",
        # And then the really unusual ones...
        ".n06",
        ".grn",  # Viking
        ".rgb",  # MER
        ".raw",  # Mars Express VMC, when capitalized
        ".tif",
        ".tiff",
    )
)


def read_hex(hex_string: str, fmt: str = ">I") -> Number:
    """
    return the decimal representation of a hexadecimal number in a given
    number format (expressed as a struct-style format string, default is
    unsigned 32-bit integer)
    """
    return struct.unpack(fmt, bytes.fromhex(hex_string))[0]


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


# TODO: super incomplete, although hopefully not often needed
IMAGE_EXTENSIONS = (".img", ".tif", ".tiff", ".rgb")
TABLE_EXTENSIONS = (".tab", ".csv")
TEXT_EXTENSIONS = (".txt", ".md")
FITS_EXTENSIONS = (".fits", ".fit")


def looks_like_this_kind_of_file(filename:str, kind_extensions) -> bool:
    is_this_kind_of_extension = partial(contains, kind_extensions)
    return any(
        map(is_this_kind_of_extension, Path(filename.lower()).suffixes)
    )


def extension_to_method_name(filename: str) -> str:
    """
    attempt to select the correct method of pdr.Data for objects only
    specified by a PDS3 FILE_NAME pointer (or by filename otherwise).
    """
    if looks_like_this_kind_of_file(filename, IMAGE_EXTENSIONS):
        return "read_image"
    if looks_like_this_kind_of_file(filename, FITS_EXTENSIONS):
        return "handle_fits_file"
    if looks_like_this_kind_of_file(filename, TEXT_EXTENSIONS):
        return "read_text"
    if looks_like_this_kind_of_file(filename, TABLE_EXTENSIONS):
        return "read_table"
    return "tbd"


def pointer_to_method_name(pointer: str, filename: str) -> str:
    """
    attempt to select the appropriate read method of pdr.Data based on a PDS3
    pointer name.
    """
    if "DESC" in pointer:  # probably points to a reference file
        return "read_text"
    if "HEADER" in pointer or "DATA_SET_MAP_PROJECTION" in pointer:
        return "read_header"
    if ("IMAGE" in pointer) or ("QUB" in pointer):
        # TODO: sloppy pt. 1. this will be problematic for
        #  products with a 'secondary' fits file, etc.
        if looks_like_this_kind_of_file(filename, FITS_EXTENSIONS):
            return "handle_fits_file"
        return "read_image"
    if "LINE_PREFIX_TABLE" in pointer:
        return "tbd"
    if "TABLE" in pointer:
        return "read_table"
    if "FILE_NAME" in pointer:
        return extension_to_method_name(pointer)
    # TODO: sloppy pt. 2
    if looks_like_this_kind_of_file(filename, FITS_EXTENSIONS):
        return "handle_fits_file"
    return "tbd"


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
