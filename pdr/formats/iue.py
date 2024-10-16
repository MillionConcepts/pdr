def get_special_block(data, name):
    """
    A subset of the IUE resampled SSI/LSI comet images have a typo in their 
    labels: the QUALITY_IMAGE pointer name does not match its OBJECT name.
    
    HITS
    * iue
        * comet_image
    """
    if data.metablock_(name) is not None:
        return False, None
    return True, data.metablock_("QUALITY_QUALITY_IMAGE")
