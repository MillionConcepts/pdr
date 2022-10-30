import os.path as _osp

from pdr.pdr import Data, Metadata
from pdr.utils import check_cases

__version__ = "0.7.2"

pkg_dir = _osp.abspath(_osp.dirname(__file__))


def read(fp, **kwargs):
    try:
        return Data(fp, **kwargs)
    except FileNotFoundError:
        if any(val in str(fp) for val in ['http', 'www.', 'ftp:']):
            raise ValueError(
                "Support for read from url is not currently implemented."
            )
        return Data(check_cases(fp), **kwargs)


def open(fp, **kwargs):
    return read(fp, **kwargs)
