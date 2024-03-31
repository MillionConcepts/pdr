class DoesNotExistError(Exception):
    """"""
    pass


def dawn_hdu_name(name):
    """
    filter out spurious HISTORY pointer

    HITS
    * dawn
        * fc_edr_fit
        * fc_rdr_fit
    """
    if name in ("IMAGE", "HEADER"):
        return 0
    elif name == 'HISTORY':
        raise DoesNotExistError(
            "Dawn FITS HISTORY extensions do not actually exist."
        )
    raise NotImplementedError("Unknown Dawn extension name")
