import pds4_tools as pds4
import numpy as np
import pandas as pd
import os
import sys
from collections import OrderedDict
from astropy.io import fits as pyfits
import pandas as pd

import struct
import pvl
import gzip
import bz2
from zipfile import ZipFile

import rasterio

def has_attached_label(filename):
    """Read the first line of a file to decide if it's a label."""
    with open(filename, "rb") as f:
        return "PDS_VERSION_ID" in str(f.readline())

def parse_attached_label(filename):
    """Parse an attached label of a IMG file."""
    # First grab the entries from the label that define how to read the label
    return pvl.load(filename)

def parse_label(filename, full=False):
    """Wraps forking paths for attached and detached PDS3 labels."""
    if filename.endswith(".fmt"):
        return pvl.load(filename)
    if not has_attached_label(filename):
        if os.path.exists(filename[: filename.rfind(".")] + ".LBL"):
            label = pvl.load(filename[: filename.rfind(".")] + ".LBL")
        elif os.path.exists(filename[: filename.rfind(".")] + ".lbl"):
            label = pvl.load(filename[: filename.rfind(".")] + ".lbl")
        elif os.path.exists(filename[: filename.rfind(".")] + ".xml"):
            # TODO: Make label data format consistent between PDS3 & 4
            label = pds4.read(
                filename[: filename.rfind(".")] + ".xml", quiet=True
            ).label.to_dict()
        else:
            print("*** Unable to locate file label. ***")
            return None
    else:
        label = parse_attached_label(filename)
    # TODO: This ugly conditional exists entirely to deal with Cassini data
    # which all seem to be returning zero-value images, so maybe it's wrong!
    if (not full) and ("UNCOMPRESSED_FILE" in label.keys()):
        if "COMPRESSED_FILE" in label.keys():
            if "ENCODING_TYPE" in label["COMPRESSED_FILE"].keys():
                if label["COMPRESSED_FILE"]["ENCODING_TYPE"] == "MSLMMM-COMPRESSED":
                    return label
        return label["UNCOMPRESSED_FILE"]
    return label


def sample_types(SAMPLE_TYPE, SAMPLE_BYTES):
    """Defines a translation from PDS data types to Python data types.

    TODO: The commented-out types below are technically valid PDS3
        types, but I haven't yet worked out the translation to Python.
    """
    # NOTE: The byte depth of various data types is non-unique in PDS3
    return {
        "MSB_INTEGER": ">h",
        "INTEGER": ">h",
        "MAC_INTEGER": ">h",
        "SUN_INTEGER": ">h",
        "MSB_UNSIGNED_INTEGER": ">h" if SAMPLE_BYTES == 2 else ">B",
        "UNSIGNED_INTEGER": ">B",
        "MAC_UNSIGNED_INTEGER": ">B",
        "SUN_UNSIGNED_INTEGER": ">B",
        "LSB_INTEGER": "<h" if SAMPLE_BYTES == 2 else "<B",
        "PC_INTEGER": "<h",
        "VAX_INTEGER": "<h",
        "LSB_UNSIGNED_INTEGER": "<h" if SAMPLE_BYTES == 2 else "<B",
        "PC_UNSIGNED_INTEGER": "<B",
        "VAX_UNSIGNED_INTEGER": "<B",
        "IEEE_REAL": ">f",
        "PC_REAL": "<f",
        "FLOAT": ">f",
        "REAL": ">f",
        "MAC_REAL": ">f",
        "SUN_REAL": ">f",
        "MSB_BIT_STRING": ">B",
    }[SAMPLE_TYPE]

# Possibly unused in PDS3: just park them here unless needed
#        'IEEE_COMPLEX': '>c',
#        'COMPLEX': '>c',
#        'MAC_COMPLEX': '>c',
#        'SUN_COMPLEX': '>c',

#        'PC_COMPLEX': '<c',

#        'MSB_BIT_STRING': '>S',
#        'LSB_BIT_STRING': '<S',
#        'VAX_BIT_STRING': '<S',


def get_data_types(filename):
    """Placeholder function for the fact that PDS3 can contain multiple
    types of data (e.g. an image and a header) which are defined by
    'pointers' in the label. This should be dealt with at some point.
    """
    for k in parse_label(filename).keys():
        if k.startswith("^"):
            print(k)


