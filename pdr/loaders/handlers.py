import warnings
from typing import Optional
import Levenshtein as lev
from cytoolz import groupby
from multidict import MultiDict


def handle_fits_file(
    fn, name="", hdu_id="", hdulist: Optional["HDUList"] = None
):
    """
    This function attempts to read all FITS files, compressed or
    uncompressed, with astropy.io.fits. Files with 'HEADER' pointer
    return the header, all others return data.

    we distinguish name and hdu_name as a slightly hacky way to facilitate
    special cases in which we explicitly map a PDS pointer to a FITS HDU name
    or index.
    """

    #TODO, maybe: dispatch to decompress() for weirdo compression
    # formats, but possibly not right here? hopefully we shouldn't need
    # to handle compressed FITS files too often anyway, and astropy can deal
    # with gzip without special help (although inline igzip is faster)

    from astropy.io import fits

    if hdulist is None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", module="astropy.io.fits.card")
            hdulist = fits.open(fn)
    # this means the id was generated by queries.get_fits_id and includes the
    # number of distinct HDUs mentioned in the PDS label, so we can do a
    # validity check.
    if isinstance(hdu_id, tuple):
        hdu_id, inferred_hdu_count = hdu_id
        if len(hdulist) != inferred_hdu_count:
            warnings.warn(
                "The number of HDUs inferred from the PDS label differs "
                "from the number of HDUs in the FITS file. Indexing may "
                "be off."
            )
    try:
        hdr_val = handle_fits_header(hdulist, hdu_id)
    # astropy.io.fits does not call any verification on read. on 'output'
    # tasks -- which iterating over header cards (sometimes) counts as, and
    # which we have to do in order to place the header content into our
    # preferred data structure -- it does call verification, at the strictest
    # settings. we do not want to prospectively fix every case because it is
    # quite slow. so, when astropy.io.fits decides something is too invalid to
    # show us, tell it to fix it first.
    except fits.VerifyError:
        try:
            hdulist.verify('silentfix')
            hdr_val = handle_fits_header(hdulist, hdu_id)
        except fits.VerifyError:  # real messed up
            hdr_val = handle_fits_header(hdulist, hdu_id, skip_bad_cards=True)
    if (
        "HEADER" not in name
        # cases where HDUs are named things like "IMAGE HEADER"
        or hdu_id in [h[1] for h in hdulist.info(False)]
    ):
        output = {f"{name}_HEADER": hdr_val}
    else:
        return {name: hdr_val}
    hdu = hdulist[pointer_to_fits_key(hdu_id, hdulist)]
    # binary table HDUs with repeated column names break astropy
    if isinstance(hdu, fits.BinTableHDU):
        reindex_dupe_names(hdu)
    body = hdu.data
    if body is None:
        import numpy as np

        body = np.array([])
    # i.e., it's a FITS table, binary or ascii
    if isinstance(body, fits.fitsrec.FITS_rec):
        import pandas as pd
        from pdr.pd_utils import structured_array_to_df
        try:
            body = pd.DataFrame.from_records(body)
        except ValueError:
            import numpy as np

            # nested arrays, generally -- we don't do this by default because
            # it requires us to 'reassemble' the array twice, so is inefficient
            body = structured_array_to_df(np.rec.fromarrays([body[k] for k in
                                          body.dtype.names], dtype=body.dtype))
    return output | {name: body}


def reindex_dupe_names(hdu: "astropy.io.fits.BinTableHDU"):
    """
    rename duplicate column names in a fits binary table -- astropy will not
    be able to construct the .data attribute otherwise
    """
    names = [c.name for c in hdu.columns]
    repeats = {n for n in names if names.count(n) > 1}
    for r in repeats:
        indices = [ix for ix, n in enumerate(names) if n == r]
        for i, ix in enumerate(indices):
            hdu.columns[ix].name += f"_{i}"


def handle_compressed_image(fn):
    """"""
    import numpy as np
    from PIL import Image

    # deactivate pillow's DecompressionBombError: many planetary images
    # are legitimately very large
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(fn)
    if im.mode == 'P':
        # classic-style GIFs
        im = im.convert('RGB', palette=im.palette)
    # noinspection PyTypeChecker
    image = np.ascontiguousarray(im).copy()
    # pillow reads images as [x, y, channel] rather than [channel, x, y]
    if len(image.shape) == 3:
        return np.ascontiguousarray(np.rollaxis(image, 2))
    return image


def handle_fits_header(hdulist, hdu_id="", skip_bad_cards=False):
    """"""
    if isinstance(hdu_id, int):
        astro_hdr = hdulist[hdu_id].header
    else:
        astro_hdr = hdulist[pointer_to_fits_key(hdu_id, hdulist)].header
    output_hdr = MultiDict()
    from astropy.io import fits
    for i in range(len(astro_hdr.cards)):
        try:
            key, val, com = astro_hdr.cards[i]
            if len(key) > 0:
                if isinstance(val, (str, float, int)):
                    output_hdr.add(key, val)
                else:
                    output_hdr.add(key, str(val))
                if len(com) > 0:
                    comment_key = key + "_comment"
                    output_hdr.add(comment_key, com)
        except fits.VerifyError:
            if skip_bad_cards is True:
                continue
            raise
        except StopIteration:
            break
    return output_hdr


def pointer_to_fits_key(pointer, hdulist):
    """
    In some datasets with FITS, the PDS3 object names and FITS object
    names are not identical. This function attempts to use Levenshtein
    "fuzzy matching" to identify the correlation between the two. It is not
    guaranteed to be correct! And special case handling might be required in
    the future.
    """
    if isinstance(pointer, int):  # permit explicit specification of HDU number
        return pointer
    # something astropy does sometimes
    elif pointer.isnumeric():
        return int(pointer)
    hdu_names = [h[1].lower() for h in hdulist.info(False)]
    try:
        return hdu_names.index(pointer.lower())
    except ValueError:
        pass
    if pointer in ("IMAGE", "TABLE", None, ""):
        return 0
    levratio = [lev.ratio(name, pointer.lower()) for name in hdu_names]
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


def unpack_fits_headers(
    filename, hdulist=None
) -> tuple[MultiDict, list[str], dict[str, int]]:
    """"""
    from astropy.io import fits

    hdumap = {}
    headerdict = MultiDict()
    if hdulist is None:
        hdulist = fits.open(filename)
    namegroups = groupby(lambda hi: hi[1], hdulist.info(False))
    for name, group in namegroups.items():
        if len(group) == 1:
            hdu_ix = group[0][0]
            headerdict.add(name, handle_fits_header(hdulist, hdu_ix))
            hdumap[name] = hdu_ix
            continue
        for ix, hdu in enumerate(group):
            hdu_ix, hdu_name = hdu[0], f'{name}_{ix}'
            headerdict.add(
                hdu_name, handle_fits_header(hdulist, hdu_ix)
            )
            hdumap[hdu_name] = hdu_ix
    params = []
    for hdu_name in headerdict.keys():
        # note that FITS headers can't be deeply nested
        params.append(hdu_name)
        for field in headerdict[hdu_name].keys():
            params.append(field)
    return headerdict, params, hdumap
