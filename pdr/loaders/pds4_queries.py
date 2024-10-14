from __future__ import annotations

from operator import mul
from functools import reduce
from itertools import chain, product
from numbers import Number
from pathlib import Path
from types import MappingProxyType
from typing import (
    Any, Collection, Mapping, Optional, Sequence, TYPE_CHECKING, Union
)
import warnings

from multidict import MultiDict

from pdr.pds4_datatypes import sample_types
from pdr.formats import check_special_block, check_special_offset
from pdr.func import specialize
from pdr.loaders._helpers import (
    count_from_bottom_of_file,
    looks_like_ascii,
    quantity_start_byte,
    _check_delimiter_stream,
)
from pdr.loaders.handlers import add_bit_column_info
from pdr.parselabel.pds3 import pointerize, read_pvl
from pdr.utils import append_repeated_object, check_cases, find_repository_root

if TYPE_CHECKING:
    from pdr.loaders.astrowrap import fits
    import numpy as np
    import pandas as pd

    from pdr.pdrtypes import (
        BandStorageType, DataIdentifiers, ImageProps, PDRLike, PhysicalTarget
    )

from dustgoggles.structures import dig_for_value


def dig_for_parent(
    mapping, key, value, mtypes=(dict, MultiDict)
):
    return dig_for_value(
        mapping,
        None,
        base_pred=lambda _, v: isinstance(v, mtypes) and v.get(key) == value,
        match='value',
        mtypes=mtypes
    )

BSTORE_DICT = {
    ("Band", "Line", "Sample"): "BAND_SEQUENTIAL",
    ("Line", "Sample", "Band"): "SAMPLE_INTERLEAVED",
    ("Line", "Band", "Sample"): "LINE_INTERLEAVED",
}


def get_block(data: PDRLike, name: str) -> Optional[MultiDict]:
    return dig_for_parent(data.metadata, 'local_identifier', name)


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
    } | {"rowpad": 0, "colpad": 0, "bandpad": 0}  # no axplanes etc. in PDS4
    if axes['Band'] is not None:
        props["nbands"] = axes['Band']
        axorder = sorted(axes.keys(), key=lambda k: axes[k]['sequence_number'])
        props['band_storage_type'] = BSTORE_DICT[tuple(axorder)]
    else:
        props["nbands"] = 1
        props["band_storage_type"] = None
    props["pixels"] = props["nrows"] * props["ncols"] * props["nbands"]
    return props


def get_target(block: MultiDict):
    return block["offset"]
