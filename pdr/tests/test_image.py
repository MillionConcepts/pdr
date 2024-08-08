import pdr


def test_image_simple_2d(uniband_image_product, tracker_factory):
    prod_name, fpath, lpath = uniband_image_product
    data = pdr.read(fpath, debug=True, tracker=tracker_factory(fpath))
    assert data.IMAGE.sum() == 0


def test_image_simple_3d(multiband_image_product, tracker_factory):
    prod_name, fpath, lpath = multiband_image_product
    data = pdr.read(fpath, debug=True, tracker=tracker_factory(fpath))
    assert data.IMAGE.sum() == 0
