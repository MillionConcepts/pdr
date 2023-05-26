import warnings
from functools import partial
from operator import contains
from pathlib import Path
from multidict import MultiDict


LABEL_EXTENSIONS = (".xml", ".lbl")
IMAGE_EXTENSIONS = (".img", ".rgb")
TABLE_EXTENSIONS = (".tab", ".csv")
TEXT_EXTENSIONS = (".txt", ".md")
FITS_EXTENSIONS = (".fits", ".fit")
TIFF_EXTENSIONS = (".tif", ".tiff")
JP2_EXTENSIONS = (".jp2", ".jpf", ".jpc", ".jpx")


def trivial(*_, **__):
    """
    This is a trivial loader. It does not load. The purpose is to use
    for any pointers we don't want to load and instead simply want ignored.
    """
    pass


def tbd(name: str, block: MultiDict, *_, **__):
    """
    This is a placeholder function for pointers that are
    not explicitly supported elsewhere. It throws a warning and
    passes just the value of the pointer.
    """
    warnings.warn(f"The {name} pointer is not yet fully supported.")
    return block


def looks_like_this_kind_of_file(filename: str, kind_extensions) -> bool:
    is_this_kind_of_extension = partial(contains, kind_extensions)
    return any(
        map(is_this_kind_of_extension, Path(filename.lower()).suffixes)
    )


def is_trivial(pointer) -> bool:
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
