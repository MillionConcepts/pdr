from pathlib import Path

from astropy.io import fits
import numpy as np

import pdr

RNG = np.random.default_rng()


def test_array_roundtrip():
    arr = RNG.poisson(100, (100, 100)).astype(np.uint8)
    hdul = fits.HDUList()
    hdul.append(fits.ImageHDU(arr, name='POISSON'))
    try:
        hdul.writeto('temp.fits')
        data = pdr.read('temp.fits')
        assert data.keys() == ['POISSON']
        assert np.all(data.POISSON == arr)
    finally:
        Path('temp.fits').unlink(missing_ok=True)

