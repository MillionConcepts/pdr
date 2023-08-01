def near_edr_hdu_name(name, data_set_id):
    """
    pointer names do not correspond closely to HDU names in some NEAR EDR
    FITS files.
    """
    if '-NIS-5' in data_set_id:
        return True, name.replace("TABLE", "")
    return True, name.replace("TABLE", "BINARY_TBL")
