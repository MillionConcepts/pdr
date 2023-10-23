"""generic i/o, parsing, and functional utilities."""
import bz2
from io import BytesIO
from itertools import chain
from numbers import Number
from pathlib import Path
import struct
import textwrap
from typing import (
    Union,
    Sequence,
    Mapping,
    MutableSequence,
    IO,
    Collection,
    Optional,
)
import warnings
from zipfile import ZipFile

from dustgoggles.structures import listify
from multidict import MultiDict


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
    lowercase = path.stem.lower()
    exts = tuple(map(str.lower, path.suffixes))
    if len(exts) == 0:
        return lowercase
    # don't remove compression suffix if it's the only suffix
    if (len(exts) == 1) or (exts[-1] in SUPPORTED_COMPRESSION_EXTENSIONS):
        return f"{lowercase}{exts[0]}"
    return f"{lowercase}{exts[-1]}"


def check_cases(
    filenames: Union[Collection[Union[Path, str]], Union[Path, str]],
    skip: bool = False,
) -> str:
    """
    check for oddly-cased versions of a specified filename in local path --
    very common to have case mismatches between PDS3 labels and actual archive
    contents. similarly, check common compression extensions.

    the skip argument makes the function simply return filename.
    """
    filenames = listify(filenames)
    for filename in filenames:
        if skip is True:
            return str(filename)
        path = Path(filename)
        if path.exists():
            return str(filename)
        if not path.parent.exists():
            continue
        matches = tuple(
            filter(
                lambda p: stem_path(p) == Path(filename).name.lower(),
                path.parent.iterdir(),
            )
        )
        if len(matches) == 0:
            continue
        if len(matches) > 1:
            warning_list = ", ".join([path.name for path in matches])
            warnings.warn(
                f"Multiple off-case or possibly-compressed versions of "
                f"{filename} found in search path: {warning_list}. Using "
                f"{matches[0].name}."
            )
        return str(matches[0])
    filelist = ';'.join([str(f) for f in filenames])
    raise FileNotFoundError(
        f"No candidate paths for required file exist. Checked:{filelist}"
    )


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


def import_best_gzip():
    try:
        from isal import igzip as gzip_lib
    except ImportError:
        import gzip as gzip_lib
    return gzip_lib


def decompress(filename):
    if filename.lower().endswith(".gz"):
        f = import_best_gzip().open(filename, "rb")
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


def find_repository_root(absolute_path):
    parts = Path(absolute_path).parts
    data_indices = [
        ix for ix, part in enumerate(parts) if part.lower() == "data"
    ]
    return Path(*parts[: data_indices[-1]])


def prettify_multidict(multi, sep=" ", indent=0):
    indentation, output, first_line = "", "{", True
    for k, v in multi.items():
        if sep == "\n":
            indentation = " " * indent
            if first_line is True:
                output += "\n"
        if isinstance(v, MultiDict):
            output += (
                f"{indentation}{k}: "
                f"{prettify_multidict(v, indent = indent + 2)},{sep}"
            )
        elif (not isinstance(v, str)) or (len(v) <= 70):
            output += f"{indentation}{k}: {v},{sep}"
        else:
            lines = textwrap.wrap(v, width=(70 - len(indentation)))
            vstr = f"{lines[0]}\n" + "\n".join(
                [(" " * (indent + 1)) + line for line in lines[1:]]
            )
            output += f"{indentation}{k}: {vstr},{sep}"
        first_line = False
        if sep != " ":
            continue
        if len(output) > 70:
            return prettify_multidict(multi, sep="\n", indent=indent + 1)
    if len(indentation) > 0:
        indentation = indentation[:-1]
    return output + indentation + "}"


def associate_label_file(
    data_filename: str,
    label_filename: Optional[str] = None,
    skip_check: bool = False,
) -> Optional[str]:
    from pdr.loaders.utility import LABEL_EXTENSIONS
    if label_filename is not None:
        return check_cases(Path(label_filename).absolute(), skip_check)
    elif data_filename.lower().endswith(LABEL_EXTENSIONS):
        return check_cases(data_filename)
    for lext in LABEL_EXTENSIONS:
        try:
            return check_cases(with_extension(data_filename, lext))
        except FileNotFoundError:
            continue
    return None


def check_primary_fmt(data_filename: str):
    from pdr.loaders.utility import FITS_EXTENSIONS

    for ext in FITS_EXTENSIONS:
        if data_filename.lower().endswith(ext):
            return "FITS"


def catch_return_default(debug: bool, return_default, exception: Exception):
    """
    if we are in debug mode, reraise an exception. otherwise, return
    the default only.
    """
    if debug is True:
        raise exception
    return return_default
