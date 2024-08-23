from pdr.loaders.queries import table_position


def marsis_get_position(identifiers, block, target, name, start_byte):
    """
    HITS
    * mex_marsis
        * TEC_EDR
    """
    table_props = table_position(identifiers, block, target, name, start_byte)
    n_records = identifiers["FILE_RECORDS"]
    record_bytes = 143
    table_props["length"] = n_records * record_bytes
    return table_props


def aspera_table_loader(filename, fmtdef_dt):
    """
    The ASPERA IMA EDRs are ascii csv tables containing 2 data types: SENSOR
    and MODE. The VALUES column is repeated and has 96 items total. In the MODE
    rows only the first VALUES item contains data, and should be followed by 95
    'missing' items.
    In reality these rows have 96 empty/missing items because of an extra
    comma. This special case cuts off the extra column during the pd.read_csv()
    call.

    HITS
    * mex_aspera
        * ima
    """
    import pandas as pd
    
    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(
        filename, header=None, usecols=range(len(fmtdef.NAME.tolist()))
    )
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table


def aspera_ima_ddr_structure(block, name, filename, data, identifiers):
    """
    The ASPERA IMA DDR table opens correctly as written in its label, but
    the BYTES values for columns 3 and 4 are wrong.

    HITS
    * mex_aspera
        * ima_ddr
    """
    from pdr.loaders.queries import read_table_structure

    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[2, "BYTES"] = 12
    fmtdef.at[3, "BYTES"] = 12
    return fmtdef, None


def pfs_edr_special_block(data, name):
    """
    The PFS EDRs have a few errors in their labels prior to orbit 8945, after
    which they are corrected.

    HITS
    * mex_marsis
        * raw_lwc
        * raw_swc
        * cal_lwc
        * cal_swc
        * hk_early_mission
        * orb001_lwc
        * orb001_swc
    """
    block = data.metablock_(name)
    orbit_number = data.metaget_("ORBIT_NUMBER")
    
    if orbit_number == "N/A" or int(orbit_number) < 8945:
        # Fixes the number of rows in the table by replacing ROWS with
        # FILE_RECORDS.
        block["ROWS"] = data.metaget_("FILE_RECORDS")
        # Replaces the time columns' DATA_TYPEs with the correct type based on
        # products created later in the mission.
        for item in iter(block.items()):
            if "COLUMN" in item:
                if item[1]["NAME"] == "OBT OBSERVATION TIME":
                    item[1]["DATA_TYPE"] = "PC_REAL"
                if item[1]["NAME"] == "SCET OBSERVATION TIME":
                    item[1]["DATA_TYPE"] = "PC_UNSIGNED_INTEGER"
        return True, block
    return False, block


def mrs_ddr_atmo_position(identifiers, block, target, name, start_byte):
    """
    The MRS derived atmosphere profiles were opening with data cut off at the
    ends of the tables. Recalculating the table length with ROW_BYTES = 278
    instead of 276 fixes it.

    HITS
    * mex_mrs
        * occ_atmo
    """
    table_props = table_position(identifiers, block, target, name, start_byte)
    row_bytes = 278
    table_props["length"] = row_bytes * block["ROWS"]
    return table_props


def mrs_get_position(identifiers, block, target, name, start_byte):
    """
    MRS ICL level 1b DOPPLER_TABLEs and ODF level 2 RANGING_TABLEs undercount
    ROW_BYTES by 1.

    HITS
    * mex_mrs
        * lvl_1b_icl (partial)
        * lvl_2_odf (partial)
    """
    table_props = table_position(identifiers, block, target, name, start_byte)
    row_bytes = block["ROW_BYTES"] + 1
    table_props["length"] = row_bytes * block["ROWS"]
    return table_props


def mrs_l1b_odf_table_loader(filename, fmtdef_dt):
    """
    MRS level 1b ODF labels have variable and sometimes incorrect ROW_BYTES
    values.

    HITS
    * mex_mrs
        * lvl_1b_odf
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=None, sep=r"\s+")
    table.columns = [
        f for f in fmtdef['NAME'] if not f.startswith('PLACEHOLDER')
    ]
    return table


def mrs_l1b_odf_rmp_redirect(data):
    """
    RMP tables are a subset of MRS level 1b ODFs that were not opening because
    their pointer and object names do not match.
    
    HITS:
    * mex_mrs
        * lvl_1b_odf (partial)
    """
    object_name = "RAMP_TABLE"
    block = data.metablock_(object_name)
    return block

def vmc_rdr_hdu_selection(name, hdulist):
    """
    The VMC RDRs have 1 IMAGE pointer and 2 IMAGE objects. From the volume's 
    readme: "The first layer includes the calibrated values, and the second 
    layer includes the raw values." It is unclear whether or not the 'second 
    layer' is a copy of the EDR image or if intermediate calibration steps 
    have been applied to it.
    Assuming the single band image is akin to the EDRs, this special case 
    returns the multiband calibrated image.

    HITS
    * mex_vmc
        * rdr
    """

    return hdulist.fileinfo(1)['datLoc']
