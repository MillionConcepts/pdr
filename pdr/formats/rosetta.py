from typing import TYPE_CHECKING, Callable

import pdr.loaders.queries

if TYPE_CHECKING:
    from pdr import Data


def rosetta_table_loader(data: "Data", pointer: str) -> Callable:

    def load_this_table(*_, **__):
        import astropy.io.ascii
        table = astropy.io.ascii.read(data.file_mapping[pointer]).to_pandas()
        table.columns = pdr.loaders.queries.read_table_structure(pointer)['NAME'].to_list()
        return table

    return load_this_table
