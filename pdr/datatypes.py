"""
definitions of sample types / data types / dtypes / ctypes, file formats
and extensions, associated special constants, and so on.
"""
from itertools import product

LABEL_EXTENSIONS = (".xml", ".XML", ".lbl", ".LBL")
DATA_EXTENSIONS = (
    ".img",
    ".IMG",
    ".fit",
    ".FIT",
    ".fits",
    ".FITS",
    ".dat",
    ".DAT",
    ".tab",
    ".TAB",
    ".QUB",
    # Compressed data... not PDS-compliant, but...
    ".gz",
    # And then the really unusual ones...
    ".n06",
    ".grn",  # Viking
    ".rgb",  # MER
    ".raw",
    ".RAW",  # Mars Express VMC
    ".TIF",
    ".tif",
    ".TIFF",
    ".tiff"
)

def sample_types(sample_type: str, sample_bytes: int) -> str:
    """
    Defines a translation from PDS data types to Python format strings,
    using both the type and bytes specified (because the mapping to type
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
        "ASCII_REAL": f"S{sample_bytes}",  # "Character string representing a real number"
        "ASCII_INTEGER": f"S{sample_bytes}",  # ASCII character string representing an integer
        "DATE": f"S{sample_bytes}",
        # "ASCII character string representing a date in PDS standard format" (1990-08-01T23:59:59)
        "CHARACTER": f"S{sample_bytes}",  # ASCII character string
    }[sample_type]


# special constants

# "basic" PDS3 special constants
from types import MappingProxyType

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
# common.

# References:
# PDS3 Standards Reference v3.8, p.172
# (https://pds.nasa.gov/datastandards/pds3/standards/sr/StdRef_20090227_v3.8.pdf)
# GDAL PDS3 driver
# (https://github.com/OSGeo/gdal/blob/master/frmts/pds/pdsdataset.cpp)
# ISIS...

# TODO: this won't work correctly if arrays are being cast into larger dtypes.
# TODO: what, if anything, are the 'correct' constants for int64?
IMPLICIT_PDS3_CONSTANTS = MappingProxyType(
    {
    "uint8": {"NULL": 0},
    "int16": {"N/A": -32768, "UNK": 32767},
    "uint16": {"N/A": 65533, "UNK": 65534},
    "int32": {"N/A": -214743648, "UNK": 2147483647},
    "uint32": {"N/A": 4294967293, "UNK": 4294967294},
    "float32": {"NULL": -3.4028226550889044521e+38, "N/A": -1E32, "UNK": 1E32},
    "float64": {"NULL": -3.4028226550889044521e+38, "N/A": -1E32, "UNK": 1E32},
    }
)

