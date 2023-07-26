import re


def lorri_edr_hdu_name(name):
    """
    pointer names do not correspond to HDU names in some LORRI EDR FITS files.
    """
    return True, re.sub(
        r"EXTENSION_ENCODED_FIRST34(_IMAGE)?", "IMAGE HEADER", name
    )


def leisa_raw_hdu_name(name):
    """
    pointer names do not correspond to HDU names in some LEISA raw FITS files.
    """
    return True, name.replace("HK_TABLE", "HOUSEKEEPING")


def leisa_cal_hdu_name(name):
    """LEISA cal FITS files do not have named HDUs."""
    if name.startswith("HEADER") or name.startswith("IMAGE"):
        return True, 0
    name = name.replace("EXTENSION_", "")
    if name.startswith("CTR") or name.startswith("WAVELENGTHS"):
        return True, 1
    if name.startswith("POINTING") or name.startswith("ANGLES"):
        return True, 2
    if name.startswith("FLATFIELD"):
        return True, 3
    if name.startswith("GAIN") or name.startswith("CALIBRATION"):
        return True, 4
    if name.startswith("ERROR"):
        return True, 5
    if name.startswith("QUALITY"):
        return True, 6
    if name.startswith("ET") or name.startswith("QUARTERNIONS"):
        return True, 7
    if name.startswith("RALPH") or name.startswith("HK"):
        return True, 8
    raise NotImplementedError("don't recognize this LEISA pointer name")
