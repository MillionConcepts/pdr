from io import StringIO

from pdr.utils import head_file


def geom_table_loader(filename, fmtdef_dt):
    """
    The Magellan radar system geometry tables include null bytes between rows.

    HITS
    * gal_nims
        * impact
    * mgn_image
        * midr_tables
    """
    import pandas as pd
    from pdr.utils import head_file

    fmtdef, dt = fmtdef_dt
    with head_file(filename) as buf:
        bytes_ = buf.read().replace(b"\x00", b"")
    string_buffer = StringIO(bytes_.decode())
    string_buffer.seek(0)
    table = pd.read_csv(string_buffer, header=None)
    names = [n for n in fmtdef['NAME'] if 'PLACEHOLDER' not in n]
    assert len(table.columns) == len(names), 'column name mismatch'
    string_buffer.close()
    table.columns = names
    return table


def orbit_table_in_img_loader():
    """
    HITS
    * mgn_post_mission
        * fmap
        * fmap_browse
    """
    return True


def get_fn(data):
    """
    HITS
    * mgn_post_mission
        * fmap
        * fmap_browse
    """
    target = data.filename
    return True, target


def occultation_loader(identifiers, fmtdef_dt, block, filename):
    """
    Checks end of each row for newline character. If missing, removes
    extraneous newline from middle of the row and adjusts for the extra byte.
    Adapted from _interpret_as_ascii()

    HITS
    * mgn_occult
        * ddr
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    record_length = block["ROW_BYTES"]

    # Checks end of each row for newline character. If missing, removes extraneous
    # newline from middle of the row and adjusts for the extra byte.
    with head_file(filename) as f:
        processed = bytearray()
        for row in range(0, identifiers["FILE_RECORDS"]):
            bytes_ = f.read(record_length)
            if not bytes_.endswith(b"\n"):
                new_bytes_ = bytes_.replace(b"\n", b"") + f.read(1)
                processed += new_bytes_
            else:
                processed += bytes_
    string_buffer = StringIO(processed.decode())
    # adapted from _interpret_as_ascii()
    colspecs = []
    position_records = fmtdef.to_dict("records")
    for record in position_records:
        col_length = record["BYTES"]
        colspecs.append((record["SB_OFFSET"], record["SB_OFFSET"] + col_length))
    string_buffer.seek(0)
    table = pd.read_fwf(string_buffer, header=None, colspecs=colspecs)
    string_buffer.close()

    table.columns = fmtdef.NAME.tolist()
    return table.drop("PLACEHOLDER_0", axis=1)


def gvanf_sample_type():
    return ">B"
