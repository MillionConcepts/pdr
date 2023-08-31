def dawn_hdu_name(name):
    """filter out spurious HISTORY pointer"""
    if name in ("IMAGE", "HEADER"):
        return True, 0
    elif name == 'HISTORY':
        raise ValueError("Dawn FITS HISTORY extensions do not actually exist.")
    raise NotImplementedError("Unknown Dawn extension name")
