from __future__ import annotations

from typing import (
    Optional,
    TYPE_CHECKING
)

from multidict import MultiDict

from pdr.parselabel.utils import dig_for_parent, levelpick
from pdr.pds4_datatypes import sample_types

if TYPE_CHECKING:
    import numpy as np

    from pdr.pdrtypes import (
        ImageProps, PDRLike
    )

# TODO: this is a slightly silly trick that may or may not remain necessary
#  after building full init workflow. make cleaner if it does remain so.


BSTORE_DICT = {
    ("Band", "Line", "Sample"): "BAND_SEQUENTIAL",
    ("Line", "Sample", "Band"): "SAMPLE_INTERLEAVED",
    ("Line", "Band", "Sample"): "LINE_INTERLEAVED",
}


def get_block(data: PDRLike, name: str) -> Optional[MultiDict]:
    return dig_for_parent(data.metadata, 'local_identifier', name)


# TODO: should probably use populated Data.file_mapping, will consider/build
#  after creating full init workflow
def get_fn(data: PDRLike, name: str) -> str:
    return levelpick(
        data.metadata,
        lambda k, v: k == 'local_identifier' and v == name,
        1,
        (dict, MultiDict)
    )['File']['file_name']


def generic_image_properties(block: MultiDict) -> ImageProps:
    """
    Construct a dict of image properties later used in the image-loading
    workflow.
    """
    elements = block["Element_Array"]
    sample_type = sample_types(elements["data_type"])
    import numpy as np  # TODO: lazy

    axes = {
        ax: dig_for_parent(block, "axis_name", ax)
        for ax in ("Line", "Sample", "Band")
    }
    props = {
        "BYTES_PER_PIXEL": np.dtype(sample_type).itemsize,
        "sample_type": sample_type,
        "nrows": axes['Line']["elements"],
        "ncols": axes['Sample']["elements"],
        "is_vax_real": False  # no VAX in PDS4
        # no axplanes etc. in PDS4
    } | {"rowpad": 0, "colpad": 0, "bandpad": 0, "linepad": 0}
    if axes['Band'] is not None:
        props["nbands"] = axes['Band']
        axorder = sorted(axes.keys(), key=lambda k: axes[k]['sequence_number'])
        props['band_storage_type'] = BSTORE_DICT[tuple(axorder)]
    else:
        props["nbands"] = 1
        props["band_storage_type"] = None
    return props


def get_start_byte(block: MultiDict):
    return block["offset"]
