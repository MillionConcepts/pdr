"""
Pointy-end functions used by Loaders that primarily work by calling external
libraries that provide high-level support for specific file formats, including
`pillow` and `astropy.io.fits`.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING, Union
import warnings

from cytoolz import groupby
from multidict import MultiDict

if TYPE_CHECKING:
    from pathlib import Path
    from pdr.loaders.astrowrap import BinTableHDU, HDUList
    import numpy as np
    import pandas as pd
    from pdr.pdrtypes import DataIdentifiers


def hdu_byte_index(obj: Union[str, Path, HDUList]) -> dict:
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


# TODO, maybe: dispatch to decompress() for weirdo compression
#  formats, but possibly not right here? hopefully we shouldn't need
#  to handle compressed FITS files too often anyway, and astropy can deal
#  with gzip without special help (although inline igzip is faster)
def handle_fits_file(
    fn: str,
    name: str,
    hdu_id: Union[str, int, tuple[int, int]],
    hdulist: Optional[HDUList] = None,
    hdu_id_is_index: bool = False,
) -> dict[str, Union[MultiDict, pd.DataFrame, np.ndarray]]:
    """
    Create an object or objects from an HDU of a FITS file using
    `astropy.io.fits`.

    `hdu_id` may be the index of an HDU or the start byte of the HDU's header
    or data section; `hdu_id_is_index=True` means that it's the HDU's index.
    If it's a start byte, and it's the start byte of the HDU's header section,
    return just the header; otherwise return the data and the header. If it's
    an index, always return the data and the header (currently this is only
    used for primary FITS files, which by construction never have headers
    labeled as independent objects).
    """
    from astropy.io import fits

    if hdulist is None:
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", module="astropy.io.fits.card")
            hdulist = fits.open(fn)
    if hdu_id_is_index is False:
        objrec = hdu_byte_index(hdulist)[hdu_id]
        hdu_ix, is_header = objrec['ix'], objrec['part'] == 'header'
    else:
        # this is the case when dealing with a FITS file in 'primary' mode.
        # This is a little sloppy, but it is more convenient to handle certain
        # things upstream. may want to collapse the two cases at some point.
        hdu_ix = hdu_id
        is_header = (
            "HEADER" in name
            # cases where HDUs are named things like "IMAGE HEADER"
            and name not in [h[1] for h in hdulist.info(False)]
        )
    try:
        hdr_val = handle_fits_header(hdulist, hdu_ix)
    # astropy.io.fits does not call any verification on read. on 'output'
    # tasks -- which iterating over header cards (sometimes) counts as, and
    # which we have to do in order to place the header content into our
    # preferred data structure -- it does call verification at the strictest
    # settings, resulting in delayed exceptions. However, we do not want to
    # automatically run every fix, because astropy's fixes can be quite slow
    # on large, complicated headers. So, if and when astropy decides something
    # is too invalid to show us, tell it to fix it.
    except fits.VerifyError:
        try:
            hdulist.verify('silentfix')
            hdr_val = handle_fits_header(hdulist, hdu_ix)
        except (fits.VerifyError, ValueError):  # real messed up
            hdr_val = handle_fits_header(hdulist, hdu_ix, skip_bad_cards=True)
    if is_header is True:
        return {name: hdr_val}
    output, hdu = {f"{name}_HEADER": hdr_val}, hdulist[hdu_ix]
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
        import numpy as np
        import pandas as pd
        from pdr.loaders.astrowrap import BinTableHDU
        from pdr.pd_utils import structured_array_to_df

        if max(map(len, body.dtype.descr)) > 2:
            body = structured_array_to_df(
                np.rec.fromarrays(
                    [body[k] for k in body.dtype.names], dtype=body.dtype
                )
            )
        elif isinstance(hdu, BinTableHDU):
            fields = {c: body[c] for c in body.dtype.names}
            for k, v in fields.items():
                if not v.dtype.isnative:
                    fields[k] = fields[k].byteswap().view(
                        fields[k].dtype.newbyteorder('=')
                    )
            body = pd.DataFrame(fields)
        else:
            body = pd.DataFrame.from_records(body)
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


def handle_compressed_image(
    fn: Union[str, Path], frame: Optional[int] = None
) -> np.ndarray:
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
    if frame is not None:
        im.seek(frame)
    if im.mode == 'P':
        # images with imbedded palettes (usually GIFs)
        im = im.convert('RGB', palette=im.palette)
    # noinspection PyTypeChecker
    image = np.ascontiguousarray(im).copy()
    # pillow reads images as [x, y, channel] rather than [channel, x, y]
    if len(image.shape) == 3:
        return np.ascontiguousarray(np.rollaxis(image, 2))
    return image


def _check_prescaled_desktop(fn: Union[str, Path]):
    """
    Check whether a desktop-format image -- i.e., one we loaded with pillow --
    might need scaling / masking / etc. Currently we treat this as true for
    JP2 and GeoTIFF and False otherwise. There might be other heuristics.
    """
    from pdr.pil_utils import skim_image_data

    meta = skim_image_data(fn)
    if any('GeoKey' in k for k in meta.keys()):
        return False
    if meta['format'] == 'JPEG2000':
        return False
    return True


def handle_fits_header(
    hdulist: HDUList,
    hdu_ix: int,
    skip_bad_cards: bool = False
) -> MultiDict:
    """
    Load the header of a specified HDU as a MultiDict, engaging in various
    sorts of gymnastics to stymie the attempts of astropy.io.fits to keep us
    safe from illegally-formatted headers.
    """
    astro_hdr, output_hdr = hdulist[hdu_ix].header, MultiDict()

    from astropy.io import fits
    for i in range(len(astro_hdr.cards)):
        try:
            key, val, com = astro_hdr.cards[i]
            if len(key) == 0:
                # placeholder card records
                continue
            if isinstance(val, (str, float, int)):
                output_hdr.add(key, val)
            # We do not want to represent keyword-only cards with weird
            # special astropy objects.
            elif val.__class__.__name__ == 'Undefined':
                output_hdr.add(key, None)
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

    from pdr.formats import check_special_bit_format
    is_special, special_obj = check_special_bit_format(
        obj, definition, identifiers
    )
    if is_special:
        obj = special_obj
    
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
            headerdict.add(hdu_name, handle_fits_header(hdulist, hdu_ix))
            hdumap[hdu_name] = hdu_ix
    params = []
    for hdu_name in headerdict.keys():
        # note that FITS headers aren't nested, so we only have to iterate
        # over one level. How refreshing!
        params.append(hdu_name)
        for field in headerdict[hdu_name].keys():
            params.append(field)
    return headerdict, params, hdumap
