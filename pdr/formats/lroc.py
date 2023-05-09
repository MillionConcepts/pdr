from functools import partial

from pdr.loaders.queries import get_image_properties


def lroc_edr_sample_type():
    """
    LROC EDRs specify signed integers but appear to be unsigned.
    """
    return '>B'
