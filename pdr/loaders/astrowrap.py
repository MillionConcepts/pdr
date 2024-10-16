try:
    from astropy.io import fits
    from astropy.io.fits import HDUList
    from astropy.io.fits.hdu import BinTableHDU
except ImportError:
    raise ModuleNotFoundError(
        "Reading FITS files requires the optional astropy dependency."
    )
