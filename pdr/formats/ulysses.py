def gas_table_loader(filename, fmtdef_dt):
    """
    GASDATA.FMT has the wrong START_BYTE for columns in the container.
    After manually changing the labels during testing, START_BYTE was still
    not incrementing correctly with each repetition of the container.
    This fixes both issues with 1 special case.

    HITS
    * ulysses
        * gas
    """
    import pandas as pd
    fmtdef, dt = fmtdef_dt
    # Some tables use tabs as column deliminators, others use spaces.
    table = pd.read_csv(filename, skiprows=17, sep=r"\s+", header=None)
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table


def get_sample_type(base_samp_info):
    """
    The bit column's data_type is BIT_STRING, which throws errors. Guessing
    this should be MSB_BIT_STRING. The tables look correct when compared to
    their ASCII versions.

    HITS
    * ulysses
        * epac_pha_bin
    """
    from pdr.datatypes import sample_types
    sample_type = base_samp_info["SAMPLE_TYPE"]
    sample_bytes = base_samp_info["BYTES_PER_PIXEL"]

    if "BIT_STRING" == sample_type:
        sample_type = "MSB_BIT_STRING"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    return False, None


def get_special_block(data, name, identifiers):
    """
    START_BYTE is wrong for repeated columns within the container. ITEM_BYTES
    is also off by 1.

    HITS
    * ulysses
        * epac_all_chan
        * epac_omni_ele
        * epac_omni_pro
        * epac_pha_asc
        * epac_pha_bin
        * epac_prtl
        * epac_pstl
    """
    block = data.metablock_(name)
    if "ULY-J-EPAC-4-SUMM-PSTL" in identifiers["DATA_SET_ID"]:
        block["CONTAINER"]["COLUMN"]["ITEM_BYTES"] = 13
        block["CONTAINER"]["COLUMN"]["START_BYTE"] = 1
    elif "ULY-J-EPAC-4-SUMM-ALL-CHAN" in identifiers["DATA_SET_ID"]:
        block.getall('CONTAINER')[0]['COLUMN']['START_BYTE'] = 1
        block.getall('CONTAINER')[1]['CONTAINER']['START_BYTE'] = 1
        block.getall('CONTAINER')[1]['CONTAINER']['COLUMN']['START_BYTE'] = 1
    return block
