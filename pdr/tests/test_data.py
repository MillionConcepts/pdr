import numpy as np

import pdr
from pdr.tests.objects import STUB_IMAGE_LABEL


def test_data_init_basic(uniband_image_product):
    prod_name, fpath, lpath = uniband_image_product
    expected_label = STUB_IMAGE_LABEL.format(product_name=prod_name, bands=1)

    data = pdr.read(fpath)
    # ??? Should pdr.read canonicalize line endings?
    # And why are we getting bare \r at the end of a LABEL that mostly
    # has DOS line endings?
    assert data.LABEL.splitlines() == expected_label.splitlines()
    assert data._target_path('IMAGE') == str(fpath)
    for k, v in data.identifiers.items():
        if k == 'SPACECRAFT_NAME':
            assert v == 'ORBITER'
        else:
            assert v == ''
    assert data.keys() == ["LABEL", "IMAGE"]
    assert data.metaget("^IMAGE") == prod_name + ".QQQ"
    assert data.get_absolute_paths('x')[0] == (fpath.parent / 'x').absolute()
    data2 = pdr.read(lpath)
    assert data.LABEL == data2.LABEL
