def jiram_rdr_sample_type():
    """
    JIRAM RDRs, both images and tables, are labeled as MSB but
    are actually LSB.

    HITS
    * juno_jiram
        * IMG_RDR
        * SPE_RDR
    """
    return "<f"


# noinspection PyProtectedMember
def waves_burst_fix_table_names(data, name):
    """
    WAVES burst files that include frequency offset tables have mismatched
    pointer/object names.

    HITS
    * juno_waves
        * CDR_BURST
    """
    if name == "DATA_TABLE":
        object_name = "TABLE"
    elif name == "FREQ_OFFSET_TABLE":
        object_name = "DATA_TABLE"
    block = data.metablock_(object_name)
    return block


def bit_start_find_and_fix(
    list_of_pvl_objects_for_bit_columns, start_bit_list
):
    """
    HITS
    * juno_jiram
        * LOG_IMG_RDR
        * LOG_SPE_RDR
        * LOG_IMG_EDR
        * LOG_SPE_EDR
    * mgs_tes
        * ATM
        * BOL
        * OBS
        * RAD_tab
    * pvo
        * pos_sedr
    """
    if (
        list_of_pvl_objects_for_bit_columns[-1].get("NAME")
        == "NADIR_OFFSET_SIGN"
    ):
        special_start_bit_list = start_bit_list
        special_start_bit_list[-1] = 16
        return True, special_start_bit_list
    return False, None
