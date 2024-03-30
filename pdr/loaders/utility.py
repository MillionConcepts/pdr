from functools import partial
from operator import contains
from pathlib import Path
from typing import Collection
import warnings

from multidict import MultiDict


LABEL_EXTENSIONS = (".xml", ".lbl")
IMAGE_EXTENSIONS = (".img", ".rgb")
TABLE_EXTENSIONS = (".tab", ".csv")
TEXT_EXTENSIONS = (".txt", ".md")
FITS_EXTENSIONS = (".fits", ".fit", ".fits.gz", ".fit.gz", ".fz")
TIFF_EXTENSIONS = (".tif", ".tiff")
JP2_EXTENSIONS = (".jp2", ".jpf", ".jpc", ".jpx")
GIF_EXTENSIONS = (".gif",)


def trivial(*_, **__):
    """
    This is a trivial loader. It does not load. The purpose is to use
    for any pointers we don't want to load and instead simply want ignored.
    It has been superseded by loaders.datawrap.Trivial, and is retained for
    merely sentimental reasons.
    """
    pass


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
