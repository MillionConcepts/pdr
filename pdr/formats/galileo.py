import warnings

from pdr.loaders.utility import trivial


def galileo_table_loader():
    warnings.warn("Galileo EDR binary tables are not yet supported.")
    return trivial


def ssi_cubes_header_loader():
    # The Ida and Gaspra cubes have HEADER pointers but no defined HEADER objects
    return True


def nims_edr_sample_type(base_samp_info):
    from pdr.datatypes import sample_types

    # Each time byte order is specified for these products it is LSB, so this
    # assumes BIT_STRING refers to LSB_BIT_STRING
    sample_type = base_samp_info["SAMPLE_TYPE"]
    sample_bytes = base_samp_info["BYTES_PER_PIXEL"]
    if "BIT_STRING" == sample_type:
        sample_type = "LSB_BIT_STRING"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    if "N/A" in sample_type:
        sample_type = "CHARACTER"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    return False, None

def probe_structure(block, name, filename, data, identifiers):
    import pdr.loaders.queries
    
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    # Several NMS products have an incorrect BYTES value in one column
    if fmtdef.at[1,"NAME"] == "COUNTS":
        fmtdef.at[1,"BYTES"] = 8
    # One ASI product has incorrect BYTES values in multiple columns 
    elif identifiers["PRODUCT_ID"] == "HK01AD.TAB":
        fmtdef.at[1,"BYTES"] = 4
        fmtdef.at[3,"BYTES"] = 2
        fmtdef.at[5,"BYTES"] = 2
    return fmtdef, None

