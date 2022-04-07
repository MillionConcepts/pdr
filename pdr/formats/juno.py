from functools import partial

from pdr.formats import generic_image_properties


def jiram_image_loader(data, _):
    """
    JIRAM RDRs are specified as MSB but appear to be LSB.
    """
    props = generic_image_properties("IMAGE", data.metablock_("IMAGE"), data)
    props['sample_type'] = '<f'
    return partial(data.read_image, special_properties=props)
