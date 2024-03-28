import re
import numpy as np
import pandas as pd
from io import StringIO
from pandas.errors import ParserError

from pdr.loaders._helpers import check_explicit_delimiter
from pdr.loaders.queries import get_array_num_items
from pdr import bit_handling
from pdr.datatypes import sample_types
from pdr.np_utils import np_from_buffered_io, enforce_order_and_object
from pdr.pd_utils import booleanize_booleans, convert_ebcdic, convert_ibm_reals, compute_offsets
from pdr.utils import decompress, head_file


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
    Read a table. Parse the label format definition and then decide
    whether to parse it as text or binary.
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
#        print("columns\n", table.columns)
#        print("names\n", fmtdef['NAME'])
#        print("last\n", table.iloc[-1, 0])
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


# TODO: this is still generally hacky and should be untangled
# noinspection PyTypeChecker
def _interpret_as_ascii(identifiers, fn, fmtdef, block, table_props):
    """
    read an ASCII table. first assume it's delimiter-separated; attempt to
    parse it as a fixed-width table if that fails.
    """
    # TODO, maybe: add better delimiter detection & dispatch
    sep = check_explicit_delimiter(block)
    with decompress(fn) as f:
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
    # TODO: I'm not sure this except clause is a good idea.
    except (UnicodeError, AttributeError, ParserError):
        table = None
    if table is None:
        try:
            table = pd.DataFrame(
                # TODO: are we ever actually using this at this point? note
                #  that it will never work for compressed files.
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
        except (TypeError, KeyError, ValueError):
            pass
    if table is not None:
        # TODO: adding this placeholder check allows many tables to use
        #  read_csv() instead of read_fwf(). This may be able to invalidate
        #  some special cases; should check.
        n_place = len(
            fmtdef.loc[fmtdef.NAME.str.contains('PLACEHOLDER')]
        )
        if len(table.columns) + n_place == len(fmtdef.NAME.tolist()):
            string_buffer.close()
            return table
    string_buffer.seek(0)
    if "BYTES" in fmtdef.columns:
        try:
            if "SB_OFFSET" not in fmtdef.columns:
                colspecs, position_records = [], compute_offsets(fmtdef).to_dict("records")
            else:
                colspecs, position_records = [], fmtdef.to_dict("records")
            for record in position_records:
                if np.isnan(record.get("ITEM_BYTES", np.nan)):
                    col_length = record["BYTES"]
                else:
                    col_length = int(record["ITEM_BYTES"])
                colspecs.append(
                    (record["SB_OFFSET"], record["SB_OFFSET"] + col_length)
                )
            table = pd.read_fwf(string_buffer, header=None, colspecs=colspecs, delimiter='\t'+' '+'"'+',')
            string_buffer.close()
            return table
        except (pd.errors.EmptyDataError, pd.errors.ParserError):
            string_buffer.seek(0)
    table = pd.read_fwf(string_buffer, header=None, delimiter='\t'+' '+'"'+',')
    string_buffer.close()
    return table
