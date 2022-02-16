from typing import Callable


def override_name(loader: Callable, name: str) -> Callable:
    def load_what_i_say(_wrong_object_name):
        return loader(name)
    return load_what_i_say


def table_loader(data, object_name):
    # mangled name
    if object_name == "CHMN_HSK_HEADER_TABLE":
        return override_name(data.read_table, "CHMN_HSKN_HEADER_TABLE")
    return data.read_table


def get_offset(_data, object_name):
    # incorrectly specifies object length rather than start byte
    if object_name == "HISTOGRAM":
        return True, 300
    if object_name == "CHMN_HSKN_HEADER_TABLE":
        return True, 0
    return False, None
