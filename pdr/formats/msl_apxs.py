def table_loader(data, pointer):
    # we don't support these right now, or maybe ever
    if pointer == "ERROR_CONTROL_TABLE":
        return data.tbd
    # clarifying SCIENCE_HEADER_TABLE-- it is a TABLE, not a HEADER
    return data.read_table
