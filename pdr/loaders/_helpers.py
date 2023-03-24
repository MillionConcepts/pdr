import os
from pathlib import Path

import pdr
import pdr.loaders.queries


def table_position(self, object_name):
    target = self._get_target(object_name)
    block = self.metablock_(object_name)
    try:
        if 'RECORDS' in block.keys():
            n_records = block['RECORDS']
        elif 'ROWS' in block.keys():
            n_records = block['ROWS']
        else:
            n_records = None
    except AttributeError:
        n_records = None
    length = None
    if (as_rows := self._check_delimiter_stream(object_name)) is True:
        if isinstance(target[1], dict):
            start = target[1]['value'] - 1
        else:
            try:
                start = target[1] - 1
            except TypeError:  # string types cannot have integers subtracted (string implies there is one object)
                start = 0
        if n_records is not None:
            length = n_records
    else:
        start = pdr.loaders.queries.data_start_byte(object_name)
        try:
            if "BYTES" in block.keys():
                length = block["BYTES"]
            elif n_records is not None:
                if "RECORD_BYTES" in block.keys():
                    record_length = block['RECORD_BYTES']
                elif "ROW_BYTES" in block.keys():
                    record_length = block['ROW_BYTES']
                    record_length += block.get("ROW_SUFFIX_BYTES", 0)
                elif self.metaget_("RECORD_BYTES") is not None:
                    record_length = self.metaget_("RECORD_BYTES")
                else:
                    record_length = None
                if record_length is not None:
                    length = record_length * n_records
        except AttributeError:
            length = None
    is_special, spec_start, spec_length, spec_as_rows = check_special_position(
        start, length, as_rows, self, object_name)
    if is_special:
        return spec_start, spec_length, spec_as_rows
    return start, length, as_rows


def looks_like_ascii(data, pointer):
    return (
        ("SPREADSHEET" in pointer)
        or ("ASCII" in pointer)
        or (data.metablock(pointer).get('INTERCHANGE_FORMAT') == 'ASCII')
    )



def _assume_data_start_given_in_bytes(target):
    # TODO: Nothing in our test database uses this. It also seems like it's calling the
    #  wrong index (should be -1?)
    if isinstance(target[0], int):
        return target[0]
    raise ValueError(f"unknown data pointer format: {target}")


def quantity_start_byte(quantity_dict, record_bytes):
    # TODO: are there cases in which _these_ aren't 1-indexed?
    if quantity_dict["units"] == "BYTES":
        return quantity_dict["value"] - 1
    if record_bytes is not None:
        return record_bytes * max(quantity_dict["value"] - 1, 0)


def _count_from_bottom_of_file(meta, filename, row_bytes=None):
    rows = meta.metaget_("ROWS")
    if not row_bytes:
        row_bytes = meta.metaget_("ROW_BYTES")
    tab_size = rows * row_bytes
    if isinstance(filename, list):
        filename = filename[0]
    return os.path.getsize(Path(filename)) - tab_size
