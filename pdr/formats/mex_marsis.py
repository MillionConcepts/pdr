
def get_sample_type(sample_type, sample_bytes, for_numpy=False):
    if sample_type == "CHARACTER":
        char = "V" if for_numpy is True else "s"
        return True, f"{char}{sample_bytes}"
    return False, None


def get_position(start, length, as_rows, data):
    n_records = data.metaget_("FILE_RECORDS")
    record_bytes = 143
    length = n_records * record_bytes
    return True, start, length, as_rows
