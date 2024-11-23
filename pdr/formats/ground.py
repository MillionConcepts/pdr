def mssso_cal_start_byte(name, hdulist):
    """
    A small subset of MSSSO CASPIR calibration images have the wrong start byte 
    for the IMAGE pointer in their PDS3 labels

    HITS
    * sl9_jupiter_impact
        * mssso_cal
    """
    if 'HEADER' in name:
        return 0
    return hdulist.fileinfo(0)['datLoc']


def wff_atm_special_block(data, name):
    """
    One WFF/ATM DEM image opens fine (BBMESA2X2), the other two (SCHOONER2X2 
    and SEDAN2X2) have their LINES and LINE_SAMPLES values backwards.

    HITS
    * wff_atm
        * dem_img
    """
    block = data.metablock_(name)

    if data.metaget_("PRODUCT_ID").startswith("S"):
        real_line_samples = block["LINES"]
        real_lines = block["LINE_SAMPLES"]

        block["LINES"] = real_lines
        block["LINE_SAMPLES"] = real_line_samples
        return True, block
    
    return False, block

def ebrocc_geom_get_position(identifiers, block, target, name, start_byte):
    """
    ROW_BYTES = 45 in the labels, but it should be 47

    HITS
    * ground_based
        * ring_occ_1989_geometry
    """
    from pdr.loaders.queries import table_position

    table_props = table_position(identifiers, block, target, name, start_byte)
    n_rows = block["ROWS"]
    row_bytes = block["ROW_BYTES"] + 2
    table_props["length"] = n_rows * row_bytes
    return table_props
