"""
Simple utilities for preprocessing pds4_tools-produced label objects for the
pdr.Metadata constructor.
"""
from collections import OrderedDict
from typing import Mapping, TYPE_CHECKING

from dustgoggles.func import constant
from dustgoggles.structures import dig_for_keys
from multidict import MultiDict


if TYPE_CHECKING:
    from pdr.pds4_tools.reader.label_objects import Label


def unpack_to_multidict(
    packed: Mapping, mtypes: tuple[type, ...] = (dict,)
) -> MultiDict:
    """
    Recursively unpack any Mapping into a MultiDict. Unpacks all list or tuple
    values at any level into multiple keys at that level. This is an unusual-
    sounding behavior but is generally appropriate for PDS4 labels, and
    specifically for the pds4_tools representation of XML labels. PDS4 types
    with cardinality > 1 always (?) represent multiple distinct entities /
    properties rather than an array of properties. The list can also always be
    retrieved from the resulting multidict with `MultiDict.get_all()`.

    Example:
    ```
    >>> unpack_to_multidict({'a': 1, 'b': [{'c': 2}, 3]})
    <MultiDict('a': 1, 'b': <MultiDict('c': 2)>, 'b': 3)>
    ```
    """
    unpacked, items = MultiDict(), list(reversed(packed.items()))
    while len(items) > 0:
        k, v = items.pop()
        if isinstance(v, (list, tuple)):
            items += [(k, e) for e in reversed(v)]
        elif isinstance(v, mtypes):
            unpacked.add(k, unpack_to_multidict(v, mtypes))
        else:
            unpacked.add(k, v)
    return unpacked


# noinspection PyTypeChecker
def reformat_pds4_tools_label(label: "Label") -> tuple[MultiDict, list[str]]:
    """
    Convert a pds4_tools Label object into a MultiDict and a list of parameters
    suitable for constructing a pdr.Metadata object. This is not just a type
    conversion; it also rearranges some nested data structures (in particular,
    repeated child elements become multiple keys of a MultiDict rather than
    a list of OrderedDicts).
    """
    unpacked = unpack_to_multidict(label.to_dict(), (OrderedDict, MultiDict))
    # collect all keys to populate pdr.Metadata's fieldcounts attribute
    params = dig_for_keys(
        unpacked, None, base_pred=constant(True), mtypes=(MultiDict,)
    )
    return unpacked, params
