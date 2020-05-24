from __future__ import absolute_import
import os.path as _osp

from pdr.pdr import Data
from pdr.utils import download_test_data

__version__ = "0.1.0"

pkg_dir = _osp.abspath(_osp.dirname(__file__))
test_dir = _osp.join(pkg_dir, 'tests')

def read(fp):
    return Data(fp)

def open(fp):
    return read(fp)

def get(index, refdatafile="refdata.csv"):
    """ Retrieve the test data at row = _index_ in the refdata.csv. """
    return download_test_data(index, test_dir=test_dir, refdatafile=f"{test_dir}/refdata.csv")
