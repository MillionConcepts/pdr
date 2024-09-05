from pdr.loaders.queries import read_table_structure
from pdr.pd_utils import insert_sample_types_into_df, compute_offsets

def rosetta_table_loader(filename, fmtdef_dt):
    """
    HITS
    * rosetta_rpc
        * RPCMIP
    """
    import astropy.io.ascii

    table = astropy.io.ascii.read(filename).to_pandas()
    fmtdef, dt = fmtdef_dt
    table.columns = fmtdef["NAME"].to_list()
    return table

def midas_rdr_sps_structure(block, name, filename, data, identifiers):
    """
    SPS TIME_SERIES tables are made up of a repeated container with 4 columns 
    followed by a non-repeated checksum column. Something about the specific 
    combination of ROW_PREFIX_BYTES, a repeated CONTAINER with sub-columns, and 
    one more non-repeating COLUMN causes problems with compute_offsets(). 
    Skipping the computer_offsets() call here outputs reasonable looking tables.

    TODO: This seems like a more general issue with how compute_offsets() 
    handles a repeated container followed by a single column

    HITS
    * rosetta_dust
        * RDR_midas_sps
    """
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    for end in ("_PREFIX", "_SUFFIX", ""):
        length = block.get(f"ROW{end}_BYTES")
        if length is not None:
            fmtdef[f"ROW{end}_BYTES"] = length

    # fmtdef.at[1024, "BLOCK_BYTES"] = fmtdef.at[1024, "BYTES"]
    # fmtdef = compute_offsets(fmtdef)

    return insert_sample_types_into_df(fmtdef, identifiers)

def fix_pad_length_structure(block, name, filename, data, identifiers):
    """
    The MIDAS FSC tables and several CONSERT ptypes have ROW_PREFIX_BYTES, 
    ROW_SUFFIX_BYTES, and a COLUMN with multiple ITEMS. compute_offsets() 
    calculates the wrong end_byte and pad_length values from the BYTES and 
    ROW_BYTES values in their labels.

    HITS
    * rosetta_consert
        * l2_land
        * l2_orbit
        * l3_land
        * l3_land_fss
        * l3_orbit
        * l3_orbit_fss
        * l4_land
        * l4_orbit
        * l4_orbit_grnd
    * rosetta_dust
        * RDR_midas_fsc
    """
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    for end in ("_PREFIX", "_SUFFIX", ""):
        length = block.get(f"ROW{end}_BYTES")
        if length is not None:
            fmtdef[f"ROW{end}_BYTES"] = length

    # to calculate end_byte correctly in compute_offsets()
    fmtdef["BYTES"] = fmtdef["ITEM_BYTES"]
    # to calculate pad_length correctly in compute_offsets()
    fmtdef["ROW_BYTES"] = fmtdef["ROW_BYTES"] + fmtdef["ROW_PREFIX_BYTES"]
    
    fmtdef = compute_offsets(fmtdef)
    return insert_sample_types_into_df(fmtdef, identifiers)
