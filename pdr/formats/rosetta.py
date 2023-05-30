def rosetta_table_loader(filename, fmtdef_dt):
    import astropy.io.ascii

    table = astropy.io.ascii.read(filename).to_pandas()
    fmtdef, dt = fmtdef_dt
    table.columns = fmtdef["NAME"].to_list()
    return table
