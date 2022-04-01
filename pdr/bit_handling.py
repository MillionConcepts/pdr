"""utilities for parsing BIT_COLUMN objects in tables."""

from functools import partial
from pdr.datatypes import determine_byte_order
from pdr.formats import check_special_bit_column_case


def expand_bit_strings(table, fmtdef):
    if "start_bit_list" not in fmtdef.columns:
        return table
    table = convert_to_full_bit_string(table, fmtdef)
    return splice_bit_string(table, fmtdef)


def convert_to_full_bit_string(table, fmtdef):
    for column in fmtdef.index:
        if isinstance(fmtdef.start_bit_list[column], list):
            byte_column = table[fmtdef.NAME[column]]
            byte_order = determine_byte_order(fmtdef.DATA_TYPE[column])
            bit_str_column = convert_byte_column_to_bits(
                byte_column, byte_order
            )
            table[fmtdef.NAME[column]] = bit_str_column
    return table


def convert_to_bits(byte):
    return bin(byte).replace("0b", "").zfill(8)


def convert_byte_str_to_bits(byte_str, byte_order):
    return "".join(
        map(convert_to_bits, conditionally_reverse(byte_str, byte_order))
    )


def convert_byte_column_to_bits(byte_column, byte_order):
    return byte_column.map(
        partial(convert_byte_str_to_bits, byte_order=byte_order)
    )


def conditionally_reverse(iterable, byteorder):
    if byteorder == '<':
        return reversed(iterable)
    return iter(iterable)


def splice_bit_string(table, fmtdef):
    if "start_bit_list" not in fmtdef.columns:
        return
    for column in fmtdef.index:
        if isinstance(fmtdef.start_bit_list[column], list):
            bit_column = table[fmtdef.NAME[column]]
            start_bit_list = [
                val - 1 for val in fmtdef.start_bit_list[column]
            ]  # python zero indexing
            bit_list_column = bit_column.map(
                partial(split_bits, start_bit_list=start_bit_list)
            )
            table[fmtdef.NAME[column]] = bit_list_column
    return table


def split_bits(bit_string, start_bit_list):
    return [
        bit_string[start:end]
        for start, end
        in zip(start_bit_list, start_bit_list[1:]+[None])
    ]


def add_bit_column_info(obj, definition, data):
    if 'BIT_COLUMN' in obj.keys():
        if 'BIT_STRING' not in obj['DATA_TYPE']:
            is_special, special_dtype = check_special_bit_column_case(data)
            if is_special is False:
                raise ValueError("Incompatible data type for bit columns.")
            obj["DATA_TYPE"] = special_dtype

        start_bit_list = []
        list_of_pvl_objects_for_bit_columns = definition.getall("BIT_COLUMN")
        for pvl_obj in list_of_pvl_objects_for_bit_columns:
            start_bit = pvl_obj.get("START_BIT")
            start_bit_list.append(start_bit)
        obj['start_bit_list'] = start_bit_list
    return obj
