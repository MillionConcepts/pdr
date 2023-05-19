from pdr.loaders.queries import table_position


def get_sample_type(sample_type, sample_bytes):
    if sample_type == "CHARACTER":
        return True, f"V{sample_bytes}"
    return False, None


def get_position(identifiers, block, target, name, filename):
    table_props = table_position(identifiers, block, target, name, filename)
    n_records = identifiers["FILE_RECORDS"]
    record_bytes = 143
    table_props['length'] = n_records * record_bytes
    return table_props
