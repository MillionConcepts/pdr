from __future__ import annotations
from typing import TYPE_CHECKING
import warnings

import pdr.loaders.queries

if TYPE_CHECKING:
    from pdr.loaders.astrowrap.fits import HDUList


# TODO: why is this in the galileo module?
def mdis_fits_start_byte(name: str, hdulist: HDUList) -> int:
    """
    The MDIS cal labels do not include accurate offsets for data objects.
    (There's also an additional HDU they don't label as a PDS object at all!)

    HITS
    * messenger_grnd_cal
        * mdis
    """
    if name not in ("IMAGE", "HEADER"):
        raise NotImplementedError("Unknown MDIS extension name")
    if name == "HEADER":
        return 0
    return hdulist.fileinfo(0)['datLoc']


def galileo_table_loader():
    """"""
    warnings.warn("Galileo EDR binary tables are not yet supported.")
    return True


def ssi_cubes_header_loader():
    """
    The Ida and Gaspra cubes have HEADER pointers but no defined HEADER
    objects

    HITS
    * gal_ssi
        * sb_cube
    """
    return True


def nims_edr_sample_type(base_samp_info):
    """
    Each time byte order is specified for these products it is LSB, so this
    assumes BIT_STRING refers to LSB_BIT_STRING. N/A samples are read as
    CHARACTER

    HITS
    * gal_nims
        * pre_jup
    """
    from pdr.datatypes import sample_types

    sample_type = base_samp_info["SAMPLE_TYPE"]
    sample_bytes = base_samp_info["BYTES_PER_PIXEL"]
    if "BIT_STRING" == sample_type:
        sample_type = "LSB_BIT_STRING"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    if "N/A" in sample_type:
        sample_type = "CHARACTER"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    return False, None


def probe_structure(block, name, filename, data, identifiers):
    """
    Several NMS products have an incorrect BYTES value in one column.
    One ASI product has incorrect BYTES values in multiple columns

    HITS
    * gal_probe
        * asi
        * nms
    """
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    # Several NMS products have an incorrect BYTES value in one column
    if fmtdef.at[1, "NAME"] == "COUNTS":
        fmtdef.at[1, "BYTES"] = 8
    # One ASI product has incorrect BYTES values in multiple columns
    elif identifiers["PRODUCT_ID"] == "HK01AD.TAB":
        fmtdef.at[1, "BYTES"] = 4
        fmtdef.at[3, "BYTES"] = 2
        fmtdef.at[5, "BYTES"] = 2
    return fmtdef, None


def epd_special_block(data, name):
    """
    All 'E1' EPD SUMM products incorrectly say ROW_BYTES = 90; changing them
    to the RECORD_BYTES values.

    HITS
    * gal_particles
        * epd_summ (partial)
    """
    block = data.metablock_(name)
    block["ROW_BYTES"] = data.metaget_("RECORD_BYTES")
    return block


def epd_structure(block, name, filename, data, identifiers):
    """
    E1PAD_7.TAB has an extra/unaccounted for byte at the start of each row

    HITS
    * gal_particles
        * epd_samp (partial)
    """
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    for row in range(0, 9):
        fmtdef.at[row, "START_BYTE"] += 1
    return fmtdef, None


def pws_special_block(data, name):
    """
    The PWS SUMM products sometimes undercount ROW_BYTES by 2

    HITS
    * gal_plasma
        * pws_summ
    * vg_pws
        * jup_summ
        * sat_summ
        * sys_summ_vg1
        * sys_summ_vg2
        * sys_ancillary
        * ur_rdr_bin
        * ur_rdr_asc
        * ur_summ_bin
        * ur_summ_asc
        * newp_summ_bin
        * nep_summ_asc
    """
    block = data.metablock_(name)
    product_id = data.metaget_("PRODUCT_ID")
    if "B.TAB" in product_id:
        block["ROW_BYTES"] = 366
    if "E.TAB" in product_id:
        block["ROW_BYTES"] = 516
    return block


def pws_table_loader(filename, fmtdef_dt):
    """
    HITS
    * gal_plasma
        * pws_ddr
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    table = pd.read_csv(filename, header=1, sep=";")
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table


def nims_sample_spectral_qube_trivial_loader():
    """
    HITS
    * gal_nims
        *cube
    """
    warnings.warn('Galileo NIMS SAMPLE_SPECTRUM_QUBE objects are not supported'
                  'due to their use of nibble pixels.')
    return True

def ssi_telemetry_bit_col_format(definition):
    """
    One of the bit columns defined in the Galileo SSI telemetry table format 
    file has multiple items, but ITEM_BITS is mislabled as BITS

    HITS:
    * gal_ssi
        * redr
    * sl9_jupiter_impact
        * go_ssi
    """
    # fix `definition` in-place
    for column in iter(definition.items()):
        if "BIT_COLUMN" in column:
            if "ITEMS" in column[1] and "ITEM_BITS" not in column[1]:
                column[1].add("ITEM_BITS", 1)
    # return nothing because nothing modifies `obj`
    return False, None
