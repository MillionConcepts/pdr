from functools import partial
from typing import Callable


def image_loader(data, _) -> Callable:
    """
    our built-in array handling is a little better than rasterio's for these:
    use it by default.
    """
    return partial(data.read_image, userasterio=False)