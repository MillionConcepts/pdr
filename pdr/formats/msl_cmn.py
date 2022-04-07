from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from pdr import Data


def override_name(loader: Callable, name: str) -> Callable:
    def load_what_i_say(_wrong_object_name):
        return loader(name)
    return load_what_i_say


def table_loader(data, object_name):
    # mangled name
    if object_name == "CHMN_HSK_HEADER_TABLE":
        return override_name(data.read_table, "CHMN_HSKN_HEADER_TABLE")
    if object_name == "HEADER":
        return data.trivial
    if object_name == "SPREADSHEET":
        return chemin_spreadsheet_loader(data)
    return data.read_table


def get_offset(_data, object_name):
    # incorrectly specifies object length rather than start byte
    if object_name == "HISTOGRAM":
        return True, 300
    if object_name == "CHMN_HSKN_HEADER_TABLE":
        return True, 0
    return False, None


def chemin_spreadsheet_loader(data: "Data"):
    def load_this_table(*_, **__):
        import pandas as pd
        return pd.read_csv(
            data.get_absolute_path(data.metaget_("^SPREADSHEET")[0])
        )
    return load_this_table
