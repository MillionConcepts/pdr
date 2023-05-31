import re
import numpy as np
import pandas as pd
from io import StringIO
from pandas.errors import ParserError

from pdr.loaders._helpers import check_explicit_delimiter
from pdr.loaders.queries import get_array_num_items, check_array_for_subobject
from pdr import bit_handling
from pdr.datatypes import sample_types
from pdr.np_utils import np_from_buffered_io, enforce_order_and_object
from pdr.pd_utils import booleanize_booleans
from pdr.utils import decompress, head_file


def read_array(filename, block, start_byte):
    """
    Read an array object from this product and return it as a numpy array.
    """
    # TODO: Maybe add block[AXES] as names? Might have to switch to pandas
    #  or a flattened structured array or something weirder
    obj = check_array_for_subobject(block)
    if block.get("INTERCHANGE_FORMAT") == "BINARY":
        with decompress(filename) as f:
            binary = np_from_buffered_io(
                f,
                dtype=sample_types(obj["DATA_TYPE"], obj["BYTES"], True),
                count=get_array_num_items(block),
                offset=start_byte,
            )
        return binary.reshape(block["AXIS_ITEMS"])
    # assume objects without the optional interchange_format key are ascii
    with open(filename) as stream:
        text = stream.read()
    try:
        text = tuple(map(float, re.findall(r"[+-]?\d+\.?\d*", text)))
    except (TypeError, IndexError, ValueError):
        text = re.split(r"\s+", text)
    array = np.asarray(text).reshape(block["AXIS_ITEMS"])
    if "DATA_TYPE" in obj.keys():
        array = array.astype(
            sample_types(obj["DATA_TYPE"], obj["BYTES"], True)
        )
    return array


def read_table(
    identifiers,
    filename,
    fmtdef_dt,
    table_props,
    block,
    start_byte,
    debug,
):
    """
    Read a table. Parse the label format definition and then decide
    whether to parse it as text or binary.
    """
    fmtdef, dt = fmtdef_dt
    if dt is None:  # we believe object is an ascii file
        table = _interpret_as_ascii(
            identifiers, filename, fmtdef, block, table_props
        )
        table.columns = fmtdef.NAME.tolist()
    else:
        table = _interpret_as_binary(filename, fmtdef, dt, block, start_byte)
    # If there were any cruft "placeholder" columns, discard them
    table = table.drop(
        [k for k in table.keys() if "PLACEHOLDER" in k], axis=1
    )
    return table


def _interpret_as_binary(fn, fmtdef, dt, block, start_byte):
    # TODO: this works poorly (from a usability and performance
    #  perspective; it's perfectly stable) for tables defined as
    #  a single row with tens or hundreds of thousands of columns
    count = block.get("ROWS")
    count = count if count is not None else 1
    with decompress(fn) as f:
        array = np_from_buffered_io(
            f, dtype=dt, offset=start_byte, count=count
        )
    swapped = enforce_order_and_object(array, inplace=False)
    table = pd.DataFrame(swapped)
    table.columns = fmtdef.NAME.tolist()
    table = booleanize_booleans(table, fmtdef)
    table = bit_handling.expand_bit_strings(table, fmtdef)
    return table


# noinspection PyTypeChecker
def _interpret_as_ascii(identifiers, filename, fmtdef, block, table_props):
    """
    read an ASCII table. first assume it's delimiter-separated; attempt to
    parse it as a fixed-width table if that fails.
    """
    # TODO, maybe: add better delimiter detection & dispatch
    sep = check_explicit_delimiter(block)
    with decompress(filename) as f:
        if table_props["as_rows"] is False:
            bytes_buffer = head_file(
                f, nbytes=table_props["length"], offset=table_props["start"]
            )
            string_buffer = StringIO(bytes_buffer.read().decode())
            bytes_buffer.close()
        else:
            if table_props["start"] > 0:
                [next(f) for _ in range(table_props["start"])]
            if table_props["length"] in (None, ""):
                lines = f.readlines()
            else:
                lines = [next(f) for _ in range(table_props["length"])]
            string_buffer = StringIO("\r\n".join(map(bytes.decode, lines)))
        string_buffer.seek(0)
    try:
        table = pd.read_csv(string_buffer, sep=sep, header=None)
    # TODO: I'm not sure this is a good idea
    # TODO: hacky, untangle this tree
    # TODO: this won't work for compressed files, but I'm not even
    #  sure what we're using it for right now
    except (UnicodeError, AttributeError, ParserError):
        table = None
    if table is None:
        try:
            table = pd.DataFrame(
                np.loadtxt(
                    filename,
                    delimiter=",",
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
        except (TypeError, KeyError, ValueError):
            pass
    if table is not None:
        try:
            assert len(table.columns) == len(fmtdef.NAME.tolist())
            string_buffer.close()
            return table
        except AssertionError:
            pass
    # TODO: handle this better
    string_buffer.seek(0)
    if "BYTES" in fmtdef.columns:
        try:
            from pdr.pd_utils import compute_offsets

            colspecs = []
            position_records = compute_offsets(fmtdef).to_dict("records")
            for record in position_records:
                if np.isnan(record.get("ITEM_BYTES", np.nan)):
                    col_length = record["BYTES"]
                else:
                    col_length = int(record["ITEM_BYTES"])
                colspecs.append(
                    (record["OFFSET"], record["OFFSET"] + col_length)
                )
            table = pd.read_fwf(string_buffer, header=None, colspecs=colspecs)
            string_buffer.close()
            return table
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            string_buffer.seek(0)
    table = pd.read_fwf(string_buffer, header=None)
    string_buffer.close()
    return table
