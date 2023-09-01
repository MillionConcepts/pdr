def sdc_edr_hdu_name(name):
    """
    pointer names do not correspond to HDU names in some SDC raw FITS files,
    and some labels fail to mention some HDUs, preventing the use of normal
    HDU indexing.
    """
    return {
        "HEADER": 0,
        "EXTENSION_DATA_HEADER": 1,
        "EXTENSION_DATA_TABLE": 1,
        "EXTENSION_HK_SDC_HEADER": 2,
        "EXTENSION_HK_SDC_TABLE": 2,
        "EXTENSION_HK_0X004_HEADER": 3,
        "EXTENSION_HK_0X004_TABLE": 3,
        "EXTENSION_HK_0X00D_HEADER": 4,
        "EXTENSION_HK_0X00D_TABLE": 4,
        "EXTENSION_HK_0X00A_HEADER": 5,
        "EXTENSION_HK_0X00A_TABLE": 5,
        "EXTENSION_THRUSTERS_HEADER": 6,
        "EXTENSION_THRUSTERS_TABLE": 6
    }[name]

