from pdr.loaders.queries import read_table_structure
from pdr.pd_utils import insert_sample_types_into_df, compute_offsets


def get_odf_structure(block, name, filename, data, identifiers):
    """"""
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[7, "BYTES"] = 2
    fmtdef[f"ROW_BYTES"] = block.get(f"ROW_BYTES")

    fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt


def get_ecs_structure(block, name, filename, data, identifiers):
    """
    HITS
    * mgs_rss_raw
        * ecs
    """
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    fmtdef.at[5, "START_BYTE"] = 80
    fmtdef[f"ROW_BYTES"] = block.get(f"ROW_BYTES")

    fmtdef = compute_offsets(fmtdef)
    fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt


def mola_pedr_table_loader(
        name,
        identifiers,
        fn,
        fmtdef_dt,
        block,
        start_byte,
    ):
    """
    Each row in the table has 3 format files that describe different sections 
    of the data. Two format files are the same across all rows, but the middle 
    of each row (bytes 501-528) is defined by 1 of 7 possible format files 
    depending on a flag in the FRAME_INDEX column (byte 492). This special case 
    opens the full table using the format file indicated by the pointer name, 
    then subsets to only the rows with a matching FRAME_INDEX flag. Most of the 
    table is being opened incorrectly, then discarded before the table is 
    returned to the user.

    TODO: It would probably be faster to check the FRAME_INDEX flag for each 
    row as it's being initally read, rather than reading the full table and 
    subsetting from there. It would almost certainly be less memory intensive 
    to do it that way.

    HITS
    * mgs_mola
        * pedr
    * mgs_sampler
        * pedr
    """
    import os
    from pathlib import Path
    from pdr.loaders.table import read_table

    # calculate how many rows are in the table and replace 'ROWS = "UNK"' 
    # (based on count_from_bottom_of_file())
    table_bytes = os.path.getsize(Path(fn)) - start_byte
    block["ROWS"] = int(table_bytes / block["ROW_BYTES"])

    # read the full table normally
    table = read_table(identifiers, fn, fmtdef_dt, None, block, start_byte,)
    # then subset the table based on the FRAME_INDEX flag
    frame_number = name.split('_')[2]
    table = table[table["FRAME_INDEX"] == int(frame_number)]

    return table


def mola_pedr_special_block(data, name):
    """
    Pointers to the format files have non-standard names, e.g. ^FIRST_STRUCTURE
    instead of ^STRUCTURE.

    HITS
    * mgs_mola
        * pedr
    * mgs_sampler
        * pedr
    """
    block = data.metablock_(name)
    block.add("^STRUCTURE", block.pop("^FIRST_STRUCTURE"))
    frame = name.split('_')[2]
    block.add("^STRUCTURE", block.pop(f"^FR_{frame}_ENG_STRUCTURE"))
    block.add("^STRUCTURE", block.pop("^THIRD_STRUCTURE"))
    return block
