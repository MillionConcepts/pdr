def spreadsheet_loader(filename):
    """
    HITS
    * msl_cmn
        * DIFFRACTION_ALL_RDR
        * ENERGY_SINGLE_RDR
        * MINERAL_TABLES
    * msl_sam
        * l0_qms
        * l1a_qms
        * l1b_qms
    """
    import pandas as pd
    return pd.read_csv(filename)


def trivial_header_loader():
    """
    HITS
    * msl_cmn
        * DIFFRACTION_ALL_RDR
        * ENERGY_SINGLE_RDR
        * MINERAL_TABLES
    * msl_sam
        * l0_hk
        * l0_qms
        * l0_gc
        * l0_tls
        * l1a_hk
        * l1a_qms
        * l1a_gc
        * l1a_tls
        * l1b_qms
        * l1b_gc
        * l2_qms
        * l2_gc
        * l2_tls
    """
    return True


def fix_mangled_name(data):
    """
    HITS
    * msl_cmn
        * HOUSEKEEPING
    """
    object_name = "CHMN_HSKN_HEADER_TABLE"
    block = data.metablock_(object_name)
    return block


def get_offset(object_name):
    """
    incorrectly specifies object length rather than start byte

    HITS
    * msl_cmn
        * DIFFRACTION_ALL_RDR
        * ENERGY_SINGLE_RDR
        * MINERAL_TABLES
        * CCD_FRAME
        * DIFFRACTION_SINGLE
        * DIFFRACTION_SPLIT
        * DIFFRACTION_ALL
        * ENERGY_ALL
        * ENERGY_SINGLE
        * ENERGY_SPLIT
        * HOUSKEEPING
        * TRANSMIT_RAW
    """
    if object_name == "HISTOGRAM":
        return True, 300
    if object_name == "CHMN_HSK_HEADER_TABLE":
        return True, 0
    return False, None
