"""
Utilities for dealing with 'desktop'-format images using pillow.

TODO: not all of this ultimately goes here. Also, we might want to use opencv
 for some things instead.
"""
from io import BytesIO
import re
from pathlib import Path
from typing import Any, Union, Mapping
from xml.etree import ElementTree

from dustgoggles.func import constant
from dustgoggles.structures import dig_for_keys
from multidict import MultiDict

try:
    from PIL import Image
    from PIL.ExifTags import GPSTAGS, TAGS
    from PIL.ImageCms import ImageCmsProfile
    from PIL.TiffTags import lookup
except ImportError:
    raise ModuleNotFoundError

NS_PATTERN = re.compile("{.*?}")


def unpack_icp(icp_blob: bytes):
    unpacked = {}
    for attr in dir((icp := ImageCmsProfile(BytesIO(icp_blob)).profile)):
        if attr.startswith("__"):
            continue
        if callable((obj := getattr(icp, attr))):
            continue
        unpacked[attr] = obj
    return unpacked


def add_gps_ifd(im: Image, gps_tagname: int):
    gpsdict = im.getexif().get_ifd(gps_tagname)
    return {GPSTAGS[k].replace('GPS', ''): v for k, v in gpsdict.items()}


def get_image_metadata(im: Image):
    outdict = {}
    meta = list(im.getexif().items())
    if hasattr(im, "mpinfo"):
        meta += list(im.mpinfo.items())
    for tag, val in meta:
        if tag in TAGS.keys():
            name = TAGS[tag]
        elif (
            im.format in ("TIFF", "MPO")
            and (tname := lookup(tag).name) != "unknown"
        ):
            name = tname
        else:
            name = str(tag)
        if name == 'GPSInfo':
            outdict |= add_gps_ifd(im, tag)
        elif name == 'XMLPacket':
            outdict[name] = unpack_xml(ElementTree.fromstring(val))
        elif name == 'InterColorProfile':
            outdict[name] = unpack_icp(val)
        else:
            outdict[name] = val
    return outdict


def strip_ns(tag):
    return NS_PATTERN.sub("", tag)


def maybestrip_ns(obj, do_remove):
    text = obj.tag if isinstance(obj, ElementTree.Element) else obj
    return text if do_remove is False else strip_ns(text)


def pick_text_attrib(node, remove_ns=True):
    has_text = node.text is not None and node.text.strip() != ''
    if has_text and len(node) > 0:
        raise SyntaxError(
            f"Can't parse text-containing parent node {node.tag}"
        )
    has_attrib = len(node.attrib) != 0
    if has_text is has_attrib is False:
        return None
    if has_attrib is False:
        return node.text.strip()
    attrib = {
        maybestrip_ns(k, remove_ns): v for k, v in node.attrib.items()
    }
    if has_text is True:
        return {'attrib': attrib, 'text': node.text.strip()}
    return attrib


def paramdig(unpacked: Mapping) -> tuple[Mapping, list[str]]:
    return unpacked, dig_for_keys(
        unpacked, None, base_pred=constant(True), mtypes=(MultiDict, dict)
    )


# TODO: probably want more!
IMAGE_META_ATTRS = (
    'mode',
    'size',
    'width',
    'height',
    'format',
    'format_description',
    'n_frames',
)


def unpack_xml(root: ElementTree.Element, remove_ns: bool = True) -> Any:
    pick = pick_text_attrib(root, remove_ns)
    if len(root) == 0:
        return pick
    if pick is not None:
        # should only ever be dict or None for a non-terminal node
        xmd = MultiDict(pick)
    else:
        xmd = MultiDict()
    for node in root:
        unpacked = unpack_xml(node, remove_ns)
        if unpacked is None or len(unpacked) == 0:
            continue
        xmd.add(maybestrip_ns(node, remove_ns), unpacked)
    return xmd


# TODO, maybe: decode ImageResources (see kings_river_canyon.tiff)
def skim_image_data(fn: Union[str, Path]) -> dict:
    im, meta = Image.open(fn), {'fn': str(fn)}
    for attr in IMAGE_META_ATTRS:
        if (val := getattr(im, attr, None)) is None:
            continue
        meta[attr] = val
    meta['mimetype'] = Image.MIME[meta['format']]
    if (pal := getattr(im, 'palette', None)) is not None:
        # TODO, maybe: I hate that they use the color as the key and the
        #  palette index as the value, but keeping it now for compatibility
        meta['palette'] = pal.colors
    # NOTE: this looks at TIFF tags for TIFFs by default
    return meta | get_image_metadata(im)
