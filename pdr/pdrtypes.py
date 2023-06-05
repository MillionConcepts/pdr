from typing import Any, Callable, Union

from pdr.pdr import Data, Metadata

PDRLike = Union[Data, Metadata]
LoaderFunction = Callable[
    [Any, ...], Union[str, "MultiDict", "pd.DataFrame", "np.ndarray"]
]
