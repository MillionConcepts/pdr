def near_edr_hdu_name(name, data_set_id):
    """
    pointer names do not correspond closely to HDU names in some NEAR NLR EDR
    FITS file.
    """
    if '-NIS-' in data_set_id:
        return True, name.replace("TABLE", "")
    return True, name.replace("TABLE", "BINARY_TBL")
