def table_loader(data, pointer):
    # we don't support these right now, or maybe ever
    if pointer == "ERROR_CONTROL_TABLE":
        return True, data.tbd
    # clarifying SCIENCE_HEADER_TABLE-- it is a TABLE, not a HEADER
    return True, data.read_table
