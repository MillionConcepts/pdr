from pdr.loaders.queries import table_position


# def lamp_rdr_histogram_header_loader(data):
#     # CAL_HISTOGRAM_DATA_HEADER pointer is an ASCII FITS header, but the
#     # 'histogram' keyword tries to send it to data.read_histogram
#     return data.read_header


# TODO: this doesn't fully solve the problem; data.show() still throws errors
# that cause ix check to crash (refers to original special case in /develop
# -- this is a rewrite)
def lamp_rdr_histogram_image_loader(data):
    """Products can have multiple unique pointers that are
    defined by a single image object (CAL_HISTOGRAM_DATA_IMAGE)."""
    object_name = "CAL_HISTOGRAM_DATA_IMAGE"
    block = data.metablock_(object_name)
    return block


def get_crater_offset():
    """
    lro crater edr products have a header table with 64 bytes per row, the
    second table start byte is given in rows (also the wrong row) but had a
    different number of row bytes

    HITS
    * lro_crater
        * edr_sec
        * edr_hk
    """
    return True, 64


def crater_bit_col_sample_type(base_samp_info):
    """
    HITS
    * lro_crater
        * edr_sec
        * edr_hk
    """
    from pdr.datatypes import sample_types

    sample_type = base_samp_info["SAMPLE_TYPE"]
    sample_bytes = base_samp_info["BYTES_PER_PIXEL"]
    if "BIT_STRING" == sample_type:
        sample_type = "MSB_BIT_STRING"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    if "N/A" in sample_type:
        sample_type = "MSB_UNSIGNED_INTEGER"
        return True, sample_types(
            sample_type, int(sample_bytes), for_numpy=True
        )
    return False, None


def rss_get_position(identifiers, block, target, name, start_byte):
    """
    The RSS WEA products' WEAREC_TABLE undercounts ROW_BYTES by 1

    HITS
    * lro_rss
        * wea
    """
    table_props = table_position(identifiers, block, target, name, start_byte)
    n_records = block["ROWS"]
    record_bytes = block["ROW_BYTES"] + 1
    length = n_records * record_bytes
    table_props["length"] = length
    return True, table_props


def mini_rf_image_loader(data, name):
    """
    one of the mosaic labels has the wrong values for lines/line_samples

    HITS
    * lro_mini_rf
        * mosaic
    """
    block = data.metablock_(name)
    block["LINES"] = 5760
    block["LINE_SAMPLES"] = 11520
    return block


def mini_rf_spreadsheet_loader(filename, fmtdef_dt):
    """
    Mini-RF housekeeping CSVs have variable-width columns but the labels treat 
    them as fixed-width. 

    HITS
    * lro_mini_rf
        * housekeeping
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt
    # The names argument is used here to explicitly set the number of columns
    # to 3. Otherwise the first row (which only has 1 column) confuses read_csv
    table = pd.read_csv(filename, header=None, sep=",",
                        names = ("POINT_NAME", "VALUE", "UNITS"))
    assert len(table.columns) == len(fmtdef.NAME.tolist())
    table.columns = fmtdef.NAME.tolist()
    return table


def wea_table_loader(filename, fmtdef_dt):
    """
    Some, but not all, wea files have more bytes than the labels define per row.

    HITS
    * lro_rss
        * wea
    """
    import pandas as pd

    fmtdef, dt = fmtdef_dt

    table = pd.read_csv(filename, skiprows=1, header=None, sep=r':|\s+',
                        engine='python')
    table.columns = [
        f for f in fmtdef['NAME'] if not f.startswith('PLACEHOLDER')
    ]
    return table


class DoesNotExistError(Exception):
    """"""
    pass

def lamp_edr_hdu_exceptions(name, hdulist):
    """
    Sometimes all the LAMP EDR table pointers exist, sometimes they aren't 
    actually there.

    HITS
    * lro_lamp
        * edr
    """
    if name == "ACQUISITION_LIST_TABLE":
        extname = "Acquisition List"
    elif name == "FRAME_DATA_TABLE":
        extname = "Raw Frame Data"
    elif name == "CALCULATED_COUNTRATE_TABLE":
        extname = "Calculated Countrate"
    elif name == "LTS_DATA_TABLE":
        extname = "LTS Data"
    elif name == "HOUSEKEEPING_TABLE":
        extname = "Housekeeping Data"
    else:
        # Nothing should hit this, but it's here in case there is a rogue 
        # product with a [*]_TABLE pointer missed above
        return False, None
    
    if hdulist.fileinfo(extname)['datSpan'] == 0:
        raise DoesNotExistError(
            f"The {name}'s length is zero; the table does not actually exist."
        )
    return False, None

def lamp_rdr_hdu_start_byte(name, hdulist):
    """
    This special case raises an error if a pointer's data doesn't actually 
    exist, and returns the correct start byte if it does.

    HITS
    * lro_lamp
        * rdr
    """
    if "ACQUISITION_LIST" in name:
        extname = "Acquisition List"
    elif "CAL_PIXELLIST_DATA" in name:
        extname = "Calibrated Pixel List Mode Data"
    elif "ANCILLARY_DATA" in name:
        extname = "Ancillary Data"
    elif "CAL_HISTOGRAM_" in name:
        # The multiple CAL_HISTOGRAM_[...]_IMAGE pointers all point at the same 
        # FITS HDU (each pointer illegally represents one image in the cube).
        extname = "Calibrated Histogram Mode Data"
    elif "CAL_CALCULATED_COUNTRATE" in name:
        extname = "Calculated Countrate"
        try:
            # Check to see if this is the correct 'EXTNAM' in the fits HDU
            hdulist.fileinfo(extname)
        except:
            # Sometimes this pointer refers to a different HDU extension name
            extname = "Reduced Count Rate"
    elif "LTS_DATA" in name:
        extname = "LTS Data"
    elif "HOUSEKEEPING" in name:
        extname = "Housekeeping Data"
    elif "WAVELENGTH_LOOKUP" in name:
        extname = "Wavelength Lookup Image"
    else:
        # The CAL_SPECTRAL_IMAGE_* pointers open fine
        return False, None

    if 'HEADER' in name:
        return True, hdulist.fileinfo(extname)['hdrLoc']
    if hdulist.fileinfo(extname)['datSpan'] == 0:
        raise DoesNotExistError(
            f"The {name}'s length is zero; the data object does not actually exist."
        )
    return True, hdulist.fileinfo(extname)['datLoc']

