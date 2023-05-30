"""
functions to construct query structures. primarily intended to delay imports.
"""
from types import MappingProxyType


def default_data_queries():
    from pdr.formats import check_special_block, check_special_offset
    from pdr.func import specialize
    from pdr.loaders.queries import (
        get_identifiers,
        get_block,
        get_file_mapping,
        get_target,
        data_start_byte,
        get_debug,
        get_return_default,
    )

    return MappingProxyType(
        {
            "identifiers": get_identifiers,
            "block": specialize(get_block, check_special_block),
            "filename": get_file_mapping,
            "target": get_target,
            "start_byte": specialize(data_start_byte, check_special_offset),
            "debug": get_debug,
            "return_default": get_return_default,
        }
    )
