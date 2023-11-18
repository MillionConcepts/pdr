def spreadsheet_loader(filename):
    """"""
    import pandas as pd
    return pd.read_csv(filename)


def trivial_header_loader():
    """"""
    return True


def fix_mangled_name(data):
    """"""
    object_name = "CHMN_HSKN_HEADER_TABLE"
    block = data.metablock_(object_name)
    return block


def get_offset(object_name):
    """incorrectly specifies object length rather than start byte"""
    if object_name == "HISTOGRAM":
        return True, 300
    if object_name == "CHMN_HSK_HEADER_TABLE":
        return True, 0
    return False, None
