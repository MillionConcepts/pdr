from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pdr import Data


def shadr_header_table_loader(data: "Data"):
    def load_header_table(pointer):
        table = data.read_table(pointer)
        return table.loc[:0]
    return load_header_table
