def hst_hdu_name(name):
    """
    The image pointers all point at the same FITS HDU; each pointer is one band
    of the image.

    HITS
    * saturn_rpx
        * hst_raw_img
        * hst_raw_mask
        * hst_cal_img
        * hst_cal_mask
        * hst_eng_data
        * hst_eng_mask
    """
    if "EXTENSION" in name:
        return 1
    else:
        return 0  # The images and their FITS header.
