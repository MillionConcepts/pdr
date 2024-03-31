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
