import re


def generic_header_hdu_name(name):
    """
    When the "HEADER" pointer is also a subset of another pointer name
    (e.g. EXTENSION_HK_HEADER), the object returned by data["HEADER"] is
    actually from the pointer with the longer name.
    """
    return True, 0

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
    if name.startswith("ET") or name.startswith("QUATERNIONS"):
        return True, 7
    if name.startswith("RALPH") or name.startswith("HK"):
        return True, 8
    raise NotImplementedError("don't recognize this LEISA pointer name")


def mvic_eng_edr_hdu_name(name):
    """
    pointer names do not correspond to HDU names in some MVIC raw FITS files.
    """
    return True, re.sub(
        r"EXTENSION_HK(_TABLE)?", "HOUSEKEEPING", name
    )

def mvic_sci_edr_hdu_name(name):
    """
    MVIC EDR FITS files in the "calibrated" dataset do not have named HDUs.
    """
    if name.startswith("HEADER") or name.startswith("IMAGE"):
        return True, 0
    name = name.replace("EXTENSION_", "")
    if name.startswith("CALGEOM"):
        return True, 1
    if name.startswith("ERROR_EST"):
        return True, 2
    if name.startswith("QUALITY"):
        return True, 3
    raise NotImplementedError("don't recognize this MVIC pointer name")

def mvic_rdr_hdu_name(name):
    """
    MVIC cal FITS files do not have named HDUs.
    """
    if name.startswith("HEADER") or name.startswith("IMAGE"):
        return True, 0
    name = name.replace("EXTENSION_", "")
    if name.startswith("ERROR_EST"):
        return True, 1
    if name.startswith("QUALITY"):
        return True, 2
    raise NotImplementedError("don't recognize this MVIC pointer name")


def pepssi_hdu_name(name):
    """
    some PEPSSI HDU names are subsets of other HDU names, which causes them
    to open wrong in the normal FITS workflow
    """
    if name.startswith("HEADER") or name.startswith("IMAGE"):
        return True, name
    name = name.replace("EXTENSION_", "")
    name = name.replace("_TABLE", "")
    return True, name

def get_fn(data):
    """
    The PEPSSI DDRs have an extra space at the start of the SPREADSHEET
    pointer's filename that causes 'file not found' errors.
    """
    from pathlib import Path
    
    label = Path(data.labelname)
    return True, Path(label.parent, f"{label.stem}.csv")

