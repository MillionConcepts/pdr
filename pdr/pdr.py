import pds4_tools
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
import matplotlib.pyplot as plt


def pvl_to_dict(labeldata):
    # Convert a PVL label object to a Python dict
    data = {}
    if (
        (type(labeldata) == pvl._collections.PVLModule)
        or (type(labeldata) == pvl._collections.PVLGroup)
        or (type(labeldata) == pvl._collections.PVLObject)
    ):
        for k in labeldata.keys():
            data[k] = pvl_to_dict(labeldata[k])
    else:
        return labeldata
    return data


def filetype(filename):
    """ Attempt to deduce the filetype based on the filename.
    """
    if ".IMG" in filename.upper():
        return "IMG"
    elif ".FITS" in filename.upper():
        return "FITS"
    elif ".DAT" in filename.upper():
        if os.path.exists(filename.replace(".DAT", ".LBL")):
            # PDS3 .DAT with detached PVL label
            return "PDS3DAT"
        else:
            # presumed PDS4 .DAT with detached xml label
            return "PDS4DAT"
    else:
        print("*** Unsupported file type: [...]{end}".format(end=filename[-10:]))
        return "UNK"


def has_attached_label(filename):
    """ Read the first line of a file to decide if it's a label.
    """
    with open(filename, "rb") as f:
        return "PDS_VERSION_ID" in str(f.readline())


def parse_attached_label(filename):
    """ Parse an attached label of a IMG file.
    """
    # First grab the entries from the label that define how to read the label
    with open(filename, "rb") as f:
        for line_ in f:
            line = line_.decode("utf-8").strip()  # hacks through a rare error
            if "PDS_VERSION_ID" in line:
                PDS_VERSION_ID = line.strip().split("=")[1]
            if "RECORD_BYTES" in line:
                RECORD_BYTES = int(line.strip().split("=")[1])
            if "LABEL_RECORDS" in line:
                if "<BYTES>" in line:
                    # Convert pointer value to bytes like everything else
                    LABEL_RECORDS = line.strip().split("=")[1].split()[0] * 8
                else:
                    LABEL_RECORDS = int(line.strip().split("=")[1])
                break
    # Read the label and then parse it with PVL
    try:
        with open(filename, "rb") as f:
            return pvl.load(f.read(RECORD_BYTES * (LABEL_RECORDS)))
    except UnboundLocalError:
        print("*** RECORD_BYTES not set??? ***")
        return None
    except:
        with open(filename, "rb") as f:
            return pvl.load(f.read(RECORD_BYTES * (LABEL_RECORDS)), strict=False)


