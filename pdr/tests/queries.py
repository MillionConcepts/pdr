from pdr.parselabel.pds3 import parse_pvl, literalize_pvl

# TODO: shouldn't have to do this import. partial circular import issue.
import pdr.formats
from pdr.loaders.queries import (
    generic_image_properties,
    im_sample_type,
    base_sample_info, get_qube_band_storage_type, generic_qube_properties,
    extract_axplane_metadata,
)

BLOCK_TEXT = """OBJECT                            = IMAGE
  INTERCHANGE_FORMAT              = BINARY
  LINES                           = 650
  LINE_SAMPLES                    = 350
  SAMPLE_TYPE                     = IEEE_REAL
  SAMPLE_BITS                     = 32
  BANDS                           = 3
  BAND_STORAGE_TYPE               = BAND_SEQUENTIAL
  FIRST_LINE                      = 375
  FIRST_LINE_SAMPLE               = 1
  SAMPLE_BIT_MASK                 = 2#0111111111111111#
  INVALID_CONSTANT                = (0.0,0.0,0.0)
  MISSING_CONSTANT                = (0.0,0.0,0.0)
END_OBJECT                        = IMAGE
"""


def basesamp():
    block = literalize_pvl(parse_pvl(BLOCK_TEXT)[0]["IMAGE"])
    base = base_sample_info(block)
    assert base == {"BYTES_PER_PIXEL": 4, "SAMPLE_TYPE": "IEEE_REAL"}
    return base


def imsamp():
    sample_type = im_sample_type(basesamp())
    assert sample_type == ">f"
    return sample_type


def generic_properties():
    block = literalize_pvl(parse_pvl(BLOCK_TEXT)[0]["IMAGE"])
    props = generic_image_properties(block, imsamp())
    assert props == {
        "BYTES_PER_PIXEL": 4,
        "is_vax_real": False,
        "sample_type": ">f",
        "nrows": 650,
        "ncols": 350,
        "nbands": 3,
        "band_storage_type": "BAND_SEQUENTIAL",
        "rowpad": 0,
        "colpad": 0,
        "bandpad": 0,
        "linepad": 0,
    }


QUBE_BLOCK_TEXT = """OBJECT = SPECTRAL_QUBE
  AXES = 3
  AXIS_NAME = (SAMPLE, LINE, BAND)
  ISIS_STRUCTURE_VERSION_ID = "2.1"
  /* Core Description */
  CORE_ITEMS = (100, 66, 17)
  CORE_NAME = "CALIBRATED SPECTRAL RADIANCE"
  CORE_ITEM_BYTES = 4
  CORE_ITEM_TYPE = IEEE_REAL
  CORE_BASE = 0.000000
  CORE_MULTIPLIER = 1.000000
  CORE_UNIT = "uWATT*CM**-2*SR**-1*uM**-1"
  CORE_NULL = -1.0
  CORE_VALID_MINIMUM = 0.0
  CORE_LOW_REPR_SATURATION = -32767.0
  CORE_LOW_INSTR_SATURATION = -32766.0
  CORE_HIGH_REPR_SATURATION = -32765.0
  CORE_HIGH_INSTR_SATURATION = -32764.0  
  SUFFIX_ITEMS = (0,0,8)
  BAND_SUFFIX_ITEM_BYTES = 4
END_OBJECT
"""


def qube_props():
    params, _ = parse_pvl(QUBE_BLOCK_TEXT)
    qube_block = literalize_pvl(params["SPECTRAL_QUBE"])
    # base = base_sample_info(qube_block)
    # samp_type = im_sample_type(base)
    band_storage_type = get_qube_band_storage_type(qube_block)
    props = generic_qube_properties(qube_block, band_storage_type)
    assert props == {
        'BYTES_PER_PIXEL': 4, 'sample_type': '>f', 'axnames': ('SAMPLE', 'LINE', 'BAND'), 'ncols': 100, 'nrows': 66, 'nbands': 17, 'band_storage_type': 'BAND_SEQUENTIAL', 'rowpad': 0, 'colpad': 0, 'bandpad': 8, 'suffix_bands': 8, 'linepad': 0
    }
    return qube_block, props


def axplanes():
    qube_block, props = qube_props()
    assert extract_axplane_metadata(qube_block, props) == {'rowpad': 0, 'colpad': 0, 'bandpad': 8, 'suffix_bands': 8}


basesamp()
imsamp()
axplanes()
qube_props()
generic_properties()
