import numpy as np

import pdr
from pdr.tests.utils import (
    make_simple_binary_table_product,
    make_simple_dsv_table_product,
)


def test_simple_binary_table():
    fpath, lpath = make_simple_binary_table_product()
    data = pdr.read(fpath, debug=True)
    assert list(data.TABLE.columns) == ['X_0', 'Y', 'X_1']
    assert list(data.TABLE.dtypes) == [
        np.dtype('uint8'), np.dtype('float32'), np.dtype('float64')
    ]
    assert data.TABLE.loc[0, 'X_0'] == 1
    assert np.isclose(data.TABLE.loc[5, 'Y'], 4.4)
    assert np.isclose(data.TABLE.loc[9, "X_1"], 8.8)


def test_simple_dsv_table():
    fpath, lpath = make_simple_dsv_table_product()
    data = pdr.read(fpath, debug=True)
    assert list(data.SPREADSHEET.columns) == ['X_0', 'Y', 'X_1']
    assert list(data.SPREADSHEET.dtypes) == [
        np.dtype('float64'), np.dtype('O'), np.dtype('int64')
    ]
    assert np.isclose(data.SPREADSHEET.loc[0, 'X_0'], 5.5)
    assert data.SPREADSHEET.loc[5, 'Y'] == 'cat'
    assert data.SPREADSHEET.loc[9, "X_1"] == -12
