from functools import partial

from pdr.formats import generic_image_properties


def jiram_image_loader(data, _):
    """
    JIRAM RDRs are specified as MSB but appear to be LSB.
    """
    props = generic_image_properties("IMAGE", data.metablock_("IMAGE"), data)
    props['sample_type'] = '<f'
    return partial(data.read_image, special_properties=props)


# noinspection PyProtectedMember
def waves_burst_with_offset_loader(data):
    """
    WAVES burst files that include frequency offset tables have mismatched
    pointer/object names. this is a slightly sloppy but expedient way to
    rectify them.
    """
    def wrap_getter(target, *args, method):
        if target == "DATA_TABLE":
            target = "TABLE"
        elif target == "FREQ_OFFSET_TABLE":
            target = "DATA_TABLE"
        return getattr(data.metadata, method)(target, *args)

    setattr(data, "metablock_", partial(wrap_getter, method="metablock_"))
    setattr(data, "metablock", partial(wrap_getter, method="metablock"))
    setattr(data, "metaget_", partial(wrap_getter, method="metaget_"))
    setattr(data, "metaget", partial(wrap_getter, method="metaget"))

    return data.read_table
