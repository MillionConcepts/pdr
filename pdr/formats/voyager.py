def get_special_block(data, name):
    # ROW_BYTES are listed as 144 in the labels for Uranus and Neptune MAG RDRs.
    # Their tables look the same, but the Neptune products open wrong. Setting
    # ROW_BYTES to 145 fixes it.
    block = data.metablock_(name)
    block["ROW_BYTES"] = 145 
    return block

