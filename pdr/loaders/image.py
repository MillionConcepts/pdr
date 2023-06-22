import warnings
from itertools import product

import numpy as np

from pdr.loaders.queries import get_image_properties
from pdr.np_utils import np_from_buffered_io
from pdr.utils import decompress


def read_image(name, gen_props, fn, start_byte):
    """
    Read an image object from this product and return it as a numpy array.
    """
    # TODO: Check for and apply BIT_MASK.
    props = get_image_properties(gen_props)
    f = decompress(fn)  # seamlessly deal with compression
    f.seek(start_byte)
    try:
        # Make sure that single-band images are 2-dim arrays.
        if props["nbands"] == 1:
            image, axplanes, pre, suf = process_single_band_image(f, props)
        else:
            image, axplanes, pre, suf = process_multiband_image(f, props)
    except Exception as ex:
        raise ex
    finally:
        f.close()
    if "PREFIX" in name:
        return pre
    elif "SUFFIX" in name:
        return suf
    return image


def make_format_specifications(props):
    endian, ctype = props["sample_type"][0], props["sample_type"][-1]
    struct_fmt = f"{endian}{props['pixels']}{ctype}"
    np_type = props["sample_type"][1:]
    dtype = np.dtype(f"{endian}{np_type}")
    return struct_fmt, dtype


def extract_single_band_linefix(image, props):
    if props["linepad"] == 0:
        return image, None, None
    prefix, suffix = None, None
    image = image.reshape(props["nrows"], props["ncols"] + props["linepad"])
    if props.get("line_suffix_pix", 0) > 0:
        suffix = image[:, -props["line_suffix_pix"] :]
        image = image[:, : -props["line_suffix_pix"]]
    if props.get("line_prefix_pix", 0) > 0:
        prefix = image[:, : props["line_prefix_pix"]]
        image = image[:, props["line_prefix_pix"] :]
    return image, prefix, suffix


def process_single_band_image(f, props):
    _, numpy_dtype = make_format_specifications(props)
    # TODO: added this 'count' parameter to handle a case in which the image
    #  was not the last object in the file. We might want to add it to
    #  the multiband loaders too.
    image = np_from_buffered_io(f, dtype=numpy_dtype, count=props["pixels"])
    image, prefix, suffix = extract_single_band_linefix(image, props)
    image = image.reshape(
        (props["nrows"] + props["rowpad"], props["ncols"] + props["colpad"])
    )
    image, axplanes = extract_axplanes(image, props)
    return make_c_contiguous(image), axplanes, prefix, suffix


def extract_bil_linefix(image, props):
    if props["linepad"] == 0:
        return image, None, None
    prefix, suffix = None, None
    image = image.reshape(props["nrows"], int(image.size / props["nrows"]))
    if props.get("line_suffix_pix") is not None:
        suffix = image[:, -props["line_suffix_pix"] :]
        image = image[:, : -props["line_suffix_pix"]]
    if props.get("line_prefix_pix") is not None:
        prefix = image[:, : props["line_prefix_pix"]]
        image = image[:, props["line_prefix_pix"] :]
    return image, prefix, suffix


def process_multiband_image(f, props):
    bst = props["band_storage_type"]
    if bst not in ("BAND_SEQUENTIAL", "LINE_INTERLEAVED", "SAMPLE_INTERLEAVED"):
        warnings.warn(
            f"Unsupported BAND_STORAGE_TYPE={bst}. Guessing BAND_SEQUENTIAL."
        )
        bst = "BAND_SEQUENTIAL"
    _, numpy_dtype = make_format_specifications(props)
    image = np_from_buffered_io(f, numpy_dtype, count=props["pixels"])
    bands, lines, samples = (
        props["nbands"] + props["bandpad"],
        props["nrows"] + props["rowpad"],
        props["ncols"] + props["colpad"],
    )
    prefix, suffix = None, None
    if bst == "BAND_SEQUENTIAL":
        image = image.reshape(bands, lines, samples)
    elif bst == "SAMPLE_INTERLEAVED":
        image = image.reshape(lines, samples, bands)
        image = np.moveaxis(image, 2, 0)
    elif bst == "LINE_INTERLEAVED":
        image, prefix, suffix = extract_bil_linefix(image, props)
        image = image.reshape(lines, bands, samples)
        image = np.moveaxis(image, 0, 1)
    image, axplanes = extract_axplanes(image, props)
    return make_c_contiguous(image), axplanes, prefix, suffix


def extract_axplanes(image, props):
    """extract ISIS-style side/bottom/backplanes from an array"""
    axplanes = {}
    for side, ax in product(("prefix", "suffix"), ("row", "col", "band")):
        if (count := props.get(f"{side}_{ax}s")) is None:
            continue
        axn, axname = {
            "band": (0, "BAND"),
            "row": (1, "LINE"),
            "col": (2, "SAMPLE"),
        }[ax]
        axn = axn - 1 if len(image.shape) == 2 else axn
        aslice, pslice = [], []
        for i in range(len(image.shape)):
            if i != axn:
                aslice.append(slice(None, None, None))
                pslice.append(slice(None, None, None))
            elif side == "prefix":
                aslice.append(slice(count, None))
                pslice.append(slice(None, count))
            else:
                aslice.append(slice(None, -count))
                pslice.append(slice(-count, None))
        axplanes[f"{side}_{ax}s"] = image[tuple(pslice)]
        image = image[tuple(aslice)]
    return image, axplanes


def make_c_contiguous(image: np.ndarray) -> np.ndarray:
    if image.flags["C_CONTIGUOUS"] is False:
        return np.ascontiguousarray(image)
    return image
