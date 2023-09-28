def hst_hdu_name(name):
    """
    The image pointers all point at the same FITS HDU; each pointer is one band
    of the image.
    """
    if "EXTENSION" in name:
        return 1
    else:
        return 0 # The images and their FITS header.
