"""
Functions for the nitty-gritty byte-juggling parts of
TABLE/SPREADSHEET/ARRAY/HISTOGRAM loading.
"""

from io import StringIO
from typing import Optional

import numpy as np
import pandas as pd
from multidict import MultiDict
from pandas.errors import ParserError
import re

from pdr import bit_handling
from pdr.datatypes import sample_types
from pdr.loaders._helpers import check_explicit_delimiter
from pdr.loaders.queries import get_array_num_items
from pdr.np_utils import np_from_buffered_io, enforce_order_and_object
from pdr.pd_utils import (
    booleanize_booleans, compute_offsets, convert_ebcdic, convert_ibm_reals
)
from pdr.utils import decompress, head_file


PAD_CHARACTERS = ' \t",'
"""
Characters we want to strip from the beginning/end of every element of an 
ASCII table.
"""


def read_array(fn, block, start_byte, fmtdef_dt):
    """
    Read an array object from this product and return it as a numpy array.
    """
    if block.get("INTERCHANGE_FORMAT") == "BINARY":
        _, dt = fmtdef_dt
        count = get_array_num_items(block)
        with decompress(fn) as f:
            array = np_from_buffered_io(
                f,
                dtype=dt,
                count=count,
                offset=start_byte,
            )
        return array.reshape(block["AXIS_ITEMS"])
    # assume objects without the optional interchange_format key are ascii
    with open(fn) as stream:
        text = stream.read()
    try:
        text = tuple(map(float, re.findall(r"[+-]?\d+\.?\d*", text)))
    except (TypeError, IndexError, ValueError):
        text = re.split(r"\s+", text)
    array = np.asarray(text).reshape(block["AXIS_ITEMS"])
    if "DATA_TYPE" in block.keys():
        array = array.astype(
            sample_types(block["DATA_TYPE"], block["BYTES"], True)
        )
    return array


def _drop_placeholders(table: pd.DataFrame) -> pd.DataFrame:
    return table.drop(
        [k for k in table.keys() if "PLACEHOLDER" in k], axis=1
    )


def read_table(
    identifiers,
    fn,
    fmtdef_dt,
    table_props,
    block,
    start_byte,
):
    """
    Read a table. Parse the label format definition and then decide whether to
    treat the table as text or binary.
    """
    fmtdef, dt = fmtdef_dt
    if dt is None:  # we believe object is an ascii file
        table = _interpret_as_ascii(
            identifiers, fn, fmtdef, block, table_props
        )
        if len(table.columns) != len(fmtdef):
            table.columns = [
                f for f in fmtdef['NAME'] if not f.startswith('PLACEHOLDER')
        ]
        else:
            table.columns = fmtdef['NAME']
    else:
        table = _interpret_as_binary(fn, fmtdef, dt, block, start_byte)
    table = _drop_placeholders(table)
    # If there is an offset and/or scaling factor, apply them:
    if fmtdef.get("OFFSET") is not None or fmtdef.get("SCALING_FACTOR") is not None:
        for col in table.columns:
            record = fmtdef.loc[fmtdef['NAME'] == col].to_dict("records")[0]
            if record.get("SCALING_FACTOR") and not pd.isnull(record.get("SCALING_FACTOR")):
                table[col] = table[col].mul(record["SCALING_FACTOR"])
            else:
                scaling_factor = 1  # TODO: appears superfluous
            if record.get("OFFSET") and not pd.isnull(record.get("OFFSET")):
                offset = record["OFFSET"]
                table[col] = table[col]+offset
    return table


def _interpret_as_binary(fn, fmtdef, dt, block, start_byte):
    """"""
    # TODO: this works poorly (from a usability and performance
    #  perspective; it's perfectly stable) for tables defined as
    #  a single row with tens or hundreds of thousands of columns
    count = block.get("ROWS")
    count = count if count is not None else 1
    with decompress(fn) as f:
        table = np_from_buffered_io(
            f, dtype=dt, offset=start_byte, count=count
        )
    table = enforce_order_and_object(table)
    table = pd.DataFrame(table)
    table = convert_ibm_reals(table, fmtdef)
    table.columns = fmtdef.NAME.tolist()
    table = convert_ebcdic(table, fmtdef)
    table = booleanize_booleans(table, fmtdef)
    table = bit_handling.expand_bit_strings(table, fmtdef)
    return table


# TODO: are we ever actually using this at this point? note
#  that it will never work for compressed files.
def _read_with_np_loadtxt(
    fn: str, identifiers: dict, sep: str
) -> pd.DataFrame:
    """
    Attempt to load text from a file and parse it as a delimited table using
    `np.loadtxt()`.
    """
    return pd.DataFrame(
        np.loadtxt(
            fn,
            delimiter=sep,
            # TODO, maybe: this currently fails -- perhaps
            #  correctly -- when there is no LABEL_RECORDS key.
            #  but perhaps it is better to set a default of 0
            #  and avoid use of read_fwf. Update: Now has the possibility of
            #  the key being "". Unsure how this will affect the behavior.
            skiprows=identifiers["LABEL_RECORDS"],
        )
        .copy()
        .newbyteorder("=")
    )


