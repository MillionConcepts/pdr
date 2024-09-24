def mssso_cal_start_byte(name, hdulist):
    """
    A small subset of MSSSO CASPIR calibration images have the wrong start byte 
    for the IMAGE pointer in their PDS3 labels

    HITS
    * sl9_jupiter_impact
        * mssso_cal
    """
    if 'HEADER' in name:
        return 0
    return hdulist.fileinfo(0)['datLoc']

def wff_atm_special_block(data, name):
    """
    One WFF/ATM DEM image opens fine (BBMESA2X2), the other two (SCHOONER2X2 
    and SEDAN2X2) have their LINES and LINE_SAMPLES values backwards.

    HITS
    * wff_atm
        * dem_img
    """
    block = data.metablock_(name)

    if data.metaget_("PRODUCT_ID").startswith("S"):
        real_line_samples = block["LINES"]
        real_lines = block["LINE_SAMPLES"]

        block["LINES"] = real_lines
        block["LINE_SAMPLES"] = real_line_samples
        return True, block
    
    return False, block
