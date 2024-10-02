from pdr.parselabel.pds3 import parse_pvl, literalize_pvl
from pdr.loaders.queries import (
    generic_image_properties,
    get_qube_band_storage_type,
    generic_qube_properties,
    extract_axplane_metadata,
)

from pdr.tests.objects import BLOCK_TEXT, QUBE_BLOCK_TEXT


def basesamp():
    block = literalize_pvl(parse_pvl(BLOCK_TEXT)[0]["IMAGE"])
    base = base_sample_info(block)
    assert base == {"BYTES_PER_PIXEL": 4, "SAMPLE_TYPE": "IEEE_REAL"}
    assert im_sample_type(base) == ">"


def test_generic_properties():
    block = parse_pvl(BLOCK_TEXT)[0]["IMAGE"]
    props = generic_image_properties(block, ">f")
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


def test_qube_props():
    params, _ = parse_pvl(QUBE_BLOCK_TEXT)
    qube_block = params["SPECTRAL_QUBE"]
    band_storage_type = get_qube_band_storage_type(qube_block)
    props = generic_qube_properties(qube_block, band_storage_type)
    assert props == {
        "BYTES_PER_PIXEL": 4,
        "sample_type": ">f",
        "axnames": ("SAMPLE", "LINE", "BAND"),
        "ncols": 100,
        "nrows": 66,
        "nbands": 17,
        "band_storage_type": "BAND_SEQUENTIAL",
        "rowpad": 0,
        "colpad": 0,
        "bandpad": 8,
        "suffix_bands": 8,
        "linepad": 0,
        "is_vax_real": False,
    }
    assert extract_axplane_metadata(qube_block, props) == {
        "rowpad": 0,
        "colpad": 0,
        "bandpad": 8,
        "suffix_bands": 8,
    }
