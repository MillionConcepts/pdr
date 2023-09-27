from pdr.loaders.queries import read_table_structure

def get_structure(block, name, filename, data, identifiers):
    fmtdef = read_table_structure(
        block, name, filename, data, identifiers
    )
    # The first column in the MCS (EDR/RDR/DDR) format files are just named "1"
    # which is being read as 'int'. This was causing problems in read_table
    # during the table.drop call 
    fmtdef["NAME"] = fmtdef["NAME"].values.astype(str)
    return fmtdef, None
