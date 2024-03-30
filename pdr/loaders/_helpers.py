"""Simple utility functions for assorted loaders and queries."""

from functools import partial
from operator import contains
import os
from pathlib import Path
from typing import Union, Optional

from multidict import MultiDict

from pdr.pdrtypes import PhysicalTarget


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
    identifiers: dict, name: str, target: PhysicalTarget
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
    # TODO: not sure this is a good assumption -- it is a bad assumption
    #  for the CHEMIN RDRs, but those labels are just wrong
    if identifiers["RECORD_BYTES"] not in (None, ""):
        return False
    # TODO: not sure this is a good assumption
    if not identifiers["RECORD_TYPE"] == "STREAM":
        return False
    textish = map(partial(contains, name), ("ASCII", "SPREADSHEET", "HEADER"))
    if any(textish):
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
