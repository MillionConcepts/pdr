def lroc_edr_sample_type():
    """
    LROC EDRs specify signed integers but appear to be unsigned.

    HITS
    * lroc
        * NAC_EDR
        * WAC_EDR
    """
    return ">B"
