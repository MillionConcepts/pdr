from pdr.loaders.queries import table_position


def marsis_get_position(identifiers, block, target, name, start_byte):
    """"""
    table_props = table_position(identifiers, block, target, name, start_byte)
    n_records = identifiers["FILE_RECORDS"]
    record_bytes = 143
    table_props["length"] = n_records * record_bytes
    return table_props

def aspera_table_loader(filename, fmtdef_dt):
    """
    The ASPERA IMA EDRs are ascii csv tables containing 2 data types: SENSOR and
    MODE. The VALUES column is repeated and has 96 items total. In the MODE 
    rows only the first VALUES item contains data, and should be followed by 95
    'missing' items.
    In reality these rows have 96 empty/missing items because of an extra comma.
    This special case cuts off the extra column during the pd.read_csv() call.
    """
    import pandas as pd
    
    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=None,
                        usecols=range(len(fmtdef.NAME.tolist())))
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table

