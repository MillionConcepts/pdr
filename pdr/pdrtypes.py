from typing import Any, Callable, Literal, Union

from pdr.pdr import Data, Metadata

ByteOrder = Literal["<", ">"]
PDRLike = Union[Data, Metadata]
LoaderFunction = Callable[
    ..., Union[str, "MultiDict", "pd.DataFrame", "np.ndarray"]
]
