"""
Simple utilities for preprocessing pds4_tools-produced label objects for the
pdr.Metadata constructor.
"""
from collections import OrderedDict
from typing import Any, Hashable, Mapping, MutableSequence, TYPE_CHECKING

from dustgoggles.func import constant
from dustgoggles.structures import dig_and_edit
from multidict import MultiDict

from pdr.parselabel.pds3 import multidict_dig_and_edit

if TYPE_CHECKING:
    from pds4_tools.reader.label_objects import Label


def log_and_pass(sequence: MutableSequence, key: Hashable, value: Any) -> Any:
    """
    Setter function for `dig_and_edit` that causes it to simply populate a
    list of all keys at all levels of the MultiDict (so in effect not really a
    'setter' function).
    """
    sequence.append(key)
    return value


def unpack_to_multidict(packed: Mapping, mtypes=(dict,)) -> MultiDict:
    """
    Produce a MultiDict from any Mapping, with every element of `packed` that
    is a list/tuple of `mtypes` converted into a seperate key of the
    `MultiDict`, and other values unchanged.

    For instance:
    ```
    >>> unpack_to_multidict({'a': 1, 'b': [{'c': 2}, {'d': 3}]})
    MultiDict({'a': 1, 'b': {'c': 2}, 'b': {'d': 3})
    ```
    """
    unpacked = MultiDict()
    for k, v in packed.items():
        if isinstance(v, (list, tuple)):
            if all([isinstance(thing, mtypes) for thing in v]):
                for thing in v:
                    unpacked.add(k, thing)
        else:
            unpacked.add(k, v)
    return unpacked


def unpack_if_mapping(
    possibly_packed: Any, mtypes: tuple[type, ...] = (dict,)
) -> Any:
    """
    Setter function for `multidict_dig_and_edit()`. Converts any element of
    `mtypes` into a MultiDict with mapping array values 'unpacked' as
    described above.
    """
    if isinstance(possibly_packed, mtypes):
        return unpack_to_multidict(MultiDict(possibly_packed))
    return possibly_packed


# noinspection PyTypeChecker
def reformat_pds4_tools_label(label: "Label") -> tuple[MultiDict, list[str]]:
    """
    Convert a pds4_tools Label object into a MultiDict and a list of parameters
    suitable for constructing a pdr.Metadata object. This is not just a type
    conversion; it also rearranges some nested data structures (in particular,
    repeated child elements become multiple keys of a MultiDict rather than
    a list of OrderedDicts).
    """
    mtypes = (OrderedDict, MultiDict)
    result = multidict_dig_and_edit(
        label.to_dict(),
        predicate=lambda _, __, ___: True,
        setter_function=lambda _, v: unpack_if_mapping(v, mtypes),
        mtypes=mtypes,
    )
    params = []
    # collect all keys to populate pdr.Metadata's fieldcounts attribute
    dig_and_edit(
        result,
        constant(True),
        lambda k, v: log_and_pass(params, k, v),
        mtypes=(MultiDict,),
    )
    return result, params
