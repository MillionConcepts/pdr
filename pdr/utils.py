"""generic i/o, parsing, and functional utilities."""
import bz2
import gzip
import struct
import warnings
from io import BytesIO
from itertools import chain
from numbers import Number
from pathlib import Path
from typing import Union, Sequence, Mapping, MutableSequence, IO
from zipfile import ZipFile


def read_hex(hex_string: str, fmt: str = ">I") -> Number:
    """
    return the decimal representation of a hexadecimal number in a given
    number format (expressed as a struct-style format string, default is
    unsigned 32-bit integer)
    """
    return struct.unpack(fmt, bytes.fromhex(hex_string))[0]


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


# compression 'types' we support
SUPPORTED_COMPRESSION_EXTENSIONS = (".gz", ".bz2", ".zip")


def stem_path(path: Path):
    """
    convert a Path to lowercase and remove any compression extensions
    from it to stem for loose matching
    """
    lowercase = path.name.lower()
    for ext in SUPPORTED_COMPRESSION_EXTENSIONS:
        lowercase = lowercase.replace(ext, "")
    return lowercase


def check_cases(filename: Union[Path, str], skip: bool = False) -> str:
    """
    check for oddly-cased versions of a specified filename in local path --
    very common to have case mismatches between PDS3 labels and actual archive
    contents. similarly, check common compression extensions.

    the skip argument makes the function simply return filename.
    """
    if skip is True:
        return str(filename)
    if Path(filename).exists():
        return str(filename)
    matches = tuple(
        filter(
            lambda path: stem_path(path) == Path(filename).name.lower(),
            Path(filename).parent.iterdir(),
        )
    )
    if len(matches) == 0:
        raise FileNotFoundError
    if len(matches) > 1:
        warning_list = ", ".join([path.name for path in matches])
        warnings.warn(
            f"Multiple off-case or possibly-compressed versions of {filename} "
            f"found in search path: {warning_list}. Using {matches[0].name}."
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
    if filename.lower().endswith(".gz"):
        f = gzip.open(filename, "rb")
    elif filename.lower().endswith(".bz2"):
        f = bz2.BZ2File(filename, "rb")
    elif filename.lower().endswith(".zip"):
        f = ZipFile(filename, "r").open(
            ZipFile(filename, "r").infolist()[0].filename
        )
    else:
        f = open(filename, "rb")
    return f


def with_extension(fn: Union[str, Path], new_suffix: str) -> str:
    return str(Path(fn).with_suffix(new_suffix))
