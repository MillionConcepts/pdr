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
    name = name.replace("EXTENSION_", "")
    name = name.replace("_TABLE", "")
    return True, name

def get_fn(data):
    """
    The several DDR products have an extra space at the start of the
    SPREADSHEET pointer's filename that causes 'file not found' errors.
    """
    from pathlib import Path
    
    label = Path(data.labelname)
    return True, Path(label.parent, f"{label.stem}.csv")


def rex_SSR_hdu_name(name):
    """
    Some of the REX EDRs have a duplicate EXTENSION_SSR_SH_HEADER pointer. The
    first of the duplicate pointers should be EXTENSION_HK_0X096_HEADER. The
    corresponding FITS EDU name is HOUSEKEEPING_0X096.
    """
    return True, "HOUSEKEEPING_0X096 HEADER"

def rex_IQval_hdu_name(name):
    """
    The REX EXTENSION_IQVALS_HEADER pointers were opening as copies of the
    EXTENSION_SSR_SH_HEADER.
    """
    return True, "I AND Q VALUES HEADER"

def sdc_edr_hdu_name(name):
    """
    The SDC "DATA" and "HK_0X00A" pointers were opening from the wrong HDU
    headers.
    """
    if name == "EXTENSION_DATA_HEADER":
        return True, "DATA_HEADER"
    if name == "EXTENSION_HK_0X00A_HEADER":
        return True, 5
    return False, None

def leisa_ddr_hdu_name(name):
    """
    Some LEISA derived FITS files repeat their HDU names.
    """
    if name == "QUBE": # skip pointers that are opening correctly
        return False, None
    if name == "IMAGE":
        return True, 0
    name = name.replace("EXTENSION_", "")
    if name.startswith("WAVELENGTH"):
        return True, 1
    if name.startswith("ERROR_ESIMATE"):
        return True, 2
    if name.startswith("GAIN"):
        return True, 3
    if name.startswith("FLATFIELD"):
        return True, 4
    raise NotImplementedError("don't recognize this LEISA pointer name")

def alice_ddr_hdu_name(name):
    """
    The ALICE derived FITS products' repeated "SPECTRA" in their HDU names was
    causing issues where pdr was opening the wrong HDU.
    """
    name = name.replace("EXTENSION_", "")
    if name.startswith("SPECTRA"):
        return True, 1
    if name.startswith("UNC_SPECTRA"):
        return True, 2
    if name.startswith("REF_SPECTRA"):
        return True, 3
    if name.startswith("REF_UNCERTAINTY"):
        return True, 4
    if name.startswith("WAVELENGTH"):
        return True, 5
    if name.startswith("MET"):
        return True, 6
    if name.startswith("TAN_RADIUS"):
        return True, 7
    raise NotImplementedError("don't recognize this ALICE pointer name")

def mvic_ddr_hdu_name(name):
    """ Only the BLUE and CH4 pointers were opening previously. """
    if name.startswith("PRIMARY"):
        return True, 0
    if name.startswith("BLUE"):
        return True, 1
    if name.startswith("RED"):
        return True, 2
    if name.startswith("NIR"):
        return True, 3
    if name.startswith("CH4"):
        return True, 4
    raise NotImplementedError("don't recognize this MVIC pointer name")
