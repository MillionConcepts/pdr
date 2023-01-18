CASSINI_SET_NAMES = (
    "CO-S-MIMI-4-CHEMS-CALIB-V1.0",
    "CO-S-MIMI-4-LEMMS-CALIB-V1.0",
    "CO-S-MIMI-4-INCA-CALIB-V1.0",
    "CO-E/J/S/SW-MIMI-2-LEMMS-UNCALIB-V1.0"
)


def ppi_table_loader(data, pointer, data_set_id):

    def load_this_table(*_, **__):
        import pandas as pd

        if "UNCALIB" in data_set_id:
            return pd.read_csv(data.file_mapping[pointer])
        structure = data.read_table_structure(pointer)
        if "FULL" in data.file_mapping[pointer]:
            skiprows = 4
        else:
            skiprows = 7
        table = pd.read_csv(
            data.file_mapping[pointer],
            skiprows=skiprows,
            header=None,
            names=structure.NAME
        )
        return table
    return load_this_table