def parse_label(filename, full=False):
    """ Wraps forking paths for attached and detached PDS3 labels.
    """
    if filename.endswith('.fmt'):
        return pvl.load(filename)
    if not has_attached_label(filename):
        if os.path.exists(filename[: filename.rfind(".")] + ".LBL"):
            label = pvl.load(filename[: filename.rfind(".")] + ".LBL")
        elif os.path.exists(filename[: filename.rfind(".")] + ".lbl"):
            label = pvl.load(filename[: filename.rfind(".")] + ".lbl")
        elif os.path.exists(filename[: filename.rfind(".")] + ".xml"):
            # TODO: Make label data format consistent between PDS3 & 4
            label = pds4_tools.read(
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
    """ Defines a translation from PDS data types to Python data types.

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
    """ Placeholder function for the fact that PDS3 can contain multiple
    types of data (e.g. an image and a header) which are defined by
    'pointers' in the label. This should be dealt with at some point.
    """
    for k in parse_label(filename).keys():
        if k.startswith("^"):
            print(k)


def data_start_byte(label, pointer):
    """ Determine the first byte of the data in an IMG file from its pointer.
    """
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


def read_image(filename, pointer="IMAGE"):  # ^IMAGE
    """ Read a PDS IMG formatted file into an array.
    TODO: Check for and account for LINE_PREFIX.
    TODO: Check for and apply BIT_MASK.
    """
    label = parse_label(filename)
    if "IMAGE" in label.keys():
        BYTES_PER_PIXEL = int(label["IMAGE"]["SAMPLE_BITS"] / 8)
        DTYPE = sample_types(label["IMAGE"]["SAMPLE_TYPE"], BYTES_PER_PIXEL)
        nrows = label["IMAGE"]["LINES"]
        ncols = label["IMAGE"]["LINE_SAMPLES"]
        if "LINE_PREFIX_BYTES" in label["IMAGE"].keys():
            #print("Accounting for a line prefix.")
            prefix_cols = int(label["IMAGE"]["LINE_PREFIX_BYTES"] / BYTES_PER_PIXEL)
        else:
            prefix_cols = 0
        try:
            BANDS = label["IMAGE"]["BANDS"]
        except KeyError:
            BANDS = 1
        pixels = nrows * (ncols + prefix_cols) * BANDS
    else:
        print("*** IMG w/ old format attached label not currently supported.")
        print("\t{fn}".format(fn=filename))
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
        f.seek(data_start_byte(label, "^IMAGE"))
        image = np.array(struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL)))
        # Make sure that single-band images are 2-dim arrays.
        if BANDS == 1:
            image = image.reshape(nrows, (ncols + prefix_cols))
            if prefix_cols:
                # Ignore the prefix data, if any.
                # TODO: Also return the prefix
                prefix = image[:, :prefix_cols]
                if pointer == "LINE_PREFIX_TABLE":
                    return prefix
                image = image[:, prefix_cols:]
        else:
            image = image.reshape(BANDS, nrows, ncols)
    finally:
        f.close()
    #print("Displaying an image")
    #plt.figure(figsize=(4, 4))
    #plt.title(filename.split("/")[-1])
    #plt.xticks([])
    #plt.yticks([])
    if len(np.shape(image)) == 2:
        #plt.imshow(image, cmap="gray")
        pass
    elif len(np.shape(image)) == 3:
        if np.shape(image)[0] == 3:
            image = np.stack([image[0, :, :], image[1, :, :], image[2, :, :]], axis=2)
        if np.shape(image)[2] == 3:
            #plt.imshow(image)
            pass
    return image


def read_image_header(filename):  # ^IMAGE_HEADER
    label = parse_label(filename)
    try:
        with open(filename, "rb") as f:
            f.seek(data_start_byte(label, "^IMAGE_HEADER"))
            image_header = pvl.load(f.read(label["IMAGE_HEADER"]["BYTES"]))
        return image_header
    except:
        print("*** Unable to parse image header. ***")
        return


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


def read_line_prefix_table(filename):
    return read_image(filename, pointer="LINE_PREFIX_TABLE")


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


def parse_table_structure(filename, pointer="TABLE"):
    # Try to turn the TABLE definition into a column name / data type array.
    # Requires renaming some columns to maintain uniqueness.
    # Also requires unpacking columns that contain multiple entries.
    label = parse_label(filename)
    #if pointer=="TELEMETRY_TABLE":
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
                dt += [(name, sample_types(obj[1]["DATA_TYPE"], obj[1]["BYTES"]))]
    return np.dtype(dt)


def read_table(filename, pointer="TABLE"):  # ^TABLE
    label = parse_label(filename)
    dt = parse_table_structure(filename, pointer)
    return pd.DataFrame(
        np.fromfile(
            filename,
            dtype=dt,
            offset=data_start_byte(label, f"^{pointer}"),
            count=label[pointer]["ROWS"],
        )
    )


def read_engineering_table(filename):  # ^ENGINEERING_TABLE
    return read_table(filename, pointer="ENGINEERING_TABLE")


def read_measurement_table(filename):  # ^MEASUREMENT_TABLE
    return read_table(filename, pointer="MEASUREMENT_TABLE")


def read_telemetry_table(filename):  # ^TELEMETRY_TABLE
    return read_table(filename, pointer="TELEMETRY_TABLE")


def read_spectrum(filename):  # ^SPECTRUM
    print("*** SPECTRUM data not yet supported. ***")
    return


def read_jp2(filename):  # .JP2 extension
    # NOTE: These are the huge HIRISE images. It might be best to just
    #       leave thie capability to GDAL so that we don't have to bother
    #       with memory management.
    print("*** JP2 filetype not yet supported. ***")
    return


def read_mslmmm_compressed(filename):
    """ WARNING: Placeholder functionality.
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
    """ Read a PDS FITS file into an array.
    Return the data _and_ the label.
    """
    hdulist = pyfits.open(filename)
    data = hdulist[dim].data
    header = hdulist[dim].header
    hdulist.close()
    return (
        data,
        pds4_tools.read(filename.replace(".fits", ".xml"), quiet=True).label.to_dict(),
    )


def read_dat_pds4(filename, write_csv=False, quiet=True):
    """ Reads a PDS4 .dat format file, preserving column order and data type,
    except that byte order is switched to native if applicable. The .dat file
    and .xml label must exist in the same directory.
    Return the data _and_ the label.
    """
    if filename[-4:].lower() == ".dat":
        filename = filename[:-4] + ".xml"
    if filename[-4:].lower() != ".xml":
        raise TypeError("Unknown filetype: {ext}".format(ext=filename[-4:]))
    structures = pds4_tools.pds4_read(filename, quiet=quiet)
    dat_dict = OrderedDict({})
    for i in range(len(structures[0].fields)):
        name = structures[0].fields[i].meta_data["name"]
        dat_dtype = structures[0].fields[i].meta_data["data_type"]
        dtype = pds4_tools.reader.data_types.pds_to_numpy_type(dat_dtype)
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
    """ Converts a PDS4 file to a Comma Separated Value (CSV) file with
    the same base filename. The .dat file and .xml label must exist in
    the same directory.
    """
    _ = read_dat(filename, write_csv=True)


def unknown(filename):
    print("\t{fn}".format(fn=filename))
    return None, None


def read_file_name(filename):  # ^FILE_NAME
    # It just names itself.
    label = parse_label(filename)
    return label["^FILE_NAME"]


def read_description(filename):  # ^DESCRIPTION
    label = parse_label(filename)
    return label["^DESCRIPTION"]


def read_abdr_table(filename):  # ^ABDR_TABLE
    print("*** ADBR_TABLE not yet supported. ***")
    return


def read_array(filename):  # ^ARRAY
    print("*** ARRAY not yet supported. ***")
    return


def read_vicar_header(filename):  # ^VICAR_HEADER
    print("*** VICAR_HEADER not yet supported. ***")
    return


def read_vicar_extension_header(filename):  # ^VICAR_EXTENSION_HEADER
    print("*** VICAR_EXTENSION_HEADER not yet supported. ***")
    return


def read_history(filename):  # ^HISTORY
    print("*** HISTORY not yet supported. ***")
    return


def read_spectral_qube(filename):  # ^SPECTRAL_QUBE
    print("*** SPECTRAL_QUBE not yet supported. ***")
    return


def read_spacecraft_pointing_mode_desc(filename):  # ^SPACECRAFT_POINTING_MODE_DESC
    print("*** SPACECRAFT_POINTING_MODE_DESC not yet supported. ***")
    return


def read_odl_header(filename):  # ^ODL_HEADER
    print("*** ODL_HEADER not yet supported. ***")
    return


# def read_any_file(filename):
class data:
    def __init__(self, filename):
        pointer_to_function = {
            "^IMAGE": read_image,
            "^IMAGE_HEADER": read_image_header,
            "^TELEMETRY_TABLE": read_telemetry_table,
            "^BAD_DATA_VALUES_HEADER": read_bad_data_values_header,
            "^LINE_PREFIX_TABLE": read_line_prefix_table,
            "^HISTOGRAM": read_histogram,
            "^TABLE": read_table,
            "^MEASUREMENT_TABLE": read_measurement_table,
            "^ENGINEERING_TABLE": read_engineering_table,
            "^SPECTRUM": read_spectrum,
            "^FILE_NAME": read_file_name,
            "^DESCRIPTION": read_description,
            "^ABDR_TABLE": read_abdr_table,
            "^ARRAY": read_array,
            "^VICAR_HEADER": read_vicar_header,
            "^VICAR_EXTENSION_HEADER": read_vicar_extension_header,
            "^HISTORY": read_history,
            "^SPECTRAL_QUBE": read_spectral_qube,
            "^SPACECRAFT_POINTING_MODE_DESC": read_spacecraft_pointing_mode_desc,
            "^ODL_HEADER": read_odl_header,
            "MSLMMM-COMPRESSED": read_mslmmm_compressed,
            "JP2": read_jp2,
        }

        # Try PDS4 options
        if os.path.exists(filename[: filename.rfind(".")] + ".xml"):
            if filename.endswith(".dat"):
                self.dat = read_dat_pds4(filename)
                self.label = pds4_tools.read(
                    filename.replace(".dat", ".xml")
                ).label.to_dict()
                # print('DAT_PDS4',type(data))
        else:
            # Try PDS3 options
            setattr(self, "LABEL", parse_label(filename, full=True))
            label = parse_label(filename)
            try:
                pointers = [k for k in label.keys() if k[0] == "^"]
            except AttributeError:
                return
            try:
                if label["COMPRESSED_FILE"]["ENCODING_TYPE"] == "MSLMMM-COMPRESSED":
                    pointers += [label["COMPRESSED_FILE"]["ENCODING_TYPE"]]
            except:
                pass
            print(filename)
            if len(pointers):
                print("\t", pointers)
                for pointer in pointers:
                    try:
                        setattr(
                            self,
                            pointer[1:] if pointer.startswith("^") else pointer,
                            pointer_to_function[pointer](filename),
                        )
                    except KeyError:
                        pass
            elif ".JP2" in filename:
                print("*** Do not yet suport JP2 images. ***")
            else:
                print("\t*** No pointers. ***")


class read:
    def __init__(self, filename):
        self.filename = filename
        if filename.endswith(".JP2"):
            print("*** JP2 not yet supported. ***")
        else:
            self.data = data(filename)


class io:
    def __init__(cls):
        pass

    def read(filename):
        return read(filename)

