import os.path as _osp

from pdr.pdr import Data, Metadata
from pdr.utils import check_cases

__version__ = "0.6.1"

pkg_dir = _osp.abspath(_osp.dirname(__file__))
test_dir = _osp.join(pkg_dir, 'oldtests')


def read(fp, **kwargs):
    try:
        return Data(fp, **kwargs)
    except FileNotFoundError:
        return Data(check_cases(fp), **kwargs)


def open(fp, **kwargs):
    return read(fp, **kwargs)


def get(url):
    from pdr.downloaders import download_test_data, download_data_and_label
    # Grab test data and the corresponding label (if applicable) into the test_dir
    return download_data_and_label(url, data_dir=test_dir)


def get_from_index(index, refdatafile="refdata.csv"):
    """ Retrieve the test data at row = _index_ in the refdata.csv. """
    from pdr.downloaders import download_test_data
    return download_test_data(
        index, data_dir=test_dir, refdatafile=f"{test_dir}/refdata.csv"
    )