def data_start_byte(label, pointer):
    """Determine the first byte of the data in an IMG file from its pointer."""
    if type(label[pointer]) is int:
        return label["RECORD_BYTES"] * (label[pointer] - 1)
    elif type(label[pointer]) is list:
        if type(label[pointer][0]) is int:
            return label[pointer][0]
        elif type(label[pointer][-1]) is int:
            return label["RECORD_BYTES"] * (label[pointer][-1] - 1)
        else:
            return 0
    elif type(label[pointer]) is str:
        return 0
    else:
        print("WTF?", label[pointer])
        raise


def read_image(filename, label, pointer="IMAGE"):  # ^IMAGE
    """Read a PDS IMG formatted file into an array.
    TODO: Check for and account for LINE_PREFIX.
    TODO: Check for and apply BIT_MASK.
    """
    """
    rasterio will read an ENVI file if the HDR metadata is present...
    However, it seems to read M3 L0 images incorrectly because it does
    not account for the L0_LINE_PREFIX_TABLE. So I am deprecating
    the use of rasterio until I can figure out how to produce consistent
    output."""
    try:
        if 'INSTRUMENT_ID' in label.keys():
            if (label['INSTRUMENT_ID'] == "M3" and label['PRODUCT_TYPE'] == "RAW_IMAGE"):
                raise # because rasterio doesn't read M3 L0 data correctly
        dataset = rasterio.open(filename)
        if len(dataset.indexes)==1:
            return dataset.read()[0,:,:] # Make 2D images actually 2D
        else:
            return dataset.read()
    except rasterio.errors.RasterioIOError:
        #print(' *** Not using rasterio. ***')
        pass
    if pointer in label.keys():
        if pointer=='QUBE': # ISIS2 QUBE format
            print('Also QUBE')
            BYTES_PER_PIXEL = int(label[pointer]["CORE_ITEM_BYTES"])# / 8)
            DTYPE = sample_types(label[pointer]["CORE_ITEM_TYPE"], BYTES_PER_PIXEL)
            nrows = label[pointer]["CORE_ITEMS"][2]
            ncols = label[pointer]["CORE_ITEMS"][0]
            prefix_cols,prefix_bytes = 0,0
            # TODO: Handle the QUB suffix data
            BANDS = label[pointer]["CORE_ITEMS"][1]
            band_storage_type = "ISIS2_QUBE"
        else:
            BYTES_PER_PIXEL = int(label[pointer]["SAMPLE_BITS"] / 8)
            DTYPE = sample_types(label[pointer]["SAMPLE_TYPE"], BYTES_PER_PIXEL)
            nrows = label[pointer]["LINES"]
            ncols = label[pointer]["LINE_SAMPLES"]
            if "LINE_PREFIX_BYTES" in label[pointer].keys():
                # print("Accounting for a line prefix.")
                prefix_cols = int(label[pointer]["LINE_PREFIX_BYTES"] / BYTES_PER_PIXEL)
                prefix_bytes = prefix_cols * BYTES_PER_PIXEL
            else:
                prefix_cols = 0
                prefix_bytes = 0
            try:
                BANDS = label[pointer]["BANDS"]
                band_storage_type = label[pointer]["BAND_STORAGE_TYPE"]
            except KeyError:
                BANDS = 1
                band_storage_type = None
        pixels = nrows * (ncols + prefix_cols) * BANDS
        start_byte = data_start_byte(label, f"^{pointer}")
    elif label["INSTRUMENT_ID"] == "M3" and label["PRODUCT_TYPE"] == "RAW_IMAGE":
        # print('Special case: Chandrayaan-1 M3 data.')
        BYTES_PER_PIXEL = int(label["L0_FILE"]["L0_IMAGE"]["SAMPLE_BITS"] / 8)
        DTYPE = sample_types(
            label["L0_FILE"]["L0_IMAGE"]["SAMPLE_TYPE"], BYTES_PER_PIXEL
        )
        nrows = label["L0_FILE"]["L0_IMAGE"]["LINES"]
        ncols = label["L0_FILE"]["L0_IMAGE"]["LINE_SAMPLES"]
        prefix_bytes = int(label["L0_FILE"]["L0_IMAGE"]["LINE_PREFIX_BYTES"])
        prefix_cols = (
            prefix_bytes / BYTES_PER_PIXEL
        )  # M3 has a prefix, but it's not image-shaped
        BANDS = label["L0_FILE"]["L0_IMAGE"]["BANDS"]
        pixels = nrows * (ncols + prefix_cols) * BANDS
        start_byte = 0
        band_storage_type = label["L0_FILE"]["L0_IMAGE"]["BAND_STORAGE_TYPE"]
    else:
        # print("*** IMG w/ old format attached label not currently supported.")
        # print("\t{fn}".format(fn=filename))
        # print("No image data identified.")
        return None
    fmt = "{endian}{pixels}{fmt}".format(endian=DTYPE[0], pixels=pixels, fmt=DTYPE[-1])
    try:  # a little decision tree to seamlessly deal with compression
        if filename.endswith(".gz"):
            f = gzip.open(filename, "rb")
        elif filename.endswith(".bz2"):
            f = bz2.BZ2File(filename, "rb")
        elif filename.endswith(".ZIP"):
            f = ZipFile(filename, "r").open(
                ZipFile(filename, "r").infolist()[0].filename
            )
        else:
            f = open(filename, "rb")
        # Make sure that single-band images are 2-dim arrays.
        f.seek(start_byte)
        prefix = None
        if BANDS == 1:
            image = np.array(struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL)))
            image = image.reshape(nrows, (ncols + prefix_cols))
            if prefix_cols:
                # Ignore the prefix data, if any.
                # TODO: Also return the prefix
                prefix = image[:, :prefix_cols]
                if pointer == "LINE_PREFIX_TABLE":
                    return prefix
                image = image[:, prefix_cols:]
        elif band_storage_type == "BAND_SEQUENTIAL":
            image = np.array(struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL)))
            image = image.reshape(BANDS, nrows, (ncols + prefix_cols))
        elif band_storage_type == "LINE_INTERLEAVED":
            image, prefix = [], []
            for i in np.arange(nrows):
                prefix += [f.read(prefix_bytes)]
                frame = np.array(
                    struct.unpack(
                        f"<{BANDS*ncols}h", f.read(BANDS * ncols * BYTES_PER_PIXEL)
                    )
                ).reshape(BANDS, ncols)
                image += [frame]
            image = np.array(image).reshape(BANDS, nrows, ncols)
        else:
            print(f"*** Unknown BAND_STORAGE_TYPE={band_storage_type}. Guessing BAND_SEQUENTIAL.")
            image = np.array(struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL)))
            image = image.reshape(BANDS, nrows, (ncols + prefix_cols))
    except:
        raise
    finally:
        f.close()
    if "PREFIX" in pointer:
        return prefix
    return image

