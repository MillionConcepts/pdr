import os
import re
import warnings
from functools import partial, reduce
from itertools import product
from operator import contains, mul
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Optional, Sequence

from multidict import MultiDict

from pdr import formats
from pdr.parselabel.pds3 import pointerize
from pdr.utils import check_cases
from pdr.datatypes import sample_types


if TYPE_CHECKING:
    from pdr import Data

LABEL_EXTENSIONS = (".xml", ".lbl")
IMAGE_EXTENSIONS = (".img", ".rgb")
TABLE_EXTENSIONS = (".tab", ".csv")
TEXT_EXTENSIONS = (".txt", ".md")
FITS_EXTENSIONS = (".fits", ".fit")
TIFF_EXTENSIONS = (".tif", ".tiff")
JP2_EXTENSIONS = (".jp2", ".jpf", ".jpc", ".jpx")

ID_FIELDS = (
    "INSTRUMENT_ID",
    "INSTRUMENT_NAME",
    "SPACECRAFT_NAME",
    "PRODUCT_TYPE",
    "DATA_SET_NAME",
    "DATA_SET_ID",
    "STANDARD_DATA_PRODUCT_ID"
)


def looks_like_this_kind_of_file(filename: str, kind_extensions) -> bool:
    is_this_kind_of_extension = partial(contains, kind_extensions)
    return any(
        map(is_this_kind_of_extension, Path(filename.lower()).suffixes)
    )


def file_extension_to_loader(filename: str, data: "Data") -> Callable:
    """
    attempt to select the correct method of pdr.Data for objects only
    specified by a PDS3 FILE_NAME pointer (or by filename otherwise).
    """
    if looks_like_this_kind_of_file(filename, FITS_EXTENSIONS):
        return data.handle_fits_file
    if looks_like_this_kind_of_file(filename, TIFF_EXTENSIONS):
        return data.handle_compressed_image
    if looks_like_this_kind_of_file(filename, IMAGE_EXTENSIONS):
        return data.read_image
    if looks_like_this_kind_of_file(filename, TEXT_EXTENSIONS):
        return data.read_text
    if looks_like_this_kind_of_file(filename, TABLE_EXTENSIONS):
        return data.read_table
    if looks_like_this_kind_of_file(filename, JP2_EXTENSIONS):
        return data.handle_compressed_image
    return data.tbd


