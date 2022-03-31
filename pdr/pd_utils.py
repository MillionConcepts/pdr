"""utilities for working with pandas dataframes."""
from typing import Hashable

import pandas.api.types
import pandas as pd


def numeric_columns(df: pd.DataFrame) -> list[Hashable]:
    return [
        col
        for col, dtype in df.dtypes.iteritems()
        if pandas.api.types.is_numeric_dtype(dtype)
    ]
