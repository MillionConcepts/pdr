"""Support objects for 'utility' Loader subclasses."""

from functools import partial
from itertools import chain
from operator import contains
from pathlib import Path
from typing import Collection
import warnings

from multidict import MultiDict


# TODO, maybe: I think we should keep these somewhere else; they're certainly
#  not used exclusively in loaders

LABEL_EXTENSIONS = (".xml", ".lbl")
IMAGE_EXTENSIONS = (".img", ".rgb")
TABLE_EXTENSIONS = (".tab", ".csv")
TEXT_EXTENSIONS = (".txt", ".md")
FITS_EXTENSIONS = (".fits", ".fit", ".fits.gz", ".fit.gz", ".fz")
TIFF_EXTENSIONS = (".tif", ".tiff")
JP2_EXTENSIONS = (".jp2", ".jpf", ".jpc", ".jpx")
GIF_EXTENSIONS = (".gif",)
JPEG_EXTENSIONS = (".jpg", ".jpeg")
PNG_EXTENSIONS = (".png",)
COMPRESSED_IMAGE_EXTENSION_HASH = {
    "TIFF": TIFF_EXTENSIONS,
    "JP2": JP2_EXTENSIONS,
    "JPEG": JPEG_EXTENSIONS,
    "GIF": GIF_EXTENSIONS,
    "PNG": PNG_EXTENSIONS
}
COMPRESSED_IMAGE_FORMATS = tuple(COMPRESSED_IMAGE_EXTENSION_HASH.keys())
COMPRESSED_IMAGE_EXTENSIONS = tuple(
    chain(*COMPRESSED_IMAGE_EXTENSION_HASH.values())
)


def trivial(*_, **__):
    """
    This is a trivial loader. It does not load. The purpose is to use
    for any pointers we don't want to load and instead simply want ignored.
    """
    pass


def tbd(name: str, block: MultiDict, *_, **__):
    """
    This is a placeholder function for objects that are not explicitly
    supported elsewhere. It throws a warning and
    passes just the value of the pointer.
    """
    warnings.warn(f"The {name} pointer is not yet fully supported.")
    return block


def looks_like_this_kind_of_file(
    filename: str, kind_extensions: Collection[str]
) -> bool:
    """Does this file have any of these extensions?"""
    is_this_kind_of_extension = partial(contains, kind_extensions)
    return any(map(is_this_kind_of_extension, Path(filename.lower()).suffixes))


def is_trivial(pointer: str) -> bool:
    """
    Returns True if this is the name of a data object we want to handle
    trivally, in the sense that we never ever want to load it directly.
    """
    # TIFF tags / headers should always be parsed by the TIFF parser itself
    if (
        ("TIFF" in pointer)
        and ("IMAGE" not in pointer)
        and ("DOCUMENT" not in pointer)
    ):
        return True
    # we don't present STRUCTURES separately from their tables
    if "STRUCTURE" in pointer:
        return True
    return False
