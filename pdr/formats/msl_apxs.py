import warnings


def table_loader(pointer):
    """
    we don't support these right now, or maybe ever

    HITS
    * msl_apxs
        * APXS_SCIENCE_EDR
    """
    warnings.warn(
        f"The MSL APXS {pointer} tables are not currently supported."
    )
    return True

def trivial_header_loader():
    """
    The HEADER pointer is just the SPREADSHEET table's header row, and it does 
    not open because "BYTES = UNK"

    HITS
    * msl_apxs
        * APXS_OXIDE_RDR
        * APXS_SPECTRUM_RDR
    """
    warnings.warn(
        f"The MSL APXS RDR HEADER pointers are not currently supported."
    )
    return True
