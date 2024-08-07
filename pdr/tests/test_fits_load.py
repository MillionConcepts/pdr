from pathlib import Path

import numpy as np

import pdr

import pytest
try:
    from astropy.io import fits
    fits_available = True
except ImportError:
    fits_available = False

RNG = np.random.default_rng()

@pytest.mark.skipif(not fits_available, reason="astropy.io.fits not available")
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
