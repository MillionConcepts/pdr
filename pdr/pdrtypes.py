from __future__ import annotations

from typing import (
    Callable, Literal, Optional, TypedDict, TYPE_CHECKING, Union
)
# TypeAlias is new in 3.10
# this is exactly how it's defined in python3.11/typing.py
try:
    from typing import TypeAlias
except ImportError:
    def TypeAlias(self, parameters):
        raise TypeError(f"{self} is not subscriptable")


if TYPE_CHECKING:
    from multidict import MultiDict
    import numpy as np
    import pandas as pd
    from pdr import Data, Metadata

ByteOrder: TypeAlias = Literal["<", ">"]
"""Most significant/least significant byteorder codes"""

PDRLike: TypeAlias = Union["Data", "Metadata"]
"""Something with a pdr-style metadata-getting interface"""

LoaderFunction: TypeAlias = Callable[
    ..., Union[str, "MultiDict", "pd.DataFrame", "np.ndarray"]
]
"""Signature of a Loader's load function"""

PhysicalTarget: TypeAlias = Union[
    list[str, int], tuple[str, int], int, str, dict[str, Union[str, int]]
]
"""Expected formats of 'pointer' parameters, i.e. ^WHATEVER = PhysicalTarget"""

BandStorageType: TypeAlias = Literal[
    "BAND_SEQUENTIAL", "LINE_INTERLEAVED", "SAMPLE_INTERLEAVED", None
]
"""
Codes for physical storage layout of 3-D arrays. Also known as BSQ/band 
sequential, BIL/band interleaved by line, BIP/band interleaved by pixel. 
None implies either that the storage layout is unknown or that the array is
not 3-D.
"""

Axname: TypeAlias = Literal["BAND", "LINE", "SAMPLE"]
"""Conventional names for image axes."""


class ImageProps(TypedDict):
    """Standard image properties dict used in image-processing workflows."""
    # Number of bytes per pixel (eventually redundant with sample_type but
    # populated much earlier)
    BYTES_PER_PIXEL: Literal[1, 2, 4, 8]
    # Do the elements of the array, when loaded, represent VAX reals?
    is_vax_real: bool
    # numpy dtype string
    sample_type: str
    # total number of elements
    pixels: int
    # number of elements along each dimension
    nrows: int
    ncols: int
    nbands: int
    # physical storage layout of 3D arrays (None for 2D arrays)
    band_storage_type: BandStorageType
    # total row/column/band pad elements due to ISIS-style axplanes
    rowpad: int
    colpad: int
    bandpad: int
    # number of pad elements for left/right sideplanes
    prefix_rows: Optional[int]
    suffix_rows: Optional[int]
    # number of pad elements for bottom/topplanes
    prefix_cols: Optional[int]
    suffix_cols: Optional[int]
    # number of pad elements for front/backplanes
    prefix_bands: Optional[int]
    suffix_bands: Optional[int]
    # total pad elements due to line prefixes/suffixes
    linepad: int
    # number of elements in line prefix and suffix
    line_prefix_pix: Optional[int]
    line_suffix_pix: Optional[int]
    # Order of axes expressed as a tuple of axis names, only used by ISIS qubes
    axnames: Optional[tuple[Axname]]


class DataIdentifiers(TypedDict):
    """
    Standard PDS3 'identifiers' Data checks its Metadata for on initialization
    (if it's made from a PDS3 product). Used primarily to make special case
    checks more compact. These are taken directly from the label, then
    stringified if they're sets or tuples. All keys are always present, but
    may be None if a parameter's not actually in the label.
    """
    DATA_SET_ID: Union[str, None]
    DATA_SET_NAME: Union[str, None]
    FILE_NAME: Union[str, None]
    FILE_RECORDS: Union[int, None]
    INSTRUMENT_ID: Union[str, None]
    INSTRUMENT_HOST_NAME: Union[str, None]
    INSTRUMENT_NAME: Union[str, None]
    LABEL_RECORDS: Union[int, None]
    NOTE: Union[str, None]
    PRODUCT_ID: Union[str, None]
    PRODUCT_TYPE: Union[str, None]
    RECORD_BYTES: Union[int, None]
    RECORD_TYPE: Union[str, None]
    ROW_BYTES: Union[int, None]
    ROWS: Union[int, None]
    SPACECRAFT_NAME: Union[str, None]
    STANDARD_DATA_PRODUCT_ID: Union[str, None]
