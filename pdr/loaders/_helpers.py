import os
from functools import partial
from operator import contains
from pathlib import Path


def looks_like_ascii(block, name):
    """"""
    return (
        ("SPREADSHEET" in name)
        or ("ASCII" in name)
        or (block.get("INTERCHANGE_FORMAT") == "ASCII")
    )


def quantity_start_byte(quantity_dict, record_bytes):
    """"""
    # TODO: are there cases in which _these_ aren't 1-indexed?
    if quantity_dict["units"] == "BYTES":
        return quantity_dict["value"] - 1
    if record_bytes is not None:
        return record_bytes * max(quantity_dict["value"] - 1, 0)


def count_from_bottom_of_file(fn, rows, row_bytes):
    """"""
    tab_size = rows * row_bytes
    if isinstance(fn, list):
        fn = fn[0]
    return os.path.getsize(Path(fn)) - tab_size


def _check_delimiter_stream(identifiers, name, target):
    """
    do I appear to point to a delimiter-separated file without
    explicit record byte length
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


def check_explicit_delimiter(block):
    """"""
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
