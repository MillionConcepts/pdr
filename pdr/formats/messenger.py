from pdr.loaders.table import read_table


def shadr_header_table_loader():
    def load_header_table(pointer):
        table = read_table(pointer)
        return table.loc[:0]
    return load_header_table
