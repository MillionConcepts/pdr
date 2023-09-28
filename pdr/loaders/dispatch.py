import re
from typing import Optional, Callable
from pdr.formats import check_trivial_case
from pdr.loaders.utility import (
    looks_like_this_kind_of_file,
    FITS_EXTENSIONS,
    TIFF_EXTENSIONS,
    JP2_EXTENSIONS,
    IMAGE_EXTENSIONS,
    TABLE_EXTENSIONS,
    TEXT_EXTENSIONS,
)
from pdr.loaders.datawrap import (
    ReadLabel,
    ReadArray,
    ReadFits,
    ReadText,
    ReadImage,
    ReadHeader,
    ReadCompressedImage,
    ReadTable,
    TBD,
    Trivial
)


def image_lib_dispatch(pointer: str, data: "Data") -> Optional[Callable]:
    """
    check file extensions to see if we want to toss a file to an external
    library rather than using our internal raster handling. current cases are:
    pillow for tiff, astropy for fits
    """
    object_filename = data._target_path(pointer)
    if looks_like_this_kind_of_file(object_filename, FITS_EXTENSIONS):
        return ReadFits()
    if looks_like_this_kind_of_file(object_filename, TIFF_EXTENSIONS):
        return ReadCompressedImage()
    if looks_like_this_kind_of_file(object_filename, JP2_EXTENSIONS):
        return ReadCompressedImage()
    return None


# noinspection PyTypeChecker
def pointer_to_loader(pointer: str, data: "Data") -> Callable:
    """
    attempt to select an appropriate loading function based on a PDS3 pointer
    name. checks for special cases and then falls back to generic loading
    methods of pdr.Data.
    """
    if check_trivial_case(
        pointer, data.identifiers, data.filename
    ):
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
    if (
        ("TABLE" in pointer)
        or ("SPREADSHEET" in pointer)
        or ("CONTAINER" in pointer)
        or ("TIME_SERIES" in pointer)
        or ("SERIES" in pointer)
        or ("SPECTRUM" in pointer)
    ):
        return ReadTable()
    if "HEADER" in pointer:
        if looks_like_this_kind_of_file(
            data.file_mapping[pointer], FITS_EXTENSIONS
        ):
            return ReadFits()
        return ReadHeader()
    if "HISTOGRAM" in pointer:
        return ReadTable()
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
    # TODO: sloppy pt. 2
    return TBD()


def file_extension_to_loader(fn: str) -> Callable:
    """
    attempt to select the correct method of pdr.Data for objects only
    specified by a PDS3 FILE_NAME pointer (or by filename otherwise).
    """
    if looks_like_this_kind_of_file(fn, FITS_EXTENSIONS):
        return ReadFits()
    if looks_like_this_kind_of_file(fn, TIFF_EXTENSIONS):
        return ReadCompressedImage()
    if looks_like_this_kind_of_file(fn, IMAGE_EXTENSIONS):
        return ReadImage()
    if looks_like_this_kind_of_file(fn, TEXT_EXTENSIONS):
        return ReadText()
    if looks_like_this_kind_of_file(fn, TABLE_EXTENSIONS):
        return ReadTable()
    if looks_like_this_kind_of_file(fn, JP2_EXTENSIONS):
        return ReadCompressedImage()
    return TBD()


# pointers we do not automatically load even when loading greedily --
# generally these are reference files, usually throwaway ones, that are not
# archived in the same place as the data products and add little, if any,
# context to individual products

objects_to_ignore = ["DATA_SET_MAP_PROJECT.*", ".*_DESC$", ".*DESCRIPTION$"]
OBJECTS_IGNORED_BY_DEFAULT = re.compile("|".join(objects_to_ignore))
