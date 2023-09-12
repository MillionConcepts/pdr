import re

from pdr.loaders.queries import get_fits_id


def sdc_edr_hdu_name(name):
    """
    pointer names do not correspond to HDU names in some SDC raw FITS files,
    and some labels fail to mention some HDUs, preventing the use of normal
    HDU indexing.
    """
    return {
        "HEADER": 0,
        "EXTENSION_DATA": 1,
        "EXTENSION_HK_SDC": 2,
        "EXTENSION_HK_0X004": 3,
        "EXTENSION_HK_0X00D": 4,
        "EXTENSION_HK_0X00A": 5,
        "EXTENSION_THRUSTERS": 6,
    }[re.sub("(_HEADER|_TABLE)", "", name)]


def rex_hdu_name(name):
    """same issue."""
    return {
        "HEADER": 0,
        "ARRAY": 0,
        "EXTENSION_IQVALS": 1,
        "EXTENSION_RAD_TIME_TAGS": 2,
        "EXTENSION_HK_0X004": 3,
        "EXTENSION_HK_0X016": 4,
        "EXTENSION_HK_0X084": 5,
        "EXTENSION_HK_0X096": 6,
        "EXTENSION_THRUSTERS": 7,
        "EXTENSION_SSR_SH": 8
    }[re.sub(r"(_HEADER|_TABLE|_IMAGE|_ARRAY)(_\d)?", "", name)]


def pepssi_edr_hdu_name(name):
    """same issue."""
    return {
        "HEADER": 0,
        "EXTENSION_N1": 1,
        "EXTENSION_N2": 2,
        "EXTENSION_N2_STATUS": 3,
        "EXTENSION_PHA_ELECTRON": 4,
        "EXTENSION_PHA_LOW_ION": 5,
        "EXTENSION_PHA_HIGH_ION": 6
    }[re.sub(r"(_HEADER|_TABLE)(_\d)?", "", name)]


def pepssi_pluto_rdr_hdu_name(name):
    """things are different on pluto."""
    return {
        "HEADER": 0,
        "IMAGE": 0,
        "EXTENSION_SPEC_PROTONS": 1,
        "EXTENSION_SPEC_HELIUM": 2,
        "EXTENSION_SPEC_HEAVIES": 3,
        "EXTENSION_SPEC_ELECTRONS": 4,
        "EXTENSION_SPEC_LOWION": 5,
        "EXTENSION_FLUX": 6,
        "EXTENSION_FLUXN1A": 7,
        "EXTENSION_FLUXN1B": 8,
        "EXTENSION_PHA_LOW_ION": 9,
        "EXTENSION_PHA_HIGH_ION": 10,
    }[re.sub(r"(_HEADER|_TABLE|_IMAGE|_ARRAY)(_\d)?", "", name)]


def pepssi_rdr_hdu_name(name):
    """same issue."""
    return {
        "HEADER": 0,
        "IMAGE": 0,
        "EXTENSION_SPEC_PROTONS": 1,
        "EXTENSION_SPEC_HELIUM": 2,
        "EXTENSION_SPEC_HEAVIES": 3,
        "EXTENSION_SPEC_ELECTRONS": 4,
        "EXTENSION_SPEC_LOWION": 5,
        "EXTENSION_FLUX": 6,
        "EXTENSION_FLUXN1A": 7,
        "EXTENSION_FLUXN1B": 8,
        "EXTENSION_PHA_ELECTRON": 9,
        "EXTENSION_PHA_LOW_ION": 10,
        "EXTENSION_PHA_HIGH_ION": 11,
    }[re.sub(r"(_HEADER|_TABLE|_IMAGE|_ARRAY)(_\d)?", "", name)]


def get_fn(data):
    """
    The PEPSSI DDRs have an extra space at the start of the SPREADSHEET
    pointer's filename that causes 'file not found' errors.
    """
    from pathlib import Path

    label = Path(data.labelname)
    return True, Path(label.parent, f"{label.stem}.csv")


def swap_hdu_stubs(data, identifiers, fn, name):
    print('went to special case')
    headers = [key for key in data.keys() if key.startswith("EXTENSION") and key.endswith("_HEADER")]
    noheaders = [key for key in data.keys() if key.startswith("EXTENSION") and not key.endswith("_HEADER")]
    if len(headers) != len(noheaders):
        headers_stripped = [n.split('_'+n.split('_')[-1])[0] for n in headers]
        noheaders_stripped = [n.split('_'+n.split('_')[-1])[0] for n in noheaders]
        stubs = [val+"_HEADER" for val in headers_stripped if val not in noheaders_stripped+noheaders]
        return get_fits_id(data, identifiers, fn, name, other_stubs=stubs)
    else:
        return get_fits_id(data, identifiers, fn, name, other_stubs=None)
