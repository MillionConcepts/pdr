from __future__ import annotations
import os.path as _osp
import sys
from typing import Collection, Optional, TYPE_CHECKING, Union

from pdr.pdr import Data, Metadata

if TYPE_CHECKING:
    from pathlib import Path

__version__ = "1.0.6"

pkg_dir = _osp.abspath(_osp.dirname(__file__))


def read(
    fp: Union[str, Path],
    debug: bool = False,
    label_fn: Optional[Union[Path, str]] = None,
    search_paths: Union[Collection[str], str] = (),
    skip_existence_check: bool = False,
    **kwargs
) -> Data:
    """
    Read a data product with PDR. `fn` can be any file associated with the
    product, preferably a detached label file if it exists. Returns a Data
    object that provides an interface to the data and metadata in all available
    files associated with the product.
    """
    try:
        return Data(
            fp,
            debug=debug,
            label_fn=label_fn,
            search_paths=search_paths,
            skip_existence_check=skip_existence_check,
            **kwargs
        )
    except FileNotFoundError:
        if any(val in str(fp) for val in ["http", "www.", "ftp:"]):
            raise ValueError("Read-from-url is not currently implemented.")
        from pdr.utils import check_cases

        return Data(check_cases(fp), **kwargs)


# pdr.open() is an alias for pdr.read()
setattr(sys.modules[__name__], 'open', read)
