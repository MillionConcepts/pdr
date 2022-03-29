
def get_sample_type(sample_type, sample_bytes, for_numpy=False):
    if sample_type == "CHARACTER":
        char = "V" if for_numpy is True else "s"
        return True, f"{char}{sample_bytes}"
    return False, None
