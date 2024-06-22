def rpx_img_hdu_start_byte(name, hdulist):
    """
    The multiple *_IMAGE pointers in these files all point at the same FITS
    HDU (each pointer illegally represents one band of the image).

    HITS
    * saturn_rpx
        * hst_raw_img
        * hst_raw_mask
        * hst_cal_img
        * hst_cal_mask
        * hst_eng_data
        * hst_eng_mask
    """
    if 'HEADER' in name:
        return 0
    return hdulist.fileinfo(0)['datLoc']
