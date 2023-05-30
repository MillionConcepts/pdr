import warnings

from pdr.loaders.utility import trivial


def image_reply_table_loader():
    warnings.warn(
        "MSL ChemCam IMAGE_REPLY binary tables are not supported "
        "due to a formatting error in label files."
    )
    return trivial
