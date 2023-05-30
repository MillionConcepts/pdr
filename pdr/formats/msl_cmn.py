from typing import TYPE_CHECKING

from pdr.loaders.utility import trivial

if TYPE_CHECKING:
    from pdr import Data


def table_loader(data, object_name):
    if object_name == "HEADER":
        return True, trivial
    if object_name == "SPREADSHEET":
        import pandas as pd

        return True, pd.read_csv(
            data.get_absolute_paths(data.metaget_("^SPREADSHEET")[0])[0]
        )
    return False, None


def fix_mangled_name(data):
    object_name = "CHMN_HSKN_HEADER_TABLE"
    block = data.metablock_(object_name)
    return block


def get_offset(object_name):
    # incorrectly specifies object length rather than start byte
    if object_name == "HISTOGRAM":
        return True, 300
    if object_name == "CHMN_HSK_HEADER_TABLE":
        return True, 0
    return False, None


def chemin_spreadsheet_loader(data: "Data"):
    def load_this_table(*_, **__):
        import pandas as pd

        return pd.read_csv(
            data.get_absolute_paths(data.metaget_("^SPREADSHEET")[0])[0]
        )

    return load_this_table
