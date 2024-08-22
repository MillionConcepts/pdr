import os
from itertools import product
from pathlib import Path

# noinspection PyProtectedMember
from pdr.loaders._helpers import (
    looks_like_ascii,
    quantity_start_byte,
    count_from_bottom_of_file,
    _check_delimiter_stream,
    check_explicit_delimiter
)


def test_looks_like_ascii():
    names = ('SPREADSHEET', 'ASCII_TABLE', 'IMAGE')
    formats = ('ASCII', 'STREAM')
    expected = (True, True, True, True, True, False)
    for (name, format_), value in zip(product(names, formats), expected):
        assert value == looks_like_ascii(
            {'INTERCHANGE_FORMAT': format_}, name
        )


def test_quantity_start_byte():
    units = "BYTES", "RECORDS"
    record_bytes = 100, None
    expected = 99, 99, 9900, None
    for (unit, rb), ex in zip(product(units, record_bytes), expected):
        assert quantity_start_byte({'units': unit, 'value': 100}, rb) == ex


def test_count_from_bottom_of_file(tmp_path):
    fn = [tmp_path / 'foo.bin', tmp_path / 'FOO.bin']
    rows = 100
    row_bytes = 256
    with fn[0].open('wb') as stream:
        stream.write(b'\x00' * rows * row_bytes * 2)
    assert (
            count_from_bottom_of_file(fn, rows, row_bytes) == rows * row_bytes
    )


def test_check_delimiter_stream():
    byte_target = {"units": "BYTES", "value": 19200}
    rec_target = {"units": "RECORDS", "value": 1200}
    identifiers = {
        "SPACECRAFT_ID": "NOSTALGIA_FOR_INFINITY",
        'RECORD_BYTES': 100,
        "ETC": ...,
        'RECORD_TYPE': 'BINARY'
    }
    empty_block = {}
    bytes_block = {"BYTES", 100}
    # should never say a stream with a byte quantity is delimited
    assert _check_delimiter_stream(identifiers, "TABLE", byte_target, empty_block) is False
    assert _check_delimiter_stream(identifiers, "TABLE", ("", byte_target), empty_block) is False
    # should never say a stream with specified record bytes is delimited
    assert _check_delimiter_stream(identifiers, "TABLE", rec_target, empty_block) is False
    identifiers['RECORD_BYTES'] = None
    # should never say a non-STREAM stream is delimited
    assert _check_delimiter_stream(identifiers, "TABLE", rec_target, empty_block) is False
    # should never say something that isn't ASCII/SPREADSHEET/HEADER is delimited
    identifiers['RECORD_TYPE'] = 'STREAM'
    assert _check_delimiter_stream(identifiers, "TABLE", rec_target, empty_block) is False
    # should never say something whose length is declared at the block level in bytes is delimited
    assert _check_delimiter_stream(identifiers, "SPREADSHEET", rec_target, bytes_block) is False
    # if all the above conditions aren't satisfied, should say it's delimited
    assert _check_delimiter_stream(identifiers, "SPREADSHEET", rec_target, empty_block) is True


def test_check_explicit_delimiter():
    assert check_explicit_delimiter({'FIELD_DELIMITER': 'VERTICAL_BAR'}) == '|'
    assert check_explicit_delimiter({}) == ','
    try:
        check_explicit_delimiter({'FIELD_DELIMITER': 'FENCE'})
        raise KeyError
    except KeyError:
        pass
