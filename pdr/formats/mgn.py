from io import StringIO

from pdr.utils import head_file


def geom_table_loader(filename, fmtdef_dt):
    """
    The Magellan radar system geometry tables include null bytes between rows.
    """
    import pandas as pd
    from pdr.utils import head_file

    fmtdef, dt = fmtdef_dt
    with head_file(filename) as buf:
        bytes_ = buf.read().replace(b"\x00", b"")
    string_buffer = StringIO(bytes_.decode())
    string_buffer.seek(0)
    table = pd.read_csv(string_buffer, header=None)
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    string_buffer.close()
    table.columns = fmtdef.NAME.tolist()
    return table


def orbit_table_in_img_loader():
    return True


def get_fn(data):
    target = data.filename
    return True, target


def occultation_loader(identifiers, fmtdef_dt, block, filename):
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
    from pdr.pd_utils import compute_offsets

    position_records = compute_offsets(fmtdef).to_dict("records")
    for record in position_records:
        col_length = record["BYTES"]
        colspecs.append((record["SB_OFFSET"], record["SB_OFFSET"] + col_length))
    string_buffer.seek(0)
    table = pd.read_fwf(string_buffer, header=None, colspecs=colspecs)
    string_buffer.close()

    table.columns = fmtdef.NAME.tolist()
    return table


def gvanf_sample_type():
    return ">B"
