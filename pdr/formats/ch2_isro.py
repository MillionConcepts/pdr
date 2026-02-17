from __future__ import annotations

def read_class_fits_table(filename, object):
    """
    The main pds4 fits tools attempt to use the wrong index to open the
    fits data.

    HITS:
    * ch2_isro
        * cla_l1
    """
    from astropy.io import fits

    if filename.endswith(".xml"):
        filename = filename.split('.')[0]+".fits"
    hdu = fits.open(filename)
    if object == 'data':
        # returns a recarray
        return hdu[1].data
    if object == 'header_Data':
        return hdu[1].header

    # shouldn't happen
    return None
