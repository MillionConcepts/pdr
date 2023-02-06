from functools import partial


def jiram_rdr_sample_type():
    """
    JIRAM RDRs, both images and tables, are labeled as MSB but
    are actually LSB.
    """
    return "<f"


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


def bit_start_find_and_fix(list_of_pvl_objects_for_bit_columns, start_bit_list):
    if list_of_pvl_objects_for_bit_columns[-1].get("NAME") == "NADIR_OFFSET_SIGN":
        special_start_bit_list = start_bit_list
        special_start_bit_list[-1] = 16
        return True, special_start_bit_list
    return False, None
