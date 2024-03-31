import warnings


def image_reply_table_loader():
    """
    HITS
    * msl_ccam
        * CCAM_RMI_EDR
    """
    warnings.warn(
        "MSL ChemCam IMAGE_REPLY binary tables are not supported "
        "due to a formatting error in label files."
    )
    return True
