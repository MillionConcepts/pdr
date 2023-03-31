from multidict import MultiDict
import Levenshtein as lev
import numpy as np


def handle_fits_file(self, pointer=""):
    """
    This function attempts to read all FITS files, compressed or
    uncompressed, with astropy.io.fits. Files with 'HEADER' pointer
    return the header, all others return data.
    TODO, maybe: dispatch to decompress() for weirdo compression
      formats, but possibly not right here? hopefully we shouldn't need
      to handle compressed FITS files too often anyway.
    """
    from astropy.io import fits

    try:
        hdulist = fits.open(self.file_mapping[pointer])
        if "HEADER" in pointer:
            return handle_fits_header(hdulist, pointer)
        else:
            hdr_key = pointer+"_HEADER"
            hdr_val = handle_fits_header(hdulist, pointer)
            setattr(self, hdr_key, hdr_val)
            self.index += [hdr_key]
        return hdulist[pointer_to_fits_key(pointer, hdulist)].data
    except Exception as ex:
        # TODO: assuming this does not need to be specified as f-string
        #  (like in read_header/tbd) -- maybe! must determine and specify
        #  what cases this exception was needed to handle
        self._catch_return_default(self.metaget_(pointer), ex)


def handle_compressed_image(self, pointer: str, userasterio=False):
    # optional hook for rasterio usage for regression tests, etc.
    if userasterio:
        import rasterio

        return rasterio.open(self.file_mapping[pointer]).read()
    # otherwise read with pillow
    from PIL import Image
    # deactivate pillow's DecompressionBombError: many planetary images
    # are legitimately very large
    Image.MAX_IMAGE_PIXELS = None
    # noinspection PyTypeChecker
    image = np.ascontiguousarray(
        Image.open(self.file_mapping[pointer])
    ).copy()
    # pillow reads images as [x, y, channel] rather than [channel, x, y]
    if len(image.shape) == 3:
        return np.ascontiguousarray(np.rollaxis(image, 2))
    return image


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


def handle_fits_header(hdulist, pointer="", ):
    astro_hdr = hdulist[pointer_to_fits_key(pointer, hdulist)].header
    output_hdr = MultiDict()
    for key, val, com in astro_hdr.cards:
        if len(key) > 0:
            if isinstance(val, (str, float, int)):
                output_hdr.add(key, val)
            else:
                output_hdr.add(key, str(val))
            if len(com) > 0:
                comment_key = key + '_comment'
                output_hdr.add(comment_key, com)
    return output_hdr