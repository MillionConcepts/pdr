from pdr.loaders.queries import table_position


def get_position(identifiers, block, target, name, start_byte):
    table_props = table_position(identifiers, block, target, name, start_byte)
    n_records = identifiers["FILE_RECORDS"]
    record_bytes = 143
    table_props['length'] = n_records * record_bytes
    return table_props
