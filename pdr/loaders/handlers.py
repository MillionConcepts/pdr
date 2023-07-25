import Levenshtein as lev
import numpy as np
from multidict import MultiDict


def handle_fits_file(fn, name="", hdu_name=""):
    """
    This function attempts to read all FITS files, compressed or
    uncompressed, with astropy.io.fits. Files with 'HEADER' pointer
    return the header, all others return data.

    we distinguish name and hdu_name as a slightly hacky way to facilitate
    special cases in which we explicitly map a PDS pointer to a FITS HDU name.

    TODO, maybe: dispatch to decompress() for weirdo compression
      formats, but possibly not right here? hopefully we shouldn't need
      to handle compressed FITS files too often anyway, and astropy can deal
      with gzip without special help (although inline igzip is faster)
    """
    from astropy.io import fits

    hdulist = fits.open(fn)
    try:
        hdr_val = handle_fits_header(hdulist, hdu_name)
    # astropy.io.fits does not call any verification on read. on 'output'
    # tasks -- which iterating over header cards (sometimes) counts as, and
    # which we have to do in order to place the header content into our
    # preferred data structure -- it does call verification, at the strictest
    # settings. we do not want to prospectively fix every case because it is
    # quite slow. so, when astropy.io.fits decides something is too invalid to
    # show us, tell it to fix it first.
    except fits.VerifyError:
        hdulist.verify('silentfix')
        hdr_val = handle_fits_header(hdulist, hdu_name)
    if (
        "HEADER" not in hdu_name
        # cases where HDUs are named things like "IMAGE HEADER"
        or hdu_name in [h[1] for h in hdulist.info(False)]
    ):
        output = {f"{name}_HEADER": hdr_val}
    else:
        return {name: hdr_val}
    body = hdulist[pointer_to_fits_key(hdu_name, hdulist)].data
    # i.e., it's a FITS table
    if isinstance(body, fits.fitsrec.FITS_rec):
        import pandas as pd
        from pdr.np_utils import enforce_order_and_object

        body = pd.DataFrame.from_records(enforce_order_and_object(body))
    return output | {name: body}


def handle_compressed_image(fn):
    from PIL import Image

    # deactivate pillow's DecompressionBombError: many planetary images
    # are legitimately very large
    Image.MAX_IMAGE_PIXELS = None
    # noinspection PyTypeChecker
    image = np.ascontiguousarray(Image.open(fn)).copy()
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
    obj["DATA_TYPE"] = obj["DATA_TYPE"].replace(" ", "_")
    if "BIT_STRING" not in obj["DATA_TYPE"]:
        obj = set_bit_string_data_type(obj, identifiers)
    return get_bit_start_and_size(obj, definition, identifiers)
