import warnings

from pdr.pd_utils import insert_sample_types_into_df


def ppi_table_loader(data, pointer, data_set_id):

    def load_this_table(*_, **__):
        import pandas as pd

        if "UNCALIB" in data_set_id:
            return pd.read_csv(data.file_mapping[pointer])
        structure = data.read_table_structure(pointer)
        names = structure.NAME
        header = None
        if "FULL" in data.file_mapping[pointer]:
            skiprows = 4
            if data_set_id == "CO-S-MIMI-4-CHEMS-CALIB-V1.0":
                header = 0
                names = None
                skiprows = range(1, 4)
        else:
            skiprows = 7
        table = pd.read_csv(data.file_mapping[pointer],
                            header=header,
                            skiprows=skiprows,
                            names=names)
        return table
    return load_this_table


def get_structure(pointer, data):
    # the data type that goes here double defines the 32 byte prefix/offset. By skipping the parse_table_structure
    # we never add the prefix bytes so it works as is.
    fmtdef = data.read_table_structure(pointer)
    fmtdef, dt = insert_sample_types_into_df(fmtdef, data)
    return True, fmtdef, dt


def trivial_loader(pointer, data):
    warnings.warn(
        f"The Cassini ISS EDR/calibration {pointer} tables are not currently "
        f"supported."
    )
    return data.trivial
