from typing import Callable, Literal, Union

from pdr.pdr import Data, Metadata

ByteOrder = Literal["<", ">"]
"""Most significant/least significant byteorder codes"""

PDRLike = Union[Data, Metadata]
"""Something with a pdr-style metadata-getting interface"""

LoaderFunction = Callable[
    ..., Union[str, "MultiDict", "pd.DataFrame", "np.ndarray"]
]
"""Signature of a Loader's load function"""

PhysicalTarget = Union[
    list[str, int], tuple[str, int], int, str, dict[str, Union[str, int]]
]
"""Expected formats of 'pointer' parameters, i.e. ^WHATEVER = PhysicalTarget"""

BandStorageType = Literal[
    "BAND_SEQUENTIAL", "LINE_INTERLEAVED", "SAMPLE_INTERLEAVED", None
]
"""
Codes for physical storage layout of 3-D arrays. Also known as BSQ/band 
sequential, BIL/band interleaved by line, BIP/band interleaved by pixel. 
None implies either that the storage layout is unknown or that the array is
not 3-D.
"""
