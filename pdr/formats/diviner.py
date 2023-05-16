from typing import Callable, TYPE_CHECKING

import numpy as np
import pandas as pd

import pdr.loaders.queries

if TYPE_CHECKING:
    from pdr import Data


# because these can contain the value "NaN", combined with the fact that they
# are space-padded, pd.read_csv sometimes casts some columns to object,
# turning some of their values into strings and some into float, throwing
# warnings and making it obnoxious to work with them (users will randomly not
# be able to, e.g., add two columns together without a data cleaning step).
def diviner_l4_table_loader(data: "Data", pointer: str) -> Callable:

    def read_diviner_l4_table(*_, **__):
        fmtdef, _ = pdr.loaders.queries.parse_table_structure(pointer)
        return pd.DataFrame(
            np.loadtxt(data.file_mapping['TABLE'], delimiter=",", skiprows=1),
            columns=fmtdef['NAME'].tolist()
        )
    return read_diviner_l4_table