def read_qube(filename, label, pointer='QUBE'):
    print('QUBE')
    return read_image(filename, label, pointer=pointer)

def read_line_prefix_table(filename, label, pointer="LINE_PREFIX_TABLE"):
    return read_image(filename, label, pointer=pointer)


def read_CH1_M3_L0_prefix_table(filename, label):
    prefix = read_line_prefix_table(filename, label, pointer="L0_LINE_PREFIX_TABLE")
    return [
        [p[:269].decode("ascii")] + list(struct.unpack("<22B", p[640:662]))
        for p in prefix
    ]


def parse_image_header(filename, label):
    # Backup function for parsing the IMAGE_HEADER when pvl breaks
    with open(filename, "r") as f:
        f.seek(data_start_byte(label, "^IMAGE_HEADER"))
        header_str = str(f.read(label["IMAGE_HEADER"]["BYTES"]))
    image_header = {}
    lastkey = None
    for entry in header_str.split("  "):
        pv = entry.split("=")
        if len(pv) == 2:
            # The `strip("'")` is to avoid double quotations
            image_header[pv[0]] = pv[1].strip("'")
            lastkey = pv[0]
        elif len(pv) == 1 and lastkey:
            # Append the runon line to the previous value...
            if len(pv[0]):  # ... unless it's empty
                image_header[lastkey] += " " + pv[0].strip("'")
        else:
            raise
    return image_header


