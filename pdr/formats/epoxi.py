from pdr.loaders.queries import table_position


def cart_model_get_position(identifiers, block, target, name, start_byte):
    """
    The cartesian shape model's RECORD_BYTES and all three of the tables'
    ROW_BYTES should be 79 but the label lists them as 80.

    HITS
    * epoxi
        * shape
    """
    table_props = table_position(identifiers, block, target, name, start_byte)
    row_bytes = 79
    table_props["start"] = row_bytes * (target[1] - 1)
    table_props["length"] = row_bytes * block["ROWS"]
    return table_props


def hriv_deconv_mask_start_byte(name, hdulist):
    """
    The EPOXI HRIV deconvolved radiance files have incorrect start byte
    specifications for the MASK HDU.

    HITS
    * epoxi
        * hriv_deconvolved
    """
    if 'HEADER' in name:
        return hdulist.fileinfo('MASK')['hdrLoc']
    return hdulist.fileinfo('MASK')['datLoc']