def _read_as_delimited(
    fn: str,
    identifiers: dict,
    sep: str,
    string_buffer: StringIO,
    fmtdef: pd.DataFrame
) -> Optional[pd.DataFrame]:
    """
    Attempt to read an ASCII table as a delimiter-separated file. We always
    try this first before moving to a fixed-width parser.
    """
    try:
        table = pd.read_csv(string_buffer, sep=sep, header=None)
    except (UnicodeError, AttributeError, ParserError):
        table = _read_with_np_loadtxt(fn, identifiers, sep)
    # TODO: adding this 'PLACEHOLDER' check has allowed many tables to use
    #  read_csv() instead of read_fwf(), which is generally preferable
    #  because read_fwf() is very slow. This may also be able to invalidate
    #  some special cases; should check.
    n_place = len(fmtdef.loc[fmtdef.NAME.str.contains('PLACEHOLDER')])
    if len(table.columns) + n_place != len(fmtdef.NAME.tolist()):
        raise IndexError("Mismatched column length.")
    for c, d in zip(table.columns, table.dtypes):
        if d.name == "object":
            table[c] = table[c].str.strip(PAD_CHARACTERS)
    return table


def _read_fwf_with_colspecs(
    fmtdef: pd.DataFrame, string_buffer: StringIO
) -> pd.DataFrame:
    """
    Attempt to read an ASCII table as a fixed-width file using column
    boundaries specified by or inferred from its format definition.
    """
    colspecs = []
    # TODO: this if clause is a 'general special' statement, intended to handle
    #  instances in which special cases call read_table_structure() but do not
    #  pass its results to parse_table_structure() due to some special required
    #  handling. We probably want to change something upstream to avoid this.
    if "SB_OFFSET" not in fmtdef.columns:
        position_records = compute_offsets(fmtdef).to_dict("records")
    else:
        position_records = fmtdef.to_dict("records")
    for record in position_records:
        if np.isnan(record.get("ITEM_BYTES", np.nan)):
            col_length = record["BYTES"]
        else:
            col_length = int(record["ITEM_BYTES"])
        colspecs.append(
            (record["SB_OFFSET"], record["SB_OFFSET"] + col_length)
        )
    # NOTE: the 'delimiter' argument to read_fwf() does _not_ specify
    # an actual delimiter. It defines characters the read_fwf parser
    # will treat as 'padding' and strip from each table element.
    table = pd.read_fwf(
        string_buffer,
        header=None,
        colspecs=colspecs,
        delimiter=PAD_CHARACTERS
    )
    return table


def _read_table_from_stringio(
    fmtdef: pd.DataFrame,
    fn: str,
    identifiers: dict,
    block: MultiDict,
    string_buffer: StringIO
) -> pd.DataFrame:
    """
    Attempt to parse a string buffer, presumably containing an ASCII table, as
    a pandas DataFrame. First try to treat it as a delimiter-separated table;
    fall back to fixed-width parsing if that doesn't work.
    """
    # TODO, maybe: add better delimiter detection & dispatch
    try:
        sep = check_explicit_delimiter(block)
        return _read_as_delimited(fn, identifiers, sep, string_buffer, fmtdef)
    except (TypeError, KeyError, IndexError, ValueError):  # ☹️
        pass
    string_buffer.seek(0)
    if "BYTES" in fmtdef.columns:
        try:
            return _read_fwf_with_colspecs(fmtdef, string_buffer)
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            string_buffer.seek(0)
    # last-ditch fallback if we don't have column specifications or using the
    # column specifications didn't work. This usually won't work!
    # NOTE: see note in _read_fwf_with_colspecs() on 'delimiter' argument
    return pd.read_fwf(string_buffer, header=None, delimiter=PAD_CHARACTERS)


def _interpret_as_ascii(
    identifiers: dict,
    fn: str,
    fmtdef: pd.DataFrame,
    block: MultiDict,
    table_props: dict
):
    """Load text from a file and parse it as an ASCII table."""
    with decompress(fn) as f:
        if table_props["as_rows"] is False:
            bytesbuf = head_file(
                f, nbytes=table_props["length"], offset=table_props["start"]
            )
            try:
                stringbuf = StringIO(bytesbuf.read().decode())
            finally:
                bytesbuf.close()
        else:
            if table_props["start"] > 0:
                [next(f) for _ in range(table_props["start"])]
            if table_props["length"] in (None, ""):
                lines = f.readlines()
            else:
                lines = [next(f) for _ in range(table_props["length"])]
            stringbuf = StringIO("\r\n".join(map(bytes.decode, lines)))
    stringbuf.seek(0)
    return _read_table_from_stringio(fmtdef, fn, identifiers, block, stringbuf)
