"""Functions to select appropriate Loader subclasses for data objects."""

from __future__ import annotations

import re
from typing import Optional, TYPE_CHECKING

from pdr.formats import check_trivial_case
from pdr.loaders.utility import (
    looks_like_this_kind_of_file,
    DESKTOP_IMAGE_EXTENSIONS,
    FITS_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TABLE_EXTENSIONS,
    TEXT_EXTENSIONS,
)
from pdr.loaders.datawrap import (
    Loader,
    ReadArray,
    ReadCompressedImage,
    ReadFits,
    ReadHeader,
    ReadImage,
    ReadLabel,
    ReadTable,
    ReadText,
    TBD,
    Trivial
)

if TYPE_CHECKING:
    from pdr import Data


def image_lib_dispatch(pointer: str, data: Data) -> Optional[Loader]:
    """
    check file extensions to see if we want to toss a file to an external
    library rather than using our internal raster handling. current cases are:
    pillow for tiff, gif, or jp2; astropy for fits
    """
    object_filename = data._target_path(pointer)
    if looks_like_this_kind_of_file(object_filename, FITS_EXTENSIONS):
        return ReadFits()
    if looks_like_this_kind_of_file(
        object_filename, DESKTOP_IMAGE_EXTENSIONS
    ):
        return ReadCompressedImage()
    return None


def pointer_to_loader(pointer: str, data: Data) -> Loader:
    """
    Attempt to select an appropriate Loader subclass based on a PDS3 object
    name (and sometimes the file extension).

    The apparently-redundant sequence of conditionals is not in fact redundant;
    it is based on our knowledge of the most frequently used but sometimes
    redundant object names in the PDS3 corpus.
    """
    if check_trivial_case(pointer, data.identifiers, data.filename):
        return Trivial()
    if pointer == "LABEL":
        return ReadLabel()
    if image_lib_dispatch(pointer, data) is not None:
        return image_lib_dispatch(pointer, data)
    if (
        "TEXT" in pointer
        or "PDF" in pointer
        or "MAP_PROJECTION_CATALOG" in pointer
    ):
        return ReadText()
    if "DESC" in pointer:  # probably points to a reference file
        return ReadText()
    if "ARRAY" in pointer:
        return ReadArray()
    if "LINE_PREFIX_TABLE" in pointer:
        return TBD()
    table_words = ["TABLE", "SPREADSHEET", "CONTAINER",
                   "SERIES", "SPECTRUM", "HISTOGRAM"]
    if (
        any(val in pointer for val in table_words)
        and not any(val+"_HEADER" in pointer for val in table_words)
        and "HISTOGRAM_IMAGE" not in pointer
    ):
        return ReadTable()
    if "HEADER" in pointer:
        if looks_like_this_kind_of_file(
            data.file_mapping[pointer], FITS_EXTENSIONS
        ):
            return ReadFits()
        return ReadHeader()
    # I have moved this below "table" due to the presence of a number of
    # binary tables named things like "Image Time Table". If there are pictures
    # of tables, we will need to do something more sophisticated.
    if (
        ("IMAGE" in pointer)
        or ("QUB" in pointer)
        or ("XDR_DOCUMENT" in pointer)
    ):
        return ReadImage()
    if "FILE_NAME" in pointer:
        return file_extension_to_loader(pointer)
    return TBD()


def file_extension_to_loader(fn: str) -> Loader:
    """
    Attempt to select the correct Loader subclass for an object based solely on
    its file extension. Used primarily for objects only specified by a PDS3
    FILE_NAME pointer or similar.
    """
    if looks_like_this_kind_of_file(fn, FITS_EXTENSIONS):
        return ReadFits()
    if looks_like_this_kind_of_file(fn, IMAGE_EXTENSIONS):
        return ReadImage()
    if looks_like_this_kind_of_file(fn, TEXT_EXTENSIONS):
        return ReadText()
    if looks_like_this_kind_of_file(fn, TABLE_EXTENSIONS):
        return ReadTable()
    if looks_like_this_kind_of_file(fn, DESKTOP_IMAGE_EXTENSIONS):
        return ReadCompressedImage()
    return TBD()


OBJECTS_TO_IGNORE = ["DATA_SET_MAP_PROJECT.*", ".*_DESC$",
                     ".*DESCRIPTION(_[0-9]*)?$"]
"""
PDS3 objects we do not automatically load, even when loading greedily.
These are reference files, usually throwaway ones, that are usually not
archived in the same place as the data products and add little, if any, context 
to individual products (they are the same across an entire 'product type').
This means that in almost all cases, attempting to greedily load them has no
purpose but to throw irrelevant warnings at the user. 
"""
OBJECTS_IGNORED_BY_DEFAULT = re.compile("|".join(OBJECTS_TO_IGNORE))