def read_image_header(filename, label):  # ^IMAGE_HEADER
    # label = parse_label(filename)
    try:
        with open(filename, "rb") as f:
            f.seek(data_start_byte(label, "^IMAGE_HEADER"))
            image_header = pvl.load(
                f.read(label["IMAGE_HEADER"]["BYTES"]))
        return image_header
    except:  # Specifically on ParseError from PVL...
        # The IMAGE_HEADER is not well-constructed according to PVL
        try:  # to parse it naively
            return parse_image_header(filename, label)
        except:
            #  Naive parsing didn't work...
            #    so just return the unparsed plaintext of the image header.
            with open(filename, "r") as f:
                f.seek(data_start_byte(label, "^IMAGE_HEADER"))
                image_header = str(f.read(label["IMAGE_HEADER"]["BYTES"]))
            return image_header
    raise  # WHAT ARE THIS?!

def read_bad_data_values_header(filename):  # ^BAD_DATA_VALUES_HEADER
    label = parse_label(filename)
    with open(filename, "rb") as f:
        f.seek(data_start_byte(label, "^BAD_DATA_VALUES_HEADER"))
        bad_data_values_header = f.read(label["BAD_DATA_VALUES_HEADER"]["BYTES"])
    print(
        "*** BAD_DATA_VALUES_HEADER not parsable without file: {DESCRIPTION} ***".format(
            DESCRIPTION=label["BAD_DATA_VALUES_HEADER"]["^DESCRIPTION"]
        )
    )
    return bad_data_values_header


def read_histogram(filename):  # ^HISTOGRAM
    label = parse_label(filename)
    DTYPE = sample_types(label["HISTOGRAM"]["DATA_TYPE"], 0)
    if label["HISTOGRAM"]["ITEM_BYTES"] == 4:
        DTYPE = DTYPE[0] + "i"
    items = label["HISTOGRAM"]["ITEMS"]
    fmt = "{endian}{items}{fmt}".format(endian=DTYPE[0], items=items, fmt=DTYPE[-1])
    with open(filename, "rb") as f:
        f.seek(data_start_byte(label, "^HISTOGRAM"))
        histogram = np.array(
            struct.unpack(fmt, f.read(items * label["HISTOGRAM"]["ITEM_BYTES"]))
        )
    return histogram


def read_engineering_table(filename, label):  # ^ENGINEERING_TABLE
    return read_table(filename, label, pointer="ENGINEERING_TABLE")


def read_measurement_table(filename, label):  # ^MEASUREMENT_TABLE
    return read_table(filename, label, pointer="MEASUREMENT_TABLE")


def read_telemetry_table(filename):  # ^TELEMETRY_TABLE
    return read_table(filename, pointer="TELEMETRY_TABLE")



def read_jp2(filename):  # .JP2 extension
    # NOTE: These are the huge HIRISE images. It might be best to just
    #       leave thie capability to GDAL so that we don't have to bother
    #       with memory management.
    print("*** JP2 filetype not yet supported. ***")
    return


def read_mslmmm_compressed(filename):
    """WARNING: Placeholder functionality.
    This will run `dat2img` to decompress the file from Malin's bespoke
    image compression format (which has no obvious purpose other than
    obfuscation) into the local direction, then read the resulting file,
    and then delete it.
    TODO: Modify dat2img.c and pdecom_msl.c, or port them, to decode the
        data directly into a Python array.
    """
    _ = os.system(f"./MMM_DAT2IMG/dat2img {filename}")
    imgfilename = filename.split("/")[-1].replace(".DAT", "_00.IMG")
    if os.path.exists(imgfilename):
        image = read_image(imgfilename)
        print(f"Deleting {imgfilename}")
        os.remove(imgfilename)
    else:
        print(f"{imgfilename} not present.")
        print("\tIs MMM_DAT2IMG available and built?")
    return


def read_fits(filename, dim=0, quiet=True):
    """Read a PDS FITS file into an array.
    Return the data _and_ the label.
    """
    hdulist = pyfits.open(filename)
    data = hdulist[dim].data
    header = hdulist[dim].header
    hdulist.close()
    return (
        data,
        pds4.read(filename.replace(".fits", ".xml"), quiet=True).label.to_dict(),
    )


