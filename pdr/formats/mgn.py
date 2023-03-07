from io import StringIO
from pdr.parselabel.pds3 import pointerize

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
    def load_orbit_table_in_img(*_, **__):
        orbit_file = data.metaget_(pointerize(pointer))
        return f'Orbit table in file {orbit_file}. Please pass that file or its label.'
    return load_orbit_table_in_img


def get_fn(data):
    target = data.filename
    return True, target
