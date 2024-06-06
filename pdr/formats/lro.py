from pdr.loaders.queries import table_position


# def lamp_rdr_histogram_header_loader(data):
#     # CAL_HISTOGRAM_DATA_HEADER pointer is an ASCII FITS header, but the
#     # 'histogram' keyword tries to send it to data.read_histogram
#     return data.read_header


# TODO: this doesn't fully solve the problem; data.show() still throws errors
# that cause ix check to crash (refers to original special case in /develop
# -- this is a rewrite)
def lamp_rdr_histogram_image_loader(data):
    """Products can have multiple unique pointers that are
    defined by a single image object (CAL_HISTOGRAM_DATA_IMAGE)."""
    object_name = "CAL_HISTOGRAM_DATA_IMAGE"
    block = data.metablock_(object_name)
    return block


def get_crater_offset():
    """
    lro crater edr products have a header table with 64 bytes per row, the
    second table start byte is given in rows (also the wrong row) but had a
    different number of row bytes

    HITS
    * lro_crater
        * edr_sec
        * edr_hk
    """
    return True, 64


def crater_bit_col_sample_type(base_samp_info):
    """
    HITS
    * lro_crater
        * edr_sec
        * edr_hk
    """
    from pdr.datatypes import sample_types

    sample_type = base_samp_info["SAMPLE_TYPE"]
    sample_bytes = base_samp_info["BYTES_PER_PIXEL"]
    if "BIT_STRING" == sample_type:
        sample_type = "MSB_BIT_STRING"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    if "N/A" in sample_type:
        sample_type = "MSB_UNSIGNED_INTEGER"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    return False, None


def rss_get_position(identifiers, block, target, name, start_byte):
    """
    The RSS WEA products' WEAREC_TABLE undercounts ROW_BYTES by 1

    HITS
    * lro_rss
        * wea
    """
    table_props = table_position(identifiers, block, target, name, start_byte)
    n_records = block["ROWS"]
    record_bytes = block["ROW_BYTES"] + 1
    length = n_records * record_bytes
    table_props["length"] = length
    return True, table_props


def mini_rf_image_loader(data, name):
    """
    one of the mosaic labels has the wrong values for lines/line_samples

    HITS
    * lro_mini_rf
        * mosaic
    """
    block = data.metablock_(name)
    block["LINES"] = 5760
    block["LINE_SAMPLES"] = 11520
    return block

def mini_rf_spreadsheet_loader(filename, fmtdef_dt):
    """
    Mini-RF housekeeping CSVs have variable-width columns but the labels treat 
    them as fixed-width. 

    HITS
    * lro_mini_rf
        * housekeeping
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    # The names argument is used here to explicitly set the number of columns
    # to 3. Otherwise the first row (which only has 1 column) confuses read_csv
    table = pd.read_csv(filename, header=None, sep=",",
                        names = ("POINT_NAME", "VALUE", "UNITS"))
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table
