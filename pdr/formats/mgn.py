from io import StringIO
from pdr.utils import head_file
from pdr.pd_utils import compute_offsets
import pandas as pd

def geom_table_loader(data, pointer):
    """
    The Magellan radar system geometry tables include null bytes between rows.
    """
    def load_mgn_geom_table(*_, **__):
        import pandas as pd
        from pdr.utils import head_file

        fmtdef, dt = data.parse_table_structure(pointer)
        with head_file(data.file_mapping[pointer]) as buf:
            bytes_ = buf.read().replace(b"\x00", b"")
        string_buffer = StringIO(bytes_.decode())
        string_buffer.seek(0)
        table = pd.read_csv(string_buffer, header=None)
        assert len(table.columns) == len(fmtdef.NAME.tolist())
        string_buffer.close()
        table.columns = fmtdef.NAME.tolist()
        return table
    return load_mgn_geom_table


def orbit_table_in_img_loader(data, pointer):
    return data.trivial


def get_fn(data):
    target = data.filename
    return True, target


def occultation_loader(data, pointer):
    def load_occult_table(*_, **__):
        fmtdef, dt = data.parse_table_structure(pointer)
        record_length = data.metablock_(pointer)['ROW_BYTES']

        # Checks end of each row for newline character. If missing, removes extraneous
        # newline from middle of the row and adjusts for the extra byte.
        with head_file(data.file_mapping[pointer]) as f:
            processed = bytearray()
            for row in range(0, data.metadata["FILE_RECORDS"]):
                bytes_ = f.read(record_length)
                if not bytes_.endswith(b'\n'):
                    new_bytes_ = bytes_.replace(b'\n', b'') + f.read(1)
                    processed += new_bytes_
                else:
                    processed += bytes_
        string_buffer = StringIO(processed.decode())

        # adapted from _interpret_as_ascii()
        colspecs = []
        position_records = compute_offsets(fmtdef).to_dict('records')
        for record in position_records:
            col_length = record['BYTES']
            colspecs.append((record['OFFSET'], record['OFFSET'] + col_length))
        string_buffer.seek(0)
        table = pd.read_fwf(string_buffer, header=None, colspecs=colspecs)
        string_buffer.close()

        table.columns = fmtdef.NAME.tolist()
        return table
    return load_occult_table

def gvanf_sample_type(sample_type, sample_bytes, for_numpy):
    from pdr.datatypes import sample_types
    if 'N/A' in sample_type:
        sample_type = 'MSB_UNSIGEND_INTEGER'
        return True, sample_types(sample_type, int(sample_bytes), for_numpy=True)
    return False, None
