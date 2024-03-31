def get_special_block(data, name):
    """
    Mariner 9 IRIS tables have 316 ROW_PREFIX_BYTES followed by 1 column
    with 1500 ITEMS. The column's START_BYTE = 317, but it should be 1.

    HITS
    * mariner
        * iris
    """
    block = data.metablock_(name)
    block["COLUMN"]["START_BYTE"] = 1
    return block
