def ppi_table_loader(data, pointer, data_set_id):

    def load_this_table(*_, **__):
        import pandas as pd
        structure = data.read_table_structure(pointer)
        if "FULL" in data.file_mapping[pointer]:
            skiprows = 4
        else:
            skiprows = 7
        table = pd.read_csv(data.file_mapping[pointer], skiprows=skiprows, header=None, names=structure.NAME)
        return table

    return load_this_table