def read_dat_pds4(filename, write_csv=False, quiet=True):
    """Reads a PDS4 .dat format file, preserving column order and data type,
    except that byte order is switched to native if applicable. The .dat file
    and .xml label must exist in the same directory.
    Return the data _and_ the label.
    """
    if filename[-4:].lower() == ".dat":
        filename = filename[:-4] + ".xml"
    if filename[-4:].lower() != ".xml":
        raise TypeError("Unknown filetype: {ext}".format(ext=filename[-4:]))
    structures = pds4.pds4_read(filename, quiet=quiet)
    dat_dict = OrderedDict({})
    for i in range(len(structures[0].fields)):
        name = structures[0].fields[i].meta_data["name"]
        dat_dtype = structures[0].fields[i].meta_data["data_type"]
        dtype = pds4.reader.data_types.pds_to_numpy_type(dat_dtype)
        data = np.array(structures[0].fields[i], dtype=dtype)
        if (sys.byteorder == "little" and ">" in str(dtype)) or (
            sys.byteorder == "big" and "<" in str(dtype)
        ):
            data = data.byteswap().newbyteorder()
        dat_dict[name] = data
    dataframe = pd.DataFrame(dat_dict)
    if write_csv:
        dataframe.to_csv(filename.replace(".xml", ".csv"), index=False)
    return dataframe


def read_dat_pds3(filename):
    if not has_attached_label(filename):
        print("*** DAT w/ detached PDS3 LBL not currently supported.")
        try:
            et = parse_label(filename)["COMPRESSED_FILE"]["ENCODING_TYPE"]
            print("\tENCODING_TYPE = {et}".format(et=et))
        except:
            pass
    else:
        print("*** DAT w/ attached PDS3 LBL not current supported.")
    print("\t{fn}".format(fn=filename))
    return None, None


def dat_to_csv(filename):
    """Converts a PDS4 file to a Comma Separated Value (CSV) file with
    the same base filename. The .dat file and .xml label must exist in
    the same directory.
    """
    _ = read_dat(filename, write_csv=True)


def unknown(filename):
    print("\t{fn}".format(fn=filename))
    return None, None


def read_description(filename):  # ^DESCRIPTION
    label = parse_label(filename)
    return label["^DESCRIPTION"]


def read_label(filename):
    try:
        label = pvl.load(filename)
        if not len(label):
            raise ValueError("Cannot find attached label data.")
        return label
    except:  # look for a detached label
        if os.path.exists(filename[: filename.rfind(".")] + ".LBL"):
            return pvl.load(filename[: filename.rfind(".")] + ".LBL")
        elif os.path.exists(filename[: filename.rfind(".")] + ".lbl"):
            return pvl.load(filename[: filename.rfind(".")] + ".lbl")
        elif os.path.exists(filename[: filename.rfind(".")] + ".xml"):
            # TODO: Also read the FITS header as a ^HEADER
            return pds4.read(
                filename[: filename.rfind(".")] + ".xml", quiet=True
            ).label.to_dict()
        else:
            print(" *** Cannot find label data. *** ")
            raise


def read_file_name(filename, label):  # ^FILE_NAME
    return label["^FILE_NAME"]


def read_description(filename, label):  # ^DESCRIPTION
    return label["^DESCRIPTION"]

