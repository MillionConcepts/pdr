import numpy as np

import pdr
from pdr.tests.objects import STUB_IMAGE_LABEL
from pdr.tests.utils import make_simple_image_product

RNG = np.random.default_rng()


def test_data_init_basic():
    fpath, lpath = make_simple_image_product()
    data = pdr.read(fpath)
    assert data.LABEL == STUB_IMAGE_LABEL
    assert data._target_path('IMAGE') == str(fpath)
    for k, v in data.identifiers.items():
        if k == 'SPACECRAFT_NAME':
            assert v == 'ORBITER'
        else:
            assert v == ''
    assert data.keys() == ["LABEL", "IMAGE"]
    assert data.metaget("^IMAGE") == "PRODUCT.QQQ"
    assert data.get_absolute_paths('x')[0] == (fpath.parent / 'x').absolute()
    data2 = pdr.read(lpath)
    assert data.LABEL == data2.LABEL
