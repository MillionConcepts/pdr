import os
from functools import partial
from operator import contains
from pathlib import Path


def looks_like_ascii(data, pointer):
    return (
        ("SPREADSHEET" in pointer)
        or ("ASCII" in pointer)
        or (data.metablock(pointer).get('INTERCHANGE_FORMAT') == 'ASCII')
    )


def quantity_start_byte(quantity_dict, record_bytes):
    # TODO: are there cases in which _these_ aren't 1-indexed?
    if quantity_dict["units"] == "BYTES":
        return quantity_dict["value"] - 1
    if record_bytes is not None:
        return record_bytes * max(quantity_dict["value"] - 1, 0)


def _count_from_bottom_of_file(filename, rows, row_bytes):
    tab_size = rows * row_bytes
    if isinstance(filename, list):
        filename = filename[0]
    return os.path.getsize(Path(filename)) - tab_size


def looks_like_this_kind_of_file(filename: str, kind_extensions) -> bool:
    is_this_kind_of_extension = partial(contains, kind_extensions)
    return any(
        map(is_this_kind_of_extension, Path(filename.lower()).suffixes)
    )