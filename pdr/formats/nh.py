import re


def lorri_edr_hdu_name(name):
    """
    pointer names do not correspond closely to HDU names in some LORRI EDR
    FITS files.
    """
    return True, re.sub(
        r"EXTENSION_ENCODED_FIRST34(_IMAGE)?", "IMAGE HEADER", name
    )
