"""Pointy-end functions for text-handling Loader subclasses."""
from io import TextIOWrapper
from pathlib import Path
from typing import Optional, Union
import warnings

from pdr.loaders._helpers import canonicalized
from pdr.loaders.utility import looks_like_this_kind_of_file
from pdr.parselabel.utils import trim_label
from pdr.utils import check_cases, decompress


def read_text(target: str, fn: Union[list[str], str]) -> Union[list[str], str]:
    """Read text from a file or list of files."""
    try:
        if isinstance(fn, str):
            return ignore_if_pdf(check_cases(fn))
        elif isinstance(fn, list):
            return [
                ignore_if_pdf(check_cases(each_file))
                for each_file in fn
            ]
    except FileNotFoundError or UnicodeDecodeError:
        warnings.warn(f"couldn't find {target}")
        raise


def read_header(
    fn: Union[str, Path],
    table_props: dict,
    name: str = "HEADER"
) -> str:
    """Read a text header from a file."""
    return skeptically_load_header(fn, table_props, name)


@canonicalized
def read_label(
    fn: Union[str, Path],
    fmt: Optional[str] = "text"
) -> Union[str, "PVLModule"]:
    """
    Read the entirety of a PDS3 label, optionally using `pvl` to parse it as
    completely as possible into Python objects. This is not intended for use
    in the primary `pdr.Metadata` initialization workflow, but rather to
    handle cases when the user explicitly requests the entirety of the label
    (typically by accessing the "LABEL" key of a `pdr.Data` object).
    """
    if fmt == "text":
        return trim_label(decompress(fn))
    elif fmt == "pvl":
        import pvl

        return pvl.load(fn)
    raise NotImplementedError(f"The {fmt} format is not yet implemented.")


@canonicalized
def skeptically_load_header(
    fn: Union[Path, str],
    table_props: dict,
    name: str = "header",  # TODO: what's with this default value?
    fmt: Optional[str] = "text",
) -> Union[str, "PVLModule", None]:
    """
    Attempt to read a text HEADER object from a file. PDS3 does not give a
    strict definition of the HEADER object, so there is no way to
    _consistently_ load HEADERs in a coherent, well-formatted fashion. However,
    providers generally use HEADER to denote either attached file/product-level
    metadata, column headers for an ASCII table, or object-level
    contextualizing metadata for ASCII tables.

    By default, simply read the designated byte range as unicode text. If
    `fmt` is "pvl", also attempt to parse this text as PVL. (This will fail
    on most products, because most HEADER objects are not PVL, but is useful
    for some ancillary attached labels, especially ISIS labels.)

    NOTE: HEADERs defined in labels very often do not actually exist and are
    never essential for loading primary data objects, so this function is
    _always_ "optional", even in debug mode. If it fails, it will simply raise
    a UserWarning and return None.

    WARNING: this function is not intended to load metadata of standard file
    formats (such as TIFF tags or FITS headers). These headers should always
    be handled by a format-specific parser. More generally, it will never work
    on binary files.
    """
    # TODO: all these check_cases calls are probably unnecessary w/new file
    #  mapping workflow
    # FIXME: PVL mode ignores the table_props
    # FIXME: Character encoding should be controlled separately from as_rows
    try:
        if fmt == "pvl":
            try:
                from pdr.pvl_utils import cached_pvl_load

                return cached_pvl_load(decompress(check_cases(fn)))
            except ValueError:
                pass
        if table_props["as_rows"] is True:
            # In order to take advantage of Python's universal newline
            # handling, we need to decode the file and _then_ split it.
            # Tolerate encoding errors mainly because we might have a
            # textual header preceded or followed by binary data, and
            # the decoder is going to process more of the file than
            # the part we actually use.
            lines = []
            start = table_props["start"]
            end = start + table_props["length"]
            with decompress(check_cases(fn)) as f:
                decoded_f = TextIOWrapper(f, encoding="UTF-8", errors="replace")
                for i, line in enumerate(decoded_f):
                    if i >= end:
                        break
                    if i >= start:
                        lines.append(line.replace("\n", "\r\n"))
            text = "".join(lines)
        else:
            with decompress(check_cases(fn)) as file:
                file.seek(table_props["start"])
                text = file.read(min(table_props["length"], 80000)).decode(
                    "ISO-8859-1"
                )
        return text
    except (ValueError, OSError) as ex:
        warnings.warn(f"unable to parse {name}: {ex}")


@canonicalized
# TODO: misleading name. Primarily a file _reader_.
def ignore_if_pdf(fn: Union[str, Path]) -> Optional[str]:
    """Read text from a file if it's not a pdf."""
    if looks_like_this_kind_of_file(fn, [".pdf"]):
        warnings.warn(f"Cannot open {fn}; PDF files are not supported.")
        return
    # TODO: should use a context manager to avoid dangling file handles
    return open(check_cases(fn)).read()
