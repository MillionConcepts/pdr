"""
simple utilities for preprocessing pds4_tools-produced label objects for the
pdr.Metadata constructor.
"""
from collections import OrderedDict

from dustgoggles.func import constant
from dustgoggles.structures import dig_and_edit
from multidict import MultiDict


def log_and_pass(sequence, key, value):
    sequence.append(key)
    return value


def unpack_to_multidict(packed, mtypes=(dict,)):
    unpacked = MultiDict()
    for k, v in packed.items():
        if isinstance(v, (list, tuple)):
            if all([isinstance(thing, mtypes) for thing in v]):
                for thing in v:
                    unpacked[k] = thing
        else:
            unpacked[k] = v
    return unpacked


def unpack_if_mapping(possibly_packed, mtypes=(dict,)):
    if isinstance(possibly_packed, mtypes):
        return unpack_to_multidict(possibly_packed)
    return possibly_packed


# noinspection PyTypeChecker
def reformat_pds4_tools_label(label):
    result = dig_and_edit(
        label.to_dict(),
        constant(True),
        lambda _, v: unpack_if_mapping(v, (OrderedDict, MultiDict)),
        mtypes=(OrderedDict, MultiDict)
    )
    params = []
    # collect all keys to populate pdr.Metadata's fieldcounts attribute
    dig_and_edit(
        result,
        constant(True),
        lambda k, v: log_and_pass(params, k, v),
        mtypes=(MultiDict,)
    )
    return result, params
