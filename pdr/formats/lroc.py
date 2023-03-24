from functools import partial

from pdr.loaders.queries import get_image_properties


def lroc_edr_image_loader(data, _):
    """
    LROC EDRs specify signed integers but appear to be unsigned.
    """
    props = get_image_properties("IMAGE", data.metablock_("IMAGE"), data)
    props['sample_type'] = '>B'
    return partial(data.read_image, special_properties=props)
