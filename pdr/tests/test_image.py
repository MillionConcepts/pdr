import pdr
from pdr.tests.utils import make_simple_image_product, make_simple_image_product_mb


def test_image_simple_2d():
    fpath, lpath = make_simple_image_product()
    data = pdr.read(fpath, debug=True)
    assert data.IMAGE.sum() == 0


def test_image_simple_3d():
    fpath, lpath = make_simple_image_product_mb()
    data = pdr.read(fpath, debug=True)
    assert data.IMAGE.sum() == 0
