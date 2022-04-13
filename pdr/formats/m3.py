from functools import partial
from typing import TYPE_CHECKING, Callable

from pdr.datatypes import sample_types

if TYPE_CHECKING:
    from pdr import Data


def m3_l0_image_properties(data):
    block, props = data.metablock_("L0_IMAGE"), {}
    props["BYTES_PER_PIXEL"] = block["SAMPLE_BITS"] / 8
    props["sample_type"] = sample_types(
        block["SAMPLE_TYPE"], props["BYTES_PER_PIXEL"],
    )
    props["nrows"] = block["LINES"]
    props["ncols"] = block["LINE_SAMPLES"]
    # M3 has a prefix, but it's not image-shaped
    props["prefix_bytes"] = block["LINE_PREFIX_BYTES"]
    props["prefix_cols"] = props["prefix_bytes"] / props["BYTES_PER_PIXEL"]
    props["BANDS"] = block["BANDS"]
    props["pixels"] = (
        props["nrows"]
        * (props["ncols"] + props["prefix_cols"])
        * props["BANDS"]
    )
    props["start_byte"] = 0
    props["band_storage_type"] = block["BAND_STORAGE_TYPE"]
    return props


# noinspection PyTypeChecker
def l0_image_loader(data: "Data") -> Callable:
    # Chandrayaan M3 L0 data  are in a deprecated ENVI format that uses
    # "line prefixes"
    return partial(
        data.read_image, special_properties=m3_l0_image_properties(data)
    )
