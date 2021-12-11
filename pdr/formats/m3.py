from functools import partial
from typing import TYPE_CHECKING, Callable

from pdr.datatypes import sample_types

if TYPE_CHECKING:
    from pdr import Data


def m3_l0_image_properties(data):
    props = {}
    props["BYTES_PER_PIXEL"] = int(
        data.LABEL["L0_FILE"]["L0_IMAGE"]["SAMPLE_BITS"] / 8
    )
    props["sample_type"] = sample_types(
        data.LABEL["L0_FILE"]["L0_IMAGE"]["SAMPLE_TYPE"],
        props["BYTES_PER_PIXEL"],
    )
    props["nrows"] = data.LABEL["L0_FILE"]["L0_IMAGE"]["LINES"]
    props["ncols"] = data.LABEL["L0_FILE"]["L0_IMAGE"]["LINE_SAMPLES"]
    props["prefix_bytes"] = int(
        data.LABEL["L0_FILE"]["L0_IMAGE"]["LINE_PREFIX_BYTES"]
    )
    props["prefix_cols"] = (
        props["prefix_bytes"] / props["BYTES_PER_PIXEL"]
    )  # M3 has a prefix, but it's not image-shaped
    props["BANDS"] = data.LABEL["L0_FILE"]["L0_IMAGE"]["BANDS"]
    props["pixels"] = (
        props["nrows"]
        * (props["ncols"] + props["prefix_cols"])
        * props["BANDS"]
    )
    props["start_byte"] = 0
    props["band_storage_type"] = data.LABEL["L0_FILE"]["L0_IMAGE"][
        "BAND_STORAGE_TYPE"
    ]
    return props


# noinspection PyTypeChecker
def l0_image_loader(data: "Data") -> Callable:
    # Chandrayaan M3 L0 data  are in a deprecated ENVI format that uses
    # "line prefixes"
    return partial(
        data.read_image,
        userasterio=False,
        special_properties=m3_l0_image_properties(data),
    )
