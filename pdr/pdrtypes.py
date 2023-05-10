from typing import Any, Callable, TYPE_CHECKING, Union

from pdr.pdr import Data, Metadata

if TYPE_CHECKING:
    from multidict import MultiDict
    import numpy as np
    import pandas as pd


PDRLike = Union[Data, Metadata]
LoaderFunction = Callable[
    [Any, ...], Union[str, "MultiDict", "pd.DataFrame", "np.ndarray"]
]
