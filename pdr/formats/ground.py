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
