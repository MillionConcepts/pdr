from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from pdr import Data


def galileo_table_loader(data: "Data") -> Callable:
    def load_this_table(*_, **__):
        import astropy.io.ascii
        table = astropy.io.ascii.read(data.filename).to_pandas()
        table.columns = data.read_table_structure('TABLE')['NAME'].values
        return table
    return load_this_table
