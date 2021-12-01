import os.path as _osp

from pdr.pdr import Data
from pdr.utils import download_test_data, download_data_and_label

__version__ = "0.5.0"

pkg_dir = _osp.abspath(_osp.dirname(__file__))
test_dir = _osp.join(pkg_dir, 'oldtests')


def read(fp):
    return Data(fp)


def open(fp):
    return read(fp)


def get(url):
    # Grab test data and the corresponding label (if applicable) into the test_dir
    return download_data_and_label(url, data_dir=test_dir)


def get_from_index(index, refdatafile="refdata.csv"):
    """ Retrieve the test data at row = _index_ in the refdata.csv. """
    return download_test_data(index, data_dir=test_dir, refdatafile=f"{test_dir}/refdata.csv")
