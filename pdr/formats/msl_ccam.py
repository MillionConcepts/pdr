from typing import TYPE_CHECKING, Callable
import warnings

if TYPE_CHECKING:
    from pdr import Data


def image_reply_table_loader(data: "Data") -> Callable:
    warnings.warn("MSL ChemCam IMAGE_REPLY binary tables are not supported due to a formatting error in label files.")
    return data.trivial
