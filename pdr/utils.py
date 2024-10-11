"""generic i/o, parsing, and functional utilities."""

from io import BytesIO
from itertools import chain
from numbers import Number
from pathlib import Path
import struct
import textwrap
from typing import (
    Collection,
    IO,
    Mapping,
    MutableSequence,
    Optional,
    Sequence,
    Union,
)
import warnings


from dustgoggles.structures import listify
from multidict import MultiDict


SUPPORTED_COMPRESSION_EXTENSIONS = (".gz", ".bz2", ".zip")
"""compression 'types' we support"""


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
    """"""
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


def stem_path(path: Path):
    """
    convert a Path to lowercase and remove any compression extensions
    from it to stem for loose matching
    """
    lowercase = path.name.split('.')[0].lower()
    exts = tuple(map(str.lower, path.suffixes))
    if len(exts) == 0:
        return lowercase
    looks_compressed = exts[-1] in SUPPORTED_COMPRESSION_EXTENSIONS
    # remove a trailing compression suffix, unless it's the only suffix
    if len(exts) > 1 and looks_compressed:
        exts = exts[:-1]
    return f"{lowercase}{''.join(exts)}"


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
    filelist = ";".join([str(f) for f in filenames])
    raise FileNotFoundError(
        f"No candidate paths for required file exist. Checked:{filelist}"
    )


def append_repeated_object(
    obj: Union[Sequence, Mapping],
    fields: MutableSequence,
    repeat_count: int,
) -> MutableSequence:
    """
    Polymorphic function to append `obj` `repeat_count` times to `fields`.
    If `obj` is a non-string sequence, it instead concatenates and adds it.
    For instance:
    ```
    >>> append_repeated_object([1, 2], [4], 3)
    [4, 1, 2, 1, 2, 1, 2]
    >>> append_repeated_object({"a": "b"}, ["a"], 3)
    ["a", {"a": "b"}, {"a": "b"}, {"a": "b"}]
    ```
    NOTE: This function treats `repeat_count` values < 1 as 1.
    WARNING: this function does not copy `obj` or any of its elements, even if
    they are mutable. This is not a bug, but can cause unexpected behavior, so
    take care (and in particular, always go depth-first if you are using this
    function in a recursive operation).
    """
    if hasattr(obj, "__add__"):
        if repeat_count > 1:
            fields += chain.from_iterable([obj for _ in range(repeat_count)])
        else:
            fields += obj
    else:
        if repeat_count > 1:
            fields += [obj for _ in range(repeat_count)]
        else:
            fields.append(obj)
    return fields


def import_best_gzip():
    """"""
    try:
        from isal import igzip as gzip_lib
    except ImportError:
        import gzip as gzip_lib
    return gzip_lib


def decompress(filename):
    """Open FILENAME.  If its name suffix indicates one of the supported
    compression algorithms, transparently decompress it."""
    # open the file directly to ensure that we get a regular OSError
    # (subclass), instead of a GzipError or something, if the file
    # doesn't exist or there's some other OS-level problem with it
    fp = open(filename, "rb")

    # this will be the _last_ suffix only, e.g. "foo.tar.gz" -> ".gz"
    suffix = Path(filename).suffix.lower()
    if suffix == ".gz":
        return import_best_gzip().GzipFile(fileobj=fp)
    if suffix == ".bz2":
        import bz2
        return bz2.BZ2File(fp)
    if suffix == ".zip":
        from zipfile import ZipFile
        z = ZipFile(fp)
        return z.open(z.infolist()[0])
    return fp


def with_extension(fn: Union[str, Path], new_suffix: str) -> str:
    """"""
    return str(Path(fn).with_suffix(new_suffix))


def find_repository_root(absolute_path):
    """"""
    parts = Path(absolute_path).parts
    data_indices = [
        ix for ix, part in enumerate(parts) if part.lower() == "data"
    ]
    return Path(*parts[: data_indices[-1]])


def prettify_multidict(multi, sep=" ", indent=0):
    """"""
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
    """"""
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
    """"""
    from pdr.loaders.utility import (
        DESKTOP_IMAGE_EXTENSIONS,
        FITS_EXTENSIONS,
        looks_like_this_kind_of_file,
        DESKTOP_IMAGE_STANDARDS
    )

    lower = data_filename.lower()
    for ext in FITS_EXTENSIONS:
        if lower.endswith(ext):
            return "FITS"
    if looks_like_this_kind_of_file(lower, DESKTOP_IMAGE_EXTENSIONS):
        try:
            from PIL import Image, UnidentifiedImageError
        except ImportError:
            raise ModuleNotFoundError(
                "Reading desktop image formats requires the 'pillow' library."
            )
        Image.MAX_IMAGE_PIXELS = None
        try:
            standard = Image.open(data_filename).format
            assert standard in DESKTOP_IMAGE_STANDARDS
        except UnidentifiedImageError:
            raise OSError(f"Can't interpret {data_filename} as an image.")
        except AssertionError:
            # noinspection PyUnboundLocalVariable
            raise NotImplementedError(
                f"{standard} images are not currently supported."
            )
        return standard
    return None


def catch_return_default(debug: bool, return_default, exception: Exception):
    """
    if we are in debug mode, reraise an exception. otherwise, return
    the default only.
    """
    if debug is True:
        raise exception
    return return_default
