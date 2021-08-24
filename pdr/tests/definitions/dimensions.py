"""
functions returning canonical dimensions for products we want to perform
dimensionality checks on. names of functions in this module must be the same,
case-insensitive, as names of test sets in test_set_definitions, with spaces
or other illegal characters replaced by underscores.
"""
from pathlib import Path
import re


def mslmrd(data):
    fn = Path(data.filename).name
    caltype_code = re.search(r"_DR\w(\w).", fn).group(1)
    dims = {"L": (3, 1533, 2108), "X": (3, 1200, 1648)}[caltype_code]
    if data.IMAGE.shape != dims:
        raise ValueError(
            f"dimension mismatch between loaded array "
            f"({data.IMAGE.shape}) and canonical value ({dims})"
        )
