"""assorted utility functions"""
import bz2
import gzip
import re
import struct
import warnings
from io import BytesIO
from itertools import chain
from numbers import Number
from pathlib import Path
from typing import (
    Optional,
    Collection,
    Union,
    Sequence,
    Mapping,
    MutableSequence,
    IO
)
from zipfile import ZipFile

import multidict
from dustgoggles.structures import dig_for
import numpy as np


def get_pds3_pointers(
    label: Optional[multidict.MultiDict] = None,
) -> tuple:
    """
    attempt to get all PDS3 "pointers" -- PVL parameters starting with "^" --
    from a MultiDict generated from a PDS3 label
    """
    return dig_for(label, "^", lambda k, v: k.startswith(v))


def pointerize(string: str) -> str:
    """make a string start with ^ if it didn't already"""
    return string if string.startswith("^") else "^" + string


def depointerize(string: str) -> str:
    """prevent a string from starting with ^"""
    return string[1:] if string.startswith("^") else string


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


def read_hex(hex_string: str, fmt: str = ">I") -> Number:
    """
    return the decimal representation of a hexadecimal number in a given
    number format (expressed as a struct-style format string, default is
    unsigned 32-bit integer)
    """
    return struct.unpack(fmt, bytes.fromhex(hex_string))[0]


# heuristic for max label size. we know it's not a real rule.
MAX_LABEL_SIZE = 500 * 1024


def head_file(
    fn_or_reader: Union[IO, Path, str],
    nbytes: Union[int, None] = None,
    offset: int = 0,
    tail: bool = False,
) -> BytesIO:
    head_buffer = BytesIO()
    if not hasattr(fn_or_reader, "read"):
        fn_or_reader = open(fn_or_reader, "rb")
    whence = 2 if tail is True else False
    offset = offset * -1 if tail is True else offset
    fn_or_reader.seek(offset, whence)
    head_buffer.write(fn_or_reader.read(nbytes))
    fn_or_reader.close()
    head_buffer.seek(0)
    return head_buffer


KNOWN_LABEL_ENDINGS = (
    b"END\r\n",  # PVL
    b"\x00{3}",  # just null bytes
)


def trim_label(
    fn: Union[IO, Path, str],
    max_size: int = MAX_LABEL_SIZE,
    raise_for_failure: bool = False,
) -> Union[str, bytes]:
    head = head_file(fn, max_size).read()
    for ending in KNOWN_LABEL_ENDINGS:
        if (endmatch := re.search(ending, head)) is not None:
            return head[: endmatch.span()[1]]
    if raise_for_failure:
        raise ValueError("couldn't find a label ending")
    return head


def casting_to_float(array: np.ndarray, *operands: Collection[Number]) -> bool:
    """
    check: will this operation cast the array to float?
    return True if array is integer-valued and any operands are not integers.
    """
    return (array.dtype.char in np.typecodes["AllInteger"]) and not all(
        [isinstance(operand, int) for operand in operands]
    )


def check_cases(filename: Union[Path, str]) -> str:
    """
    check for oddly-cased versions of a specified filename in local path --
    very common to have case mismatches between PDS3 labels and actual archive
    contents.
    """
    if Path(filename).exists():
        return filename
    matches = tuple(
        filter(
            lambda path: path.name.lower() == Path(filename).name.lower(),
            Path(filename).parent.iterdir(),
        )
    )
    if len(matches) == 0:
        raise FileNotFoundError
    if len(matches) > 1:
        warning_list = ", ".join([path.name for path in matches])
        warnings.warn(
            f"Multiple off-case versions of {filename} found in search path: "
            f"{warning_list}. Using {matches[0].name}."
        )
    return str(matches[0])


def append_repeated_object(
    obj: Union[Sequence[Mapping], Mapping],
    fields: MutableSequence[Mapping],
    repeat_count: int,
) -> Sequence[Mapping]:
    # sum lists (from containers) together and add to fields
    if hasattr(obj, "__add__"):
        if repeat_count > 1:
            fields += chain.from_iterable([obj for _ in range(repeat_count)])
        else:
            fields += obj
    # put dictionaries in a repeated list and add to fields
    else:
        if repeat_count > 1:
            fields += [obj for _ in range(repeat_count)]
        else:
            fields.append(obj)
    return fields


def decompress(filename):
    filename = check_cases(filename)
    if filename.endswith(".gz"):
        f = gzip.open(filename, "rb")
    elif filename.endswith(".bz2"):
        f = bz2.BZ2File(filename, "rb")
    elif filename.endswith(".ZIP"):
        f = ZipFile(filename, "r").open(
            ZipFile(filename, "r").infolist()[0].filename
        )
    else:
        f = open(filename, "rb")
    return f

