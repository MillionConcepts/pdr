
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
        sample_type = 'MSB_UNSIGEND_INTEGER'
        return True, sample_types(sample_type, int(sample_bytes), for_numpy=True)
    return False, None
