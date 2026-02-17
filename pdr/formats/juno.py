from __future__ import annotations

def jiram_rdr_sample_type():
    """
    JIRAM RDRs, both images and tables, are labeled as MSB but
    are actually LSB.

    HITS
    * juno_jiram
        * IMG_RDR
        * SPE_RDR
    """
    return "<f"


# noinspection PyProtectedMember
def waves_burst_fix_table_names(data, name):
    """
    WAVES burst files that include frequency offset tables have mismatched
    pointer/object names.

    HITS
    * juno_waves
        * CDR_BURST
    """
    if name == "DATA_TABLE":
        object_name = "TABLE"
    elif name == "FREQ_OFFSET_TABLE":
        object_name = "DATA_TABLE"
    block = data.metablock_(object_name)
    return block


def bit_start_find_and_fix(
    list_of_pvl_objects_for_bit_columns, start_bit_list
):
    """
    HITS
    * juno_jiram
        * LOG_IMG_RDR
        * LOG_SPE_RDR
        * LOG_IMG_EDR
        * LOG_SPE_EDR
    * mgs_tes
        * ATM
        * BOL
        * OBS
        * RAD_tab
    * pvo
        * pos_sedr
    """
    if (
        list_of_pvl_objects_for_bit_columns[-1].get("NAME")
        == "NADIR_OFFSET_SIGN"
    ):
        special_start_bit_list = start_bit_list
        special_start_bit_list[-1] = 16
        return True, special_start_bit_list
    return False, None


def uvs_rdr_start_byte(name, hdul):
    """
    Sometimes, the start byte is incorrectly recorded in the PDS3 labels (It
    is always wrong in the PDS4 labels. We do not have a "check" for that yet,
    so I recommend using the PDS3 labels). Here we use the FITS index
    defined by the mission for each object to look up the correct start_byte in
    the HDU fileinfo.

    This won't work if HDUs are missing etc, but I have not encountered that.

    HITS
    * juno_uvs
        * RDR
    """
    import warnings
    # indices are in online PDS docs and comments in the labels
    index_dict = {'CALIBRATED_SPECTRAL_HEADER': 0,
                  'CALIBRATED_SPECTRAL_IMAGE': 0,
                  'ACQUISITION_LIST_HEADER': 1,
                  'ACQUISITION_LIST_TABLE': 1,
                  'CALIBRATED_PHOTON_LIST_HEADER': 2,
                  'CALIBRATED_PHOTON_LIST_TABLE': 2,
                  'ANCILLARY_DATA_HEADER': 3,
                  'ANCILLARY_DATA_TABLE': 3,
                  'CALIBRATED_ANALOG_COUNT_RATE_HEADER': 4,
                  'CALIBRATED_ANALOG_COUNT_RATE_TABLE': 4,
                  'CALIBRATED_DIGITAL_COUNT_RATE_HEADER': 5,
                  'CALIBRATED_DIGITAL_COUNT_RATE_TABLE': 5,
                  'HOUSEKEEPING_HEADER': 6,
                  'HOUSEKEEPING_TABLE': 6,
                  'WAVELENGTH_LOOKUP_HEADER': 7,
                  'WAVELENGTH_LOOKUP_IMAGE': 7,
                  'MASK_INFORMATION_HEADER': 8,
                  'MASK_INFORMATION_TABLE': 8,
                  }
    try:
        correct_index = index_dict[name]
        hdu = hdul[correct_index]
        hinfo = hdu.fileinfo()
        if 'HEADER' in name:
            return hinfo['hdrLoc']
        else:
            return hinfo['datLoc']
    except Exception as e:
        warnings.warn("This key doesn't appear to be in the FITS file.")
        return None


def uvs_edr_start_byte(name, hdul):
    """
    Sometimes, the start byte is incorrectly recorded in the PDS3 labels (It
    is always wrong in the PDS4 labels. We do not have a "check" for that yet,
    so I recommend using the PDS3 labels). Here we use the FITS index
    defined by the mission for each object to look up the correct start_byte in
    the HDU fileinfo.

    This won't work if HDUs are missing etc, but I have not encountered that.

    HITS
    * juno_uvs
        * EDR
    """
    import warnings
    # indices are in online PDS docs and comments in the labels
    index_dict = {'SPECTRAL_VS_SPATIAL_HEADER': 0,
                  'SPECTRAL_VS_SPATIAL_IMAGE': 0,
                  'SPATIAL_VS_TIME_HEADER': 1,
                  'SPATIAL_VS_TIME_QUBE': 1,
                  'FRAME_LIST_HEADER': 2,
                  'FRAME_LIST_TABLE': 2,
                  'SCAN_MIRROR_POSITIONS_HEADER': 3,
                  'SCAN_MIRROR_POSITIONS_TABLE': 3,
                  'RAW_FRAME_HEADER': 4,
                  'RAW_FRAME_TABLE': 4,
                  'ANALOG_COUNT_RATE_HEADER': 5,
                  'ANALOG_COUNT_RATE_TABLE': 5,
                  'DIGITAL_COUNT_RATE_HEADER': 6,
                  'DIGITAL_COUNT_RATE_TABLE': 6,
                  'PULSE_HEIGHT_DISTRIBUTION_LA_HEADER': 7,
                  'PULSE_HEIGHT_DISTRIBUTION_LA_QUBE': 7,
                  'PULSE_HEIGHT_DISTRIBUTION_STELLAR_HEADER': 8,
                  'PULSE_HEIGHT_DISTRIBUTION_STELLAR_QUBE': 8,
                  'PULSE_HEIGHT_DISTRIBUTION_STIM_HEADER': 9,
                  'PULSE_HEIGHT_DISTRIBUTION_STIM_QUBE': 9,
                  'HOUSEKEEPING_HEADER': 10,
                  'HOUSEKEEPING_TABLE': 10,
                  'PARAMETER_LIST_HEADER': 11,
                  'PARAMETER_LIST_TABLE': 11,
                  }

    try:
        correct_index = index_dict[name]
        hdu = hdul[correct_index]
        hinfo = hdu.fileinfo()
        if 'HEADER' in name:
            return hinfo['hdrLoc']
        else:
            return hinfo['datLoc']
    except Exception as e:
        warnings.warn("This key doesn't appear to be in the FITS file.")
        return None