def parse_table_structure(label, pointer="TABLE"):
    # Try to turn the TABLE definition into a column name / data type array.
    # Requires renaming some columns to maintain uniqueness.
    # Also requires unpacking columns that contain multiple entries.
    # if pointer=="TELEMETRY_TABLE":
    #    if ((label["SPACECRAFT_NAME"] == "GALILEO ORBITER") and
    #        (label["INSTRUMENT_NAME"] == "SOLID_STATE_IMAGING")):
    #        label = {pointer:parse_label('ref/GALILEO_ORBITER/SOLID_STATE_IMAGING/rtlmtab.fmt')}
    dt = []
    for i in range(len(label[pointer].keys())):
        obj = label[pointer][i]
        if obj[0] == "COLUMN":
            if obj[1]["NAME"] == "RESERVED":
                name = "RESERVED_" + str(obj[1]["START_BYTE"])
            else:
                name = obj[1]["NAME"]
            try:  # Some "columns" contain a lot of columns
                for n in range(obj[1]["ITEMS"]):
                    dt += [
                        (
                            f"{name}_{n}",
                            sample_types(obj[1]["DATA_TYPE"], obj[1]["ITEM_BYTES"]),
                        )
                    ]
            except KeyError:
                if len(dt):
                    while (
                        name in np.array(dt)[:, 0].tolist()
                    ):  # already a column with this name
                        name = f"{name}_"  # dunno... dumb way to enforce uniqueness
                dt += [(name, sample_types(obj[1]["DATA_TYPE"], obj[1]["BYTES"]))]
    return np.dtype(dt)


def read_table(filename, label, pointer="TABLE"):  # ^TABLE
    dt = parse_table_structure(label, pointer)
    return pd.DataFrame(
        np.fromfile(
            filename,
            dtype=dt,
            offset=data_start_byte(label, f"^{pointer}"),
            count=label[pointer]["ROWS"],
        )
        .byteswap()
        .newbyteorder()  # Pandas doesn't do non-native endian
    )

def read_bcr_image(filename,label,pointer="BCR_IMAGE"):
    # TODO: Make this function work.
    # This pointer appears in Rosetta / MIDAS data
    return read_image(filename, label, pointer=pointer)

def tbd(filename,label,pointer=""):
    print(f"The {pointer} pointer is not yet fully supported.")
    return label[f"^{pointer}"]

def pointer_to_function(pointer):
    try:
        return {
            "^IMAGE": read_image,
            "^IMAGE_HEADER": read_image_header,
            "^FILE_NAME": read_file_name,
            "^TABLE": read_table,
            "^DESCRIPTION": read_description,
            "^MEASUREMENT_TABLE": read_measurement_table,
            "^ENGINEERING_TABLE": read_engineering_table,
            "^QUBE": read_qube,
            "^BCR_IMAGE": read_bcr_image,
            }[pointer]
    except KeyError:
        return tbd

# def read_any_file(filename):
class Data:
    def __init__(self, filename):
        if filename.endswith(('xml','XML','lbl','LBL')):
            if os.path.exists(fn:=filename[:filename.rfind('.')]+'.IMG'):
                filename=fn
            elif os.path.exists(fn:=filename[:filename.rfind('.')]+'.img'):
                filename = fn
            elif os.path.exists(fn:=filename[:filename.rfind('.')]+'.fit'):
                filename = fn
            elif os.path.exists(fn := filename[:filename.rfind('.')] + '.FITS'):
                filename = fn
            elif os.path.exists(fn:=filename[:filename.rfind('.')]+'.FIT'):
                filename = fn
        setattr(self, "filename", filename)
        # Try PDS3 options
        setattr(self, "LABEL", read_label(filename))
        setattr(self, "pointers", [k for k in self.LABEL.keys() if k[0] == "^"])
        try:
            _ = [
                setattr(
                    self,
                    pointer[1:] if pointer.startswith("^") else pointer,
                    pointer_to_function(pointer)(filename, self.LABEL, pointer=pointer.strip("^")),
                )
                for pointer in self.pointers
            ]
        except: # no pointers defined
            raise
        try:
            if (
                self.LABEL["INSTRUMENT_ID"] == "M3"
                and self.LABEL["PRODUCT_TYPE"] == "RAW_IMAGE"
            ):
                setattr(self, "L0_IMAGE", read_image(filename, self.LABEL))
                setattr(
                    self,
                    "L0_LINE_PREFIX_TABLE",
                    read_CH1_M3_L0_prefix_table(filename, self.LABEL),
                )
        except: # not an M3 L0 image
            pass
        # Sometimes images do not have explicit pointers, so just always try
        #  to read an image out of the file no matter what.
        #if not ("^IMAGE" in self.pointers):
        try:
            image = read_image(filename, self.LABEL)
            if not image is None:
                setattr(self, "IMAGE", read_image(filename, self.LABEL))
        except:
            pass
