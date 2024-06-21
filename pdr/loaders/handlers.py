"""
Pointy-end functions used by Loaders that primarily work by calling external
libraries that provide high-level support for specific file formats, including
`pillow` and `astropy.io.fits`.
"""

from __future__ import annotations

from numbers import Number
from typing import Any, Optional, TYPE_CHECKING, Union
import warnings

from cytoolz import groupby
import Levenshtein as lev
from multidict import MultiDict

if TYPE_CHECKING:
    from pathlib import Path
    from astropy.io.fits.hdu import BinTableHDU, HDUList
    import numpy as np
    from pdr.pdrtypes import DataIdentifiers


def hdu_index(obj: Union[str, Path, HDUList]) -> dict:
    """
    produce a dict describing the locations of HDUs and their headers within
    a FITS file.
    """
    from astropy.io import fits

    info = {}
    hdul = obj if isinstance(obj, fits.HDUList) else fits.open(obj)
    hdulinfo = hdul.info(False)
    for hdu_ix, hdu in enumerate(hdul):
        hinfo = hdu.fileinfo()
        baserec = {'ix': hdu_ix, 'name': hdulinfo[hdu_ix][3]}
        info[hinfo['hdrLoc']] = baserec | {'part': 'header'}
        info[hinfo['datLoc']] = baserec | {'part': 'data'}
    return info


def handle_fits_file(
    fn: str,
    name: str = "",
    hdu_id: Union[str, int, tuple[int, int]] = "",
    hdulist: Optional[HDUList] = None,
    id_as_offset: Optional[bool] = False,
):
    """
    Read a data object from an HDU of a FITS file using `astropy.io.fits`. If
    `name` (the PDS3 data object name / `pdr.Data` key) contains the string
    'HEADER' but is not the actual name (EXTNAME / HDUNAME) of an HDU in the
    file, return the HDU's header; otherwise return the HDU's data.

    We distinguish `name` and `hdu_id` as a slightly hacky way to facilitate
    cases in which we explicitly map a PDS pointer to a FITS HDU name or index
    (because PDS data object names _very often_ do not match FITS HDU names).
    """

    # TODO, maybe: dispatch to decompress() for weirdo compression
    #  formats, but possibly not right here? hopefully we shouldn't need
    #  to handle compressed FITS files too often anyway, and astropy can deal
    #  with gzip without special help (although inline igzip is faster)

    from astropy.io import fits

    if hdulist is None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", module="astropy.io.fits.card")
            hdulist = fits.open(fn)
    if id_as_offset is True:
        objrec = hdu_index(hdulist)[hdu_id]
        hdu_id, is_header = objrec['ix'], objrec['part'] == 'header'
    else:
        is_header = (
            "HEADER" in name
            # cases where HDUs are named things like "IMAGE HEADER"
            and hdu_id not in [h[1] for h in hdulist.info(False)]
        )
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
        except (fits.VerifyError, ValueError):  # real messed up
            hdr_val = handle_fits_header(hdulist, hdu_id, skip_bad_cards=True)
    if is_header is False:
        output = {f"{name}_HEADER": hdr_val}
    else:
        output = {name: hdr_val}
    if is_header is True:
        return output
    hdu = hdulist[pointer_to_fits_key(hdu_id, hdulist)]
    # binary table HDUs with repeated column names break astropy -- it will not
    # actually afford the data unless we manipulate it first.
    if isinstance(hdu, fits.BinTableHDU):
        reindex_dupe_names(hdu)
    body = hdu.data
    if body is None:
        # This case is typically a 'stub' PRIMARY HDU. For type consistency,
        # we prefer to return an empty array rather than None.
        import numpy as np

        body = np.array([])
    elif isinstance(body, fits.fitsrec.FITS_rec):
        # This case is a FITS table, binary or ASCII. For type consistency, we
        # want to return a pandas DataFrame, not a FITS_rec.
        import pandas as pd
        from pdr.pd_utils import structured_array_to_df
        try:
            body = pd.DataFrame.from_records(body)
        except ValueError:
            import numpy as np

            # These are generally nested arrays. We don't do this by default,
            # because it requires us to 'reassemble' the array twice, and
            # because pd.DataFrame.from_records() fails very quickly on nested
            # dtypes, it's much more efficient to just try it first.
            body = structured_array_to_df(
                np.rec.fromarrays(
                    [body[k] for k in body.dtype.names], dtype=body.dtype
                )
            )
    return output | {name: body}


def reindex_dupe_names(hdu: BinTableHDU):
    """
    Astropy cannot construct the .data attribute of a BinTableHDU if the table
    has duplicate column names. This changes any duplicate column names in
    place following the same convention we use for PDS binary tables (appending
    incrementing integers).
    """
    names = [c.name for c in hdu.columns]
    repeats = {n for n in names if names.count(n) > 1}
    for r in repeats:
        indices = [ix for ix, n in enumerate(names) if n == r]
        for i, ix in enumerate(indices):
            hdu.columns[ix].name += f"_{i}"


def handle_compressed_image(fn: Union[str, Path]) -> np.ndarray:
    """
    Open an image in a standard 'desktop' format (GIF, standard TIFF, GeoTIFF,
    classic JPEG, JPEG2000, PNG, etc.) using pillow. "Compressed" is slightly
    misleading, because this will work fine on uncompressed GeoTIFF etc.
    """
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


def handle_fits_header(
    hdulist: HDUList,
    hdu_id: Union[str, int] = "",
    skip_bad_cards: bool = False
) -> MultiDict:
    """
    Load the header of a specified HDU as a MultiDict, engaging in various
    sorts of gymnastics to stymie the attempts of astropy.io.fits to keep us
    safe from illegally-formatted headers.
    """
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


def pointer_to_fits_key(pointer: Union[str, Number], hdulist: HDUList) -> int:
    """
    Attempt to map a PDS data object name to an HDU of a FITS file.

    If we're pretty sure about it already based on position information in the
    label, `pointer` will be a number of some kind, and we just open it. If we
    haven't, but the PDS3 object name exactly matches an HDU name (meaning
    value of EXTNAME/HDUNAME), open that one. If it doesn't, and it's named
    IMAGE/TABLE, this usually means "it's the PRIMARY HDU", so open that. If
    neither of those are true -- which is quite common -- use Levenshtein
    "fuzzy matching" to match the PDS3 object name to an HDU name. This is not
    guaranteed to be correct!

    Products for which none of these methods work consistently (e.g. PEPSSI
    RDRs) require special cases.
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


# TODO: shouldn't be in this module
def add_bit_column_info(
    obj: dict,
    definition: MultiDict,
    identifiers: DataIdentifiers
) -> dict:
    """
    Parse the bit column description (if any) from a `dict` created from a
    COLUMN PVL object and add that parsed description to `obj` (most likely
    that definition plus block info). Used in `queries.read_format_block()`.
    """
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
    filename: Union[str, Path], hdulist: Optional[HDUList] = None
) -> tuple[MultiDict, list[str], dict[str, int]]:
    """
    Unpack all headers in a FITS file into a MultiDict and flattened list of
    keys suitable for constructing a `pdr.Metadata` object, along with a
    mapping between HDU names and indices. Used when opening a FITS file in
    "primary" mode (i.e., directly from its own headers, without a supporting
    PDS3 or PDS4 label).
    """
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
