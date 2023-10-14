def get_structure(block, name, filename, data, identifiers):
    from pdr.loaders.queries import read_table_structure
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    # GASDATA.FMT has the wrong START_BYTE for columns in the container.
    # After manually changing the labels during testing, START_BYTE was still
    # not incrementing correctly with each repetition of the container. 
    # This fixes both issues with 1 special case.
    for i in range(10):
        fmtdef.at[i+7, "START_BYTE"] = 1 + (i*7)
    return fmtdef, None

def get_sample_type(base_samp_info):
    from pdr.datatypes import sample_types
    sample_type = base_samp_info["SAMPLE_TYPE"]
    sample_bytes = base_samp_info["BYTES_PER_PIXEL"]
    # The bit column's data_type is BIT_STRING, which throws errors. Guessing
    # this should be MSB_BIT_STRING. The tables look correct when compared to
    # their ASCII versions.
    if "BIT_STRING" == sample_type:
        sample_type = "MSB_BIT_STRING"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    return False, None

def get_special_block(data, name):
    # START_BYTE is wrong for repeated columns within the container.
    # ITEM_BYTES is also off by 1.
    block = data.metablock_(name)
    block["CONTAINER"]["COLUMN"]["ITEM_BYTES"] = 13
    block["CONTAINER"]["COLUMN"]["START_BYTE"] = 1
    return block
