import re
import warnings
from typing import Optional, Callable

import pdr.loaders.handlers
from pdr import check_cases
from pdr.formats import check_special_case
from pdr.loaders._helpers import looks_like_this_kind_of_file
from pdr.loaders.handlers import handle_fits_file, handle_compressed_image
from pdr.parselabel.pds3 import pointerize

LABEL_EXTENSIONS = (".xml", ".lbl")
IMAGE_EXTENSIONS = (".img", ".rgb")
TABLE_EXTENSIONS = (".tab", ".csv")
TEXT_EXTENSIONS = (".txt", ".md")
FITS_EXTENSIONS = (".fits", ".fit")
TIFF_EXTENSIONS = (".tif", ".tiff")
JP2_EXTENSIONS = (".jp2", ".jpf", ".jpc", ".jpx")


def image_lib_dispatch(pointer: str, data: "Data") -> Optional[Callable]:
    """
    check file extensions to see if we want to toss a file to an external
    library rather than using our internal raster handling. current cases are:
    pillow for tiff, astropy for fits
    """
    object_filename = data._target_path(pointer)
    if looks_like_this_kind_of_file(object_filename, FITS_EXTENSIONS):
        return pdr.loaders.handlers.handle_fits_file
    if looks_like_this_kind_of_file(object_filename, TIFF_EXTENSIONS):
        return pdr.loaders.handlers.handle_compressed_image
    if looks_like_this_kind_of_file(object_filename, JP2_EXTENSIONS):
        return pdr.loaders.handlers.handle_compressed_image
    return None


# noinspection PyTypeChecker
def pointer_to_loader(pointer: str, data: "Data") -> Callable:
    """
    attempt to select an appropriate loading function based on a PDS3 pointer
    name. checks for special cases and then falls back to generic loading
    methods of pdr.Data.
    """
    if is_trivial(pointer) is True:
        return data.trivial
    is_special, loader = check_special_case(pointer, data)
    if is_special is True:
        return loader
    if pointer == "LABEL":
        return data.read_label
    if "TEXT" in pointer or "PDF" in pointer or "MAP_PROJECTION_CATALOG" in pointer:
        return data.read_text
    if "DESC" in pointer:  # probably points to a reference file
        return data.read_text
    if "ARRAY" in pointer:
        return data.read_array
    if "LINE_PREFIX_TABLE" in pointer:
        return data.tbd
    if (
        ("TABLE" in pointer)
        or ("SPREADSHEET" in pointer)
        or ("CONTAINER" in pointer)
        or ("TIME_SERIES" in pointer)
        or ("SERIES" in pointer)
        or ("SPECTRUM" in pointer)
    ):
        return data.read_table
    if "HISTOGRAM" in pointer:
        return data.read_histogram
    if "HEADER" in pointer:
        return data.read_header
    # I have moved this below "table" due to the presence of a number of
    # binary tables named things like "Image Time Table". If there are pictures
    # of tables, we will need to do something more sophisticated.
    if ("IMAGE" in pointer) or ("QUB" in pointer):
        # TODO: sloppy pt. 1. this may be problematic for
        #  products with a 'secondary' fits file, etc.
        if image_lib_dispatch(pointer, data) is not None:
            return image_lib_dispatch(pointer, data)
        return data.read_image
    if "FILE_NAME" in pointer:
        return file_extension_to_loader(pointer, data)
    # TODO: sloppy pt. 2
    if image_lib_dispatch(pointer, data) is not None:
        return image_lib_dispatch(pointer, data)
    return data.tbd


def file_extension_to_loader(filename: str, data: "Data") -> Callable:
    """
    attempt to select the correct method of pdr.Data for objects only
    specified by a PDS3 FILE_NAME pointer (or by filename otherwise).
    """
    if looks_like_this_kind_of_file(filename, FITS_EXTENSIONS):
        return handle_fits_file
    if looks_like_this_kind_of_file(filename, TIFF_EXTENSIONS):
        return handle_compressed_image
    if looks_like_this_kind_of_file(filename, IMAGE_EXTENSIONS):
        return data.read_image
    if looks_like_this_kind_of_file(filename, TEXT_EXTENSIONS):
        return data.read_text
    if looks_like_this_kind_of_file(filename, TABLE_EXTENSIONS):
        return data.read_table
    if looks_like_this_kind_of_file(filename, JP2_EXTENSIONS):
        return handle_compressed_image
    return data.tbd


# pointers we do not automatically load even when loading greedily --
# generally these are reference files, usually throwaway ones, that are not
# archived in the same place as the data products and add little, if any,
# context to individual products

objects_to_ignore = [
    "DESCRIPTION", "DATA_SET_MAP_PROJECT.*", ".*_DESC"
]
OBJECTS_IGNORED_BY_DEFAULT = re.compile('|'.join(objects_to_ignore))


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


def ignore_if_pdf(data, object_name, path):
    if looks_like_this_kind_of_file(path, [".pdf"]):
        warnings.warn(
            f"Cannot open {path}; PDF files are not supported."
        )
        block = data.metaget_(object_name)
        if block is None:
            return data.metaget_(pointerize(object_name))
        return block
    return open(check_cases(path)).read()


