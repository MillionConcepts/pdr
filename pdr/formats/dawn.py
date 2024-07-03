class DoesNotExistError(Exception):
    """"""
    pass


def dawn_history_hdu_exception():
    """
    filter out spurious HISTORY pointer

    HITS
    * dawn
        * fc_edr_fit
        * fc_rdr_fit
    """
    raise DoesNotExistError(
        "Dawn FITS HISTORY extensions do not actually exist."
    )
