import Levenshtein as lev
import numpy as np
from multidict import MultiDict


def handle_fits_file(data, filename, name=""):
    """
    This function attempts to read all FITS files, compressed or
    uncompressed, with astropy.io.fits. Files with 'HEADER' pointer
    return the header, all others return data.
    TODO, maybe: dispatch to decompress() for weirdo compression
      formats, but possibly not right here? hopefully we shouldn't need
      to handle compressed FITS files too often anyway.
    """
    from astropy.io import fits

    hdulist = fits.open(filename)
    hdr_val = handle_fits_header(hdulist, name)
    if "HEADER" in name:
        return hdr_val
    else:
        # TODO: add header key in queries so we don't need to pass a data
        #  object here?
        hdr_key = name + "_HEADER"
        setattr(data, hdr_key, hdr_val)
        data.index += [hdr_key]
    return hdulist[pointer_to_fits_key(name, hdulist)].data


def handle_compressed_image(filename):
    from PIL import Image

    # deactivate pillow's DecompressionBombError: many planetary images
    # are legitimately very large
    Image.MAX_IMAGE_PIXELS = None
    # noinspection PyTypeChecker
    image = np.ascontiguousarray(Image.open(filename)).copy()
    # pillow reads images as [x, y, channel] rather than [channel, x, y]
    if len(image.shape) == 3:
        return np.ascontiguousarray(np.rollaxis(image, 2))
    return image


def handle_fits_header(
    hdulist,
    name="",
):
    astro_hdr = hdulist[pointer_to_fits_key(name, hdulist)].header
    output_hdr = MultiDict()
    for key, val, com in astro_hdr.cards:
        if len(key) > 0:
            if isinstance(val, (str, float, int)):
                output_hdr.add(key, val)
            else:
                output_hdr.add(key, str(val))
            if len(com) > 0:
                comment_key = key + "_comment"
                output_hdr.add(comment_key, com)
    return output_hdr


def pointer_to_fits_key(pointer, hdulist):
    """
    In some datasets with FITS, the PDS3 object names and FITS object
    names are not identical. This function attempts to use Levenshtein
    "fuzzy matching" to identify the correlation between the two. It is not
    guaranteed to be correct! And special case handling might be required in
    the future.
    """
    if pointer in ("IMAGE", "TABLE", None, ""):
        # TODO: sometimes the primary HDU contains _just_ a header.
        #  (e.g., GALEX raw6, which is not in scope, but I'm sure something in
        #  the PDS does this awful thing too.) it might be a good idea to have
        #  a heuristic for, when we are implicitly looking for data, walking
        #  forward until we find a HDU that actually has something in it...
        #  or maybe just populating multiple keys from the HDU names.
        return 0
    levratio = [
        lev.ratio(i[1].lower(), pointer.lower())
        for i in hdulist.info(output=False)
    ]
    return levratio.index(max(levratio))


def add_bit_column_info(obj, definition, identifiers):
    if "BIT_COLUMN" not in obj.keys():
        return obj
    from pdr.bit_handling import (
        set_bit_string_data_type, get_bit_start_and_size
    )
    if "BIT_STRING" not in obj["DATA_TYPE"]:
        obj = set_bit_string_data_type(obj, identifiers)
    return get_bit_start_and_size(obj, definition, identifiers)