def check_special_offset(pointer, data) -> tuple[bool, Optional[int]]:
    # these incorrectly specify object length rather than
    # object offset in the ^HISTOGRAM pointer target
    if data.metaget_("INSTRUMENT_ID", "") == "CHEMIN":
        return formats.msl_cmn.get_offset(data, pointer)
    if (
        data.metaget_("DATA_SET_ID", "") == "CLEM1-L-RSS-5-BSR-V1.0"
        and pointer in ("HEADER_TABLE", "DATA_TABLE")
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_offset(data, pointer)
    # if (
    #     data.metaget_("DATA_SET_ID", "").startswith("ODY-M-THM-5-VISGEO")
    #     and (pointer == "QUBE")
    # ):
    #     # incorrectly specified record length etc.
    #     return formats.themis.get_visgeo_qube_offset(data)
    #
    if data.metaget_("INSTRUMENT_ID") == "THEMIS" and pointer == "QUBE":
        return formats.themis.get_qube_offset(data)
    if (
            data.metaget_("INSTRUMENT_NAME", "") == "DESCENT IMAGER SPECTRAL RADIOMETER"
            and (data.metaget_("PRODUCT_TYPE", "") == "RDR")
            or any(
                sub in data.metaget_("FILE_NAME", "") for sub in
                ["STRIP", "VISIBL", "IMAGE", "IR_", "TIME", "SUN", "SOLAR"]
            )
    ):
        return formats.cassini.get_offset(data, pointer)


    return False, None


def check_special_structure(pointer, data):
    if (data.metaget_("DATA_SET_ID", "") == "CLEM1-L-RSS-5-BSR-V1.0"
            and pointer == "DATA_TABLE"):
        # sequence wrapped as string for object names
        return formats.clementine.get_structure(pointer, data)
    if (data.metaget_("INSTRUMENT_HOST_NAME", "") == "MARS GLOBAL SURVEYOR"
            and data.metaget_("INSTRUMENT_ID", "") == "RSS"
            and data.metaget_("PRODUCT_TYPE", "") == "ODF" and pointer == "ODF3B_TABLE"):
        return formats.mgs.get_structure(pointer, data)
    if (data.metaget_("INSTRUMENT_HOST_NAME", "") == "CASSINI ORBITER"
            and data.metaget_("INSTRUMENT_ID", "") == "RPWS"
            and pointer == "TIME_SERIES"):
        return formats.cassini.get_structure(pointer, data)
    if (data.metaget_("INSTRUMENT_HOST_NAME", "") == "HUYGENS PROBE"
            and "HUY_DTWG_ENTRY_AERO" in data.filename):
        return formats.cassini.get_structure(pointer, data)
    return False, None, None


def check_special_position(start, length, as_rows, data, object_name):
    if (data.metaget_("INSTRUMENT_ID", "") == "MARSIS" and
            " TEC " in data.metaget_("DATA_SET_NAME", "")):
        return formats.mex_marsis.get_position(start, length, as_rows, data)
    if (
            data.metaget_("INSTRUMENT_HOST_NAME", "") == "HUYGENS PROBE"
            and any(
                sub in data.metaget_("FILE_NAME", "")
                for sub in ["DARK", "STRIP", "VIS_EX", "SUN", "VISIBL", "TIME", "SOLAR", "IMAGE"]
            )
            or (
                data.metaget_("INSTRUMENT_NAME", "") == "DESCENT IMAGER SPECTRAL RADIOMETER"
                and data.metaget_("PRODUCT_TYPE", "") == "RDR")
            ):
        return formats.cassini.get_position(start, length, as_rows, data, object_name)
    if (data.metaget_("DATA_SET_ID", "") == "LRO-L-RSS-1-TRACKING-V1.0" and
            object_name == "WEAREC_TABLE"):
        return formats.lro.rss_get_position(start, length, as_rows, data, object_name)
    return False, None, None, None


def check_special_sample_type(
    data: "Data",
    sample_type: str,
    sample_bytes: int,
    for_numpy: bool
) -> tuple[bool, Optional[str]]:
    if (
        data.metaget_("INSTRUMENT_ID") == "MARSIS"
        and data.metaget_("PRODUCT_TYPE") == "EDR"
    ):
        return formats.mex_marsis.get_sample_type(
            sample_type, sample_bytes, for_numpy
        )
    if (
        data.metaget_("DATA_SET_ID") == "JNO-J-JIRAM-3-RDR-V1.0"
        and data.metaget("PRODUCT_TYPE") == "RDR"
    ):
        return formats.juno.jiram_rdr_sample_type()
    if (data.metaget_("DATA_SET_ID") == "MGN-V-RDRS-5-GVDR-V1.0"
        and "GVANF" in data.metaget("PRODUCT_ID")
    ):
        return formats.mgn.gvanf_sample_type(sample_type, sample_bytes, for_numpy)
    if data.metaget_("DATA_SET_ID") == "LRO-L-CRAT-2-EDR-RAWDATA-V1.0":
        return formats.lro.crater_bit_col_sample_type(sample_type, sample_bytes, for_numpy)
    return False, None


def check_special_bit_column_case(data):
    instrument = data.metaget_("INSTRUMENT_NAME")
    if instrument in (
        "ALPHA PARTICLE X-RAYSPECTROMETER",
        "JOVIAN AURORAL PLASMA DISTRIBUTIONS EXPERIMENT",
        "CHEMISTRY AND MINERALOGY INSTRUMENT",
        "MARS ADVANCED RADAR FOR SUBSURFACE ANDIONOSPHERE SOUNDING"
    ):
        return True, "MSB_BIT_STRING"
    return False, None


def check_special_bit_start_case(
    data, list_of_pvl_objects_for_bit_columns, start_bit_list
):
    if data.metaget_("INSTRUMENT_NAME", "") in "JOVIAN INFRARED AURORAL MAPPER":
        return formats.juno.bit_start_find_and_fix(
            list_of_pvl_objects_for_bit_columns, start_bit_list
        )
    return False, None


def check_special_case(pointer, data) -> tuple[bool, Optional[Callable]]:
    if pointer == 'SHADR_HEADER_TABLE':
        return True, formats.messenger.shadr_header_table_loader(data)
    ids = {field: str(data.metaget_(field, "")) for field in ID_FIELDS}
    if (
        ids["INSTRUMENT_ID"] == "LROC"
        and ids["PRODUCT_TYPE"] == "EDR"
        and pointer == "IMAGE"
    ):
        # unsigned integers not specified as such
        return True, formats.lroc.lroc_edr_image_loader(data, pointer)
    if (
        ids["INSTRUMENT_ID"] == "LAMP"
        and ids["PRODUCT_TYPE"] == "RDR"
        and "HEADER" in pointer and "HISTOGRAM" in pointer
    ):
        # FITS headers with 'histogram' in pointer name
        return True, formats.lro.lamp_rdr_histogram_header_loader(data)
    if (
        ids["INSTRUMENT_ID"] == "LAMP"
        and ids["PRODUCT_TYPE"] == "RDR"
        and "IMAGE" in pointer and "HISTOGRAM" in pointer
    ):
        # multiple image objects are defined by one non-unique image object
        return True, formats.lro.lamp_rdr_histogram_image_loader(data, pointer)
    if (
        ids["DATA_SET_ID"] == "LRO-L-MRFLRO-5-GLOBAL-MOSAIC-V1.0"
        and "GLOBAL_S4_32PPD" in data.metaget_("PRODUCT_ID")
        and pointer == "IMAGE"
    ):
        # typo in one of the labels
        return True, formats.lro.mini_rf_image_loader(data, pointer)
    if (
        ids["SPACECRAFT_NAME"] == "MAGELLAN" 
        and pointer == "TABLE"
        and data.metaget_("NOTE", "").startswith("Geometry")
    ):
        return True, formats.mgn.geom_table_loader(data, pointer)
    if (
        ids["INSTRUMENT_NAME"] == "ROSETTA PLASMA CONSORTIUM - MUTUAL IMPEDANCE PROBE"
        and "SPECTRUM_TABLE" in pointer
    ):
        return True, formats.rosetta.rosetta_table_loader(data, pointer)
    if ids["INSTRUMENT_ID"] == "APXS" and "TABLE" in pointer:
        # just an ambiguous name: best to specify it)
        return True, formats.msl_apxs.table_loader(data, pointer)
    if (
        ids["INSTRUMENT_ID"] == "CHEMIN"
        and (("HEADER" in pointer) or ("SPREADSHEET" in pointer))
    ):
        # mangled object names + positions
        return True, formats.msl_cmn.table_loader(data, pointer)
    # difficult table formats that are handled well by astropy.io.ascii
    if (
        ids["INSTRUMENT_NAME"] == "TRIAXIAL FLUXGATE MAGNETOMETER"
        and pointer == "TABLE"
    ):
        return True, formats.galileo.galileo_table_loader(data)
    if (
        ids["INSTRUMENT_NAME"] == "CHEMISTRY CAMERA REMOTE MICRO-IMAGER"
        and pointer == "IMAGE_REPLY_TABLE"
    ):
        return True, formats.msl_ccam.image_reply_table_loader(data)
    if (
        ids["DATA_SET_ID"].startswith("JNO-E/J/SS")
        and "BSTFULL" in ids["DATA_SET_ID"]
        and "FREQ_OFFSET_TABLE" in data.keys()
        and pointer in ("FREQ_OFFSET_TABLE", "DATA_TABLE")
    ):
        return True, formats.juno.waves_burst_with_offset_loader(data)
    if (
        ids["DATA_SET_ID"] in (
            "CO-S-MIMI-4-CHEMS-CALIB-V1.0",
            "CO-S-MIMI-4-LEMMS-CALIB-V1.0",
            "CO-S-MIMI-4-INCA-CALIB-V1.0",
            "CO-E/J/S/SW-MIMI-2-LEMMS-UNCALIB-V1.0"
        )
        and pointer == "SPREADSHEET"
    ):
        return True, formats.cassini.ppi_table_loader(
            data, pointer, ids["DATA_SET_ID"]
        )
    if (
        ids["INSTRUMENT_ID"] == "DLRE"
        and ids["PRODUCT_TYPE"] in ("GCP", "PCP", "PRP")
        and pointer == "TABLE"
    ):
        return True, formats.diviner.diviner_l4_table_loader(data, pointer)
    if (
        ids["DATA_SET_ID"].startswith("ODY-M-THM-5")
        and (pointer in ("HEADER", "HISTORY"))
    ):
        return True, formats.themis.trivial_themis_geo_loader(data, pointer)
    if re.match(r"CO-(CAL-ISS|[S/EVJ-]+ISSNA/ISSWA-2)", ids["DATA_SET_ID"]):
        if pointer in ("TELEMETRY_TABLE", "LINE_PREFIX_TABLE"):
            return True, formats.cassini.trivial_loader(pointer, data)
    if pointer == "XDR_DOCUMENT":
        return True, formats.cassini.xdr_loader(pointer, data)
    if (data.metaget_("INSTRUMENT_HOST_NAME", "") == "HUYGENS PROBE"
            and "HASI" in data.metaget_("FILE_NAME", "") and "PWA" not in
            data.metaget_("FILE_NAME", "") and pointer == "TABLE"):
        return True, formats.cassini.hasi_loader(pointer, data)
    if (
        ids["DATA_SET_ID"] == "CO-SSA-RADAR-3-ABDR-SUMMARY-V1.0" 
        and pointer == "SPREADSHEET"
    ):
        return True, formats.cassini.radar_asum_loader(pointer, data)
    if (data.metaget_("SPACECRAFT_NAME", "") == "MAGELLAN" and (data.filename.endswith(
            '.img') or data.filename.endswith('.ibg')) and pointer == "TABLE"):
        return True, formats.mgn.orbit_table_in_img_loader(data, pointer)
    if ids["DATA_SET_ID"].startswith("MGN-V-RSS-5-OCC-PROF") and pointer == "TABLE":
        return True, formats.mgn.occultation_loader(data, pointer)
    return False, None


def is_trivial(pointer) -> bool:
    # TIFF tags / headers should always be parsed by the TIFF parser itself
    if (
        ("TIFF" in pointer)
        and ("IMAGE" not in pointer)
        and ("DOCUMENT" not in pointer)
    ):
        return True
    # we don't present STRUCTURES separately from their tables
    if "STRUCTURE" in pointer:
        return True
    return False


# noinspection PyTypeChecker
def pointer_to_loader(pointer: str, data: "Data") -> Callable:
    """
    attempt to select an appropriate loading function based on a PDS3 pointer
    name. checks for special cases and then falls back to generic loading
    methods of pdr.Data.
    """
    if is_trivial(pointer) is True:
        return data.trivial
    is_special, loader = check_special_case(pointer, data)
    if is_special is True:
        return loader
    if pointer == "LABEL":
        return data.read_label
    if "TEXT" in pointer or "PDF" in pointer or "MAP_PROJECTION_CATALOG" in pointer:
        return data.read_text
    if "DESC" in pointer:  # probably points to a reference file
        return data.read_text
    if "ARRAY" in pointer:
        return data.read_array
    if "LINE_PREFIX_TABLE" in pointer:
        return data.tbd
    if (
        ("TABLE" in pointer)
        or ("SPREADSHEET" in pointer)
        or ("CONTAINER" in pointer)
        or ("TIME_SERIES" in pointer)
        or ("SERIES" in pointer)
        or ("SPECTRUM" in pointer)
    ):
        return data.read_table
    if "HISTOGRAM" in pointer:
        return data.read_histogram
    if "HEADER" in pointer:
        return data.read_header
    # I have moved this below "table" due to the presence of a number of
    # binary tables named things like "Image Time Table". If there are pictures
    # of tables, we will need to do something more sophisticated.
    if ("IMAGE" in pointer) or ("QUB" in pointer):
        # TODO: sloppy pt. 1. this may be problematic for
        #  products with a 'secondary' fits file, etc.
        if image_lib_dispatch(pointer, data) is not None:
            return image_lib_dispatch(pointer, data)
        return data.read_image
    if "FILE_NAME" in pointer:
        return file_extension_to_loader(pointer, data)
    # TODO: sloppy pt. 2
    if image_lib_dispatch(pointer, data) is not None:
        return image_lib_dispatch(pointer, data)
    return data.tbd


def image_lib_dispatch(pointer: str, data: "Data") -> Optional[Callable]:
    """
    check file extensions to see if we want to toss a file to an external
    library rather than using our internal raster handling. current cases are:
    pillow for tiff, astropy for fits
    """
    object_filename = data._target_path(pointer)
    if looks_like_this_kind_of_file(object_filename, FITS_EXTENSIONS):
        return data.handle_fits_file
    if looks_like_this_kind_of_file(object_filename, TIFF_EXTENSIONS):
        return data.handle_compressed_image
    if looks_like_this_kind_of_file(object_filename, JP2_EXTENSIONS):
        return data.handle_compressed_image
    return None


def check_special_qube_props(object_name, block, data):
    if (
            data.metaget_("INSTRUMENT_HOST_NAME", "") == "CASSINI_ORBITER"
            and object_name == "QUBE"
    ):
        return formats.cassini.get_special_qube_props(block)
    return False, None, None


def qube_image_properties(block: MultiDict) -> dict:
    props = {}
    use_block = block if "CORE" not in block.keys() else block["CORE"]
    props["BYTES_PER_PIXEL"] = int(use_block["CORE_ITEM_BYTES"])  # / 8)
    props["sample_type"] = sample_types(
        use_block["CORE_ITEM_TYPE"], props["BYTES_PER_PIXEL"]
    )
    if "AXIS_NAME" in set(block.keys()).union(use_block.keys()):
        # TODO: if we end up handling this at higher level in the PVL parser,
        #  remove this splitting stuff
        axnames = block.get('AXIS_NAME')
        if axnames is None:
            axnames = use_block.get('AXIS_NAME')
        props['axnames'] = tuple(re.sub(r'[)( ]', '', axnames).split(","))
        ax_map = {'LINE': 'nrows', 'SAMPLE': 'ncols', 'BAND': 'nbands'}
        for ax, count in zip(props['axnames'], use_block['CORE_ITEMS']):
            props[ax_map[ax]] = count
    else:
        props["nrows"] = use_block["CORE_ITEMS"][2]
        props["ncols"] = use_block["CORE_ITEMS"][0]
        props["nbands"] = use_block["CORE_ITEMS"][1]
    props['band_storage_type'] = use_block.get("BAND_STORAGE_TYPE")
    if props['band_storage_type'] is None:
        if props.get('axnames') is not None:
            # noinspection PyTypeChecker
            # writing keys in last-axis-fastest for clarity. however,
            # ISIS always (?) uses first-axis-fastest, hence `reversed` below.
            props['band_storage_type'] = {
                ('BAND', 'LINE', 'SAMPLE'): 'BAND_SEQUENTIAL',
                ('LINE', 'SAMPLE', 'BAND'): 'SAMPLE_INTERLEAVED',
                ('LINE', 'BAND', 'SAMPLE'): 'LINE_INTERLEAVED'
            }[tuple(reversed(props['axnames']))]
        else:
            props['band_storage_type'] = 'ISIS2_QUBE'
    props |= extract_axplane_metadata(use_block, props)
    # TODO: unclear whether lower-level linefixes ever appear on qubes
    return props | extract_linefix_metadata(use_block, props)


def extract_axplane_metadata(block: MultiDict, props: dict) -> dict:
    """extract metadata for ISIS-style side/back/bottomplanes"""
    # shorthand relating side/backplane "direction" to row/column axes.
    rowcol = {'SAMPLE': "col", "LINE": "row", "BAND": "band"}
    axplane_metadata = {'rowpad': 0, 'colpad': 0, 'bandpad': 0}
    for ax, side in product(("BAND", "LINE", "SAMPLE"), ("PREFIX", "SUFFIX")):
        if (itembytes := block.get(f"{ax}_{side}_ITEM_BYTES")) is None:
            continue
        if (itemcount := block.get(f"{side}_ITEMS")) is None:
            raise ValueError(
                f"Specified {ax} {side} item bytes with no specified "
                f"number of items; can't interpret."
            )
        if props.get('axnames') is None:
            raise ValueError(
                f"Specified {ax} {side} items with no specified axis "
                f"order; can't interpret."
            )
        # TODO: handle variable-length axplanes
        fixbytes = itemcount[props['axnames'].index(ax)] * itembytes
        fix_pix = fixbytes / props['BYTES_PER_PIXEL']
        if int(fix_pix) != fix_pix:
            raise NotImplementedError(
                "Pre/suffix itemsize < array itemsize is not supported."
            )
        axplane_metadata[f"{side.lower()}_{rowcol[ax]}s"] = int(fix_pix)
        axplane_metadata[f"{rowcol[ax]}pad"] += int(fix_pix)
    return axplane_metadata


def extract_linefix_metadata(block: MultiDict, props: dict) -> dict:
    """extract metadata for line prefix/suffix 'tables'"""
    linefix_metadata = {"linepad": 0}
    for side in ("PREFIX", "SUFFIX"):
        if (fixbytes := block.get(f"LINE_{side}_BYTES")) in (0, None):
            continue
        fix_pix = fixbytes / props['BYTES_PER_PIXEL']
        if fix_pix != int(fix_pix):
            raise NotImplementedError(
                "Line pre/suffixes not aligned with array element size are "
                "not supported."
            )
        linefix_metadata[f"line_{side.lower()}_pix"] = int(fix_pix)
        linefix_metadata["linepad"] += int(fix_pix)
    return linefix_metadata


def gt0f(seq):
    return tuple(filter(lambda x: x > 0, seq))


def generic_image_properties(object_name, block, data) -> dict:
    if "QUBE" in object_name:  # ISIS2 QUBE format
        is_special, special_props, special_block = check_special_qube_props(
            object_name, block, data)
        if is_special:
            props = special_props
            props |= extract_axplane_metadata(special_block, props)
            props |= extract_linefix_metadata(special_block, props)
        else:
            props = qube_image_properties(block)
    else:
        props = {"BYTES_PER_PIXEL": int(block["SAMPLE_BITS"] / 8)}
        is_special, special_type = check_special_sample_type(
            data, block["SAMPLE_TYPE"], props["BYTES_PER_PIXEL"], True
        )
        if is_special:
            props["sample_type"] = special_type
        else:
            props["sample_type"] = sample_types(
                block["SAMPLE_TYPE"], props["BYTES_PER_PIXEL"], for_numpy=True
            )
        props["nrows"] = block["LINES"]
        props["ncols"] = block["LINE_SAMPLES"]
        if "BANDS" in block:
            props["nbands"] = block["BANDS"]
            props["band_storage_type"] = block.get("BAND_STORAGE_TYPE", None)
            # TODO: assess whether this is always ok
            if props["band_storage_type"] is None and props["nbands"] > 1:
                raise ValueError(
                    "Cannot read 3D image with no specified band storage type."
                )
        else:
            props["nbands"] = 1
            props["band_storage_type"] = None
        props |= extract_axplane_metadata(block, props)
        props |= extract_linefix_metadata(block, props)
    if (
        (props['linepad'] > 0)
        and ((props['rowpad'] + props['colpad'] + props['bandpad']) > 0)
    ):
        raise NotImplementedError(
            "Objects that contain both 'conventional' line pre/suffixes and "
            "ISIS-style side/back/bottomplanes are not supported."
        )
    if len(gt0f((props['rowpad'], props['colpad'], props['bandpad']))) > 1:
        raise NotImplementedError(
            "ISIS-style axplanes along multiple axes are not supported."
        )
    if (
        (props['linepad'] > 0)
        and props['band_storage_type'] not in (None, "LINE_INTERLEAVED")
    ):
        raise NotImplementedError(
            "'Conventional' line pre/suffixes are not supported for non-BIL "
            "multiband images."
        )
    props["pixels"] = (
        (props["nrows"] + props['rowpad'])
        * (props["ncols"] + props['colpad'] + props['linepad'])
        * (props["nbands"] + props['bandpad'])
    )
    props["start_byte"] = data.data_start_byte(object_name)
    return props


def special_image_constants(data):
    consts = {}
    if data.metaget_("INSTRUMENT_ID") == "CRISM":
        consts["NULL"] = 65535
    return consts


def check_special_fn(data, object_name) -> tuple[bool, Optional[str]]:
    """
    special-case handling for labels with nonstandard filename specifications
    """
    dsi = data.metaget_("DATA_SET_ID", "")
    if (
        (dsi == "CLEM1-L-RSS-5-BSR-V1.0")
        and (object_name in ("HEADER_TABLE", "DATA_TABLE"))
    ):
        # sequence wrapped as string for object names
        return formats.clementine.get_fn(data, object_name)
    if (
        data.metaget_("SPACECRAFT_NAME", "") == "MAGELLAN"
        and (data.filename.endswith('.img') or data.filename.endswith('ibg'))
        and object_name == "TABLE"
    ):
        return formats.mgn.get_fn(data)
    # filenames are frequently misspecified
    if str(dsi).startswith("CO-D-CDA") and (object_name == "TABLE"):
        return formats.cassini.cda_table_filename(data)
    # THEMIS labels don't always mention when a file is stored gzipped
    if data.metaget("INSTRUMENT_ID") == "THEMIS":
        return formats.themis.check_gzip_fn(data, object_name)
    return False, None


# pointers we do not automatically load even when loading greedily --
# generally these are reference files, usually throwaway ones, that are not
# archived in the same place as the data products and add little, if any,
# context to individual products
objects_to_ignore = [
    "DESCRIPTION", "DATA_SET_MAP_PROJECT.*", ".*_DESC"
]
OBJECTS_IGNORED_BY_DEFAULT = re.compile('|'.join(objects_to_ignore))


def ignore_if_pdf(data, object_name, path):
    if looks_like_this_kind_of_file(path, [".pdf"]):
        warnings.warn(
            f"Cannot open {path}; PDF files are not supported."
        )
        block = data.metaget_(object_name)
        if block is None:
            return data.metaget_(pointerize(object_name))
        return block
    return open(check_cases(path)).read()


def check_array_for_subobject(block):
    valid_subobjects = ["ARRAY", "BIT_ELEMENT", "COLLECTION", "ELEMENT"]
    subobj = [sub for sub in valid_subobjects if sub in block]
    if len(subobj) > 1:
        raise ValueError(
            f'ARRAY objects may only have one subobject (this has '
            f'{len(subobj)})'
        )
    if len(subobj) < 1:
        return block
    return block[subobj[0]]


def get_array_num_items(block):
    items = block["AXIS_ITEMS"]
    if isinstance(items, int):
        return items
    if isinstance(items, Sequence):
        return reduce(mul, items)
    raise TypeError("can't interpret this item number specification")
