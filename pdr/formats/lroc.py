def lroc_edr_sample_type():
    """
    LROC EDRs specify signed integers but appear to be unsigned.
    """
    return '>B'
