def ppi_table_loader(data, pointer, data_set_id):

    def load_this_table(*_, **__):
        import pandas as pd
        structure = data.read_table_structure(pointer)
        if data_set_id == "CO-S-MIMI-4-CHEMS-CALIB-V1.0" or "CO-S-MIMI-4-INCA-CALIB-V1.0":
            skiprows = 7
        if data_set_id == "CO-S-MIMI-4-LEMMS-CALIB-V1.0":
            skiprows = 4
        table = pd.read_csv(data.file_mapping[pointer], skiprows=skiprows, header=None, names=structure.NAME)
        return table

    return load_this_table
