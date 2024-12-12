
def cube_envi_header_position(identifiers, block, target, name, start_byte, fn):
    """
    The ENVI_HEADER pointer's BYTES = "N/A"

    HITS
    * msx
        * cubes
    """
    from pdr.loaders.queries import table_position
    import os
    from pathlib import Path
    
    table_props = table_position(identifiers, block, target, name, start_byte)
    table_props["length"] = os.path.getsize(Path(fn))
    return table_props

