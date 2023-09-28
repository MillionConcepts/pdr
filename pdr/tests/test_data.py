from pathlib import Path

import numpy as np

import pdr
from pdr.tests.objects import STUB_LABEL

RNG = np.random.default_rng()


def make_stub_product_1():
    randarray = np.zeros((100, 100))
    fpath = (Path(__file__).parent / 'IMAGE.IMG')
    lpath = (Path(__file__).parent / 'IMAGE.LBL')
    with fpath.open("wb") as stream:
        stream.write(randarray.tobytes())
    with lpath.open("w") as stream:
        stream.write(STUB_LABEL)
    return fpath, lpath


def test_data_init_basic():
    fpath, lpath = make_stub_product_1()
    try:
        data = pdr.read(fpath)
        assert data.LABEL == STUB_LABEL
        assert data._target_path('IMAGE') == str(fpath)
    finally:
        fpath.unlink()
        lpath.unlink()
    for k, v in data.identifiers.items():
        if k == 'SPACECRAFT_NAME':
            assert v == 'ORBITER'
        else:
            assert v == ''
    assert data.keys() == ["LABEL", "IMAGE"]
    assert data.metaget("^IMAGE") == "IMAGE.IMG"
    assert data.get_absolute_paths('x')[0] == (fpath.parent / 'x').absolute()


test_data_init_basic()
