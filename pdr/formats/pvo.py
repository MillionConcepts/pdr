def orpa_low_res_loader(data, name):
    # ORPA low resolution: labels for earlier orbits have the correct ROW_BYTES,
    # but there is a typo introduced later that says 'ROW_BYTES = 241' instead
    # of 243
    block = data.metablock_(name)
    block["ROW_BYTES"] = 243
    return block


def oims_12s_loader(data, name):
    # OIMS 12 second averages: all labels say 'ROWS = 42' reglardless of the
    # data's actual length
    block = data.metablock_(name)
    block["ROWS"] = data.metaget_("FILE_RECORDS")
    return block
