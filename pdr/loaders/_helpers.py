"""Simple utility functions for assorted loaders and queries."""
from __future__ import annotations
from functools import wraps
import os
from pathlib import Path
import re
from typing import Any, Callable, Optional, Union, TYPE_CHECKING

from cytoolz import curry
from multidict import MultiDict

if TYPE_CHECKING:
    from pdr.pdrtypes import DataIdentifiers, PhysicalTarget


HETERODOX_ENDING = re.compile(r"\r\n?")
"""Pattern for heterodox but not deeply bizarre line endings."""
_cle = curry(re.sub, HETERODOX_ENDING, "\n")
"""partially evaluated replacer of heterodox with orthodox line endings."""


def looks_like_ascii(block: MultiDict, name: str) -> bool:
    """Is this probably an ASCII table?"""
    return (
        ("SPREADSHEET" in name)
        or ("ASCII" in name)
        or (block.get("INTERCHANGE_FORMAT") == "ASCII")
    )


def quantity_start_byte(
    quantity_dict: dict[str, Union[str, int]], record_bytes: Optional[int]
) -> Optional[int]:
    """
    Attempt to infer an object's start byte from a dict parsed from a PVL
    quantity object associated with a PVL pointer parameter, along with, if
    known, the size of a product's records (relevant only if the quantity
    units are not bytes). Returns None if we can't infer it (usually meaning
    that the label gives the start position in records but doesn't say how
    big the records are).
    """
    # TODO: are there cases in which _these_ aren't 1-indexed?
    if quantity_dict["units"] == "BYTES":
        return quantity_dict["value"] - 1
    if record_bytes is not None:
        return record_bytes * max(quantity_dict["value"] - 1, 0)


def count_from_bottom_of_file(
    fn: Union[str, list, Path], rows: int, row_bytes: int
) -> int:
    """
    Fallback start-byte-finding function for cases in which a label gives
    the length of a table in terms of number of rows and row length, but does
    not specify where in the file the table _starts_. In these cases, the table
    usually goes to the end of the file, but may be preceded by a header or
    whatever, which means that we can often guess its start byte by subtracting
    the table size in bytes from the physical size of the file. This is not
    guaranteed to work!
    """
    tab_size = rows * row_bytes
    if isinstance(fn, list):
        fn = fn[0]
    return os.path.getsize(Path(fn)) - tab_size


def _check_delimiter_stream(
    identifiers: DataIdentifiers,
    name: str,
    target: PhysicalTarget,
    block: MultiDict,
) -> bool:
    """
    Does it look like this object is a delimiter-separated table without an
    explicitly-defined row length?
    """
    # TODO: this may be deprecated. assess against notionally-supported
    #  products.
    if isinstance(target, dict):
        if target.get("units") == "BYTES":
            return False
    # TODO: untangle this, everywhere
    if isinstance(target, (list, tuple)):
        if isinstance(target[-1], dict):
            if target[-1].get("units") == "BYTES":
                return False
    # TODO: Other criteria that could appear in the block?
    if "BYTES" in block:
        return False
    # TODO: not sure this is a good assumption -- it is a bad assumption
    #  for the CHEMIN RDRs, but those labels are just wrong
    if identifiers["RECORD_BYTES"] not in (None, ""):
        return False
    # TODO: not sure this is a good assumption
    if not identifiers["RECORD_TYPE"] == "STREAM":
        return False
    # Well-known object types that imply textuality, if we have nothing
    # else to go on
    if any(label in name for label in ("ASCII", "SPREADSHEET", "HEADER")):
        return True
    return False


def check_explicit_delimiter(block: MultiDict) -> str:
    """
    Check if an ASCII TABLE/SPREADSHEET definition explicitly gives a field
    delimiter. If it doesn't, tentatively assume it's comma-separated.
    """
    if "FIELD_DELIMITER" in block.keys():
        try:
            return {
                "COMMA": ",",
                "VERTICAL_BAR": "|",
                "SEMICOLON": ";",
                "TAB": "\t",
            }[block["FIELD_DELIMITER"]]
        except KeyError:
            raise KeyError("Unknown FIELD_DELIMITER character.")
    return ","


def canonicalize_line_endings(text: Any) -> Any:
    """
    Attempt to replace common 'heterodox' line endings in a string or
    list/tuple of strings with canonical endings (\n). Does not attempt to
    perform sophisticated delimiter sniffing, and will only reliably handle
    only \r and \r\n endings, not \n\r, EM / 0x19, \r\r\n, etc.
    Ignores (returns unchanged) non-strings and non-string elements of
    lists/tuples.
    """
    if isinstance(text, str):
        return _cle(text)
    if isinstance(text, (list, tuple)):
        return type(text)([_cle(s) if isinstance(s, str) else s for s in text])
    return text


def canonicalized(func: Callable) -> Callable:
    """
    Creates a version of `func` that canonicalizes line endings of any string
    (or top-level string elements of a list/tuple), returned by `func`
    """

    @wraps(func)
    def with_canonical_endings(*args, **kwargs):
        return canonicalize_line_endings(func(*args, **kwargs))

    return with_canonical_endings
