from typing import TYPE_CHECKING, Callable
import warnings

if TYPE_CHECKING:
    from pdr import Data


def galileo_table_loader(data: "Data") -> Callable:
    if "-EDR-" in data.metaget_("DATA_SET_ID", ""):
        warnings.warn("Galileo EDR binary tables are not yet supported.")
        return data.trivial

    def load_this_table(*_, **__):
        import astropy.io.ascii
        table = astropy.io.ascii.read(data.file_mapping['TABLE']).to_pandas()
        table.columns = data.read_table_structure('TABLE')['NAME'].values
        return table

    return load_this_table
