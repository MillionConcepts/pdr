
def lamp_rdr_histogram_header_loader(data):
    # CAL_HISTOGRAM_DATA_HEADER pointer is an ASCII FITS header, but the 
    # 'histogram' keyword tries to send it to data.read_histogram
    return data.read_header

# TO-DO: this doesn't fully solve the problem; data.show() still throws errors
# that cause ix check to crash
def lamp_rdr_histogram_image_loader(data, pointer):
    # Products can have multiple unique pointers that are 
    # defined by a single image object (CAL_HISTOGRAM_DATA_IMAGE).
    return data.handle_fits_file

def crater_bit_col_sample_type(sample_type, sample_bytes, for_numpy):
    from pdr.datatypes import sample_types
    if 'BIT_STRING' == sample_type:
        sample_type = 'MSB_BIT_STRING'
        return True, sample_types(sample_type, int(sample_bytes), for_numpy=True)
    if 'N/A' in sample_type:
        sample_type = 'MSB_UNSIGNED_INTEGER'
        return True, sample_types(sample_type, int(sample_bytes), for_numpy=True)
    return False, None

def rss_get_position(start, length, as_rows, data, object_name):
    # The RSS WEA products' WEAREC_TABLE undercounts ROW_BYTES by 1
    n_records = data.metaget_(object_name)['ROWS']
    record_bytes = data.metaget_(object_name)['ROW_BYTES']+1
    length = n_records * record_bytes
    return True, start, length, as_rows
