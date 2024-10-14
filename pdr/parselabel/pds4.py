"""
Simple utilities for preprocessing pds4_tools-produced label objects for the
pdr.Metadata constructor.
"""
from itertools import chain
from pathlib import Path
import re
from typing import Union

from dustgoggles.func import constant
from dustgoggles.structures import dig_for_keys, dig_for_values
from lxml import etree
from multidict import MultiDict

from pdr.parselabel.utils import levelpick

STRIP_NS = re.compile(r"^{.*?}")


def simple_elpath(node: etree._Element) -> str:
    return '/'.join(
        STRIP_NS.sub('', n.tag)
        for n in chain(reversed(tuple(node.iterancestors())), (node,))
    )


# TODO: should probably make namespace stripping optional
#  but it's faster if I don't
# TODO: do we have to worry about any other Python typecasting
#  cases? PDS4 doesn't use weird tuple types etc, it
#  represents that sort of metadata with higher-cardinality
#  XML types, or by explicitly naming the elements of
#  the tuple as separate XML types (e.g., compare
#  ROVER_MOTION_COUNTER to geom:Motion_Counter)
# TODO: is there a cleaner way to do this? I
#  sort of think there's not unless we literally look at
#  the XML schema and build a mapping from it, which seems
#  like a big pain and also very slow if we do it dynamically
#  (although we shouldn't need to).
# NOTE: intentionally ignores attributes on nodes with children
# TODO, maybe: convoluted but I don't want all the extra function
#  calls, maybe doesn't matter, will check
def node_to_multidict(node: etree._Element) -> MultiDict:
    nodemap = MultiDict()
    for child in node:
        tag = STRIP_NS.sub('', child.tag)
        cval = None if child.text is None else child.text.strip()
        if cval not in (None, ''):
            if len(child) > 0:
                raise NotImplementedError(
                    f"Mixed text / element content is not supported "
                    f"(founud in {simple_elpath(node)})"
                )
            if cval is not None:
                for ptype in (int, float):
                    try:
                        cval = ptype(cval)
                        break
                    except ValueError:
                        pass
            if len(child.attrib) > 0:
                cval = {'value': cval} | dict(child.attrib)
            nodemap.add(tag, cval)
        elif len(child) > 0:
            nodemap.add(tag, node_to_multidict(child))
        else:
            nodemap.add(tag, None)
    return nodemap


def read_xml(label_fn: Union[str, Path]) -> tuple[MultiDict, list[str]]:
    with open(label_fn, "rb") as stream:
        root = etree.fromstring(stream.read())
    labeldict = node_to_multidict(root)
    # collect all tag names to populate pdr.Metadata's fieldcounts attribute
    params = dig_for_keys(
        labeldict, None, base_pred=constant(True), mtypes=(MultiDict,)
    )
    return labeldict, params


def get_pds4_index(unpacked: MultiDict) -> list[str]:
    index = dig_for_values(unpacked, "local_identifier", mtypes=(MultiDict,))
    if len(set(index)) == len(index):
        return index
    raise NotImplementedError(
        "Duplicate local_identifier not supported for PDS4 products."
    )


def get_pds4_fn(unpacked: MultiDict, objname: str) -> str:
    return levelpick(
        unpacked,
        lambda k, v: k == 'local_identifier' and v == objname,
        1,
        (MultiDict,)
    )['File']['file_name']
