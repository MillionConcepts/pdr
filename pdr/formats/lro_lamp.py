
def rdr_histogram_header_loader(data):
    # CAL_HISTOGRAM_DATA_HEADER pointer is an ASCII FITS header, but the 
    # 'histogram' keyword tries to send it to data.read_histogram
    return data.read_header

# TO-DO: this doesn't fully solve the problem; data.show() still throws errors
# that cause ix check to crash
def rdr_histogram_image_loader(data, pointer):
    # Products can have multiple unique pointers that are 
    # defined by a single image object (CAL_HISTOGRAM_DATA_IMAGE).
    return data.handle_fits_file
