from pathlib import Path, PurePath
import pds4_tools as pds4
from astropy.io import fits
import pvl
import numpy as np
import pandas as pd
import rasterio
import struct
import warnings
from pandas.errors import ParserError
from pvl.exceptions import ParseError
import Levenshtein as lev
import gzip
from zipfile import ZipFile
import bz2

# Define known data and label filename extensions
# This is used in order to search for companion data/metadata
label_extensions = ('.xml','.XML','.lbl','.LBL')
data_extensions = ('.img','.IMG',
                   '.fit','.FIT','.fits','.FITS',
                   '.dat','.DAT','.tab','.TAB',
                   '.QUB',
                   # Compressed data... not PDS-compliant, but...
                   '.gz',
                   # And then the really unusual ones...
                   '.n06', '.grn', # Viking
                   '.rgb', # MER
                   '.raw','.RAW', # Mars Express VMC
                   )

def sample_types(SAMPLE_TYPE, SAMPLE_BYTES):
    """Defines a translation from PDS data types to Python data types,
    using both the type and bytes specified (because the mapping to type
    is not consistent across PDS3).
    """
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
        "ASCII_REAL":f"S{SAMPLE_BYTES}", # "Character string representing a real number"
        "ASCII_INTEGER":f"S{SAMPLE_BYTES}", # ASCII character string representing an integer
        "DATE":f"S{SAMPLE_BYTES}", # "ASCII character string representing a date in PDS standard format" (1990-08-01T23:59:59)
        "CHARACTER":f"S{SAMPLE_BYTES}", # ASCII character string
    }[SAMPLE_TYPE]

def pointer_to_fits_key(pointer,hdu):
    """ In some data sets with FITS, the PDS3 object names and FITS object names
    are not identical. This function attempts to use Levenshtein "fuzzy matching" to
    identify the correlation between the two. It is not guaranteed to be correct! And
    special case handling might be required in the future. """
    if pointer=='IMAGE' or pointer=='TABLE':
        return 0
    levratio = [lev.ratio(i[1].lower(),pointer.lower()) for i in hdu.info(output=False)]
    return levratio.index(max(levratio))

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
        try:
            # This is to handle the PVL "Quantity" object... should probably do this better
            return label[pointer].value
        except:
            raise ParseError(f"Unknown data pointer format: {label[pointer]}")

def decompress(filename):
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
    return f

def read_label(self):
    """Attempt to read the data label, checking first whether this is a
    PDS4 file, then whether it has a detached label, then whether it
    has an attached label. Returns None if all of these attempts are
    unsuccessful.
    """
    if 'labelname' in dir(self): # a detached label exists
        if Path(self.labelname).suffix.lower()=='.xml':
            return pds4.read(
                self.labelname, quiet=True
            ).label.to_dict()
        return pvl.load(self.labelname)
    try:

        return pvl.load(decompress(self.filename)) # check for an attached label
    except:
        return

def read_image(self, pointer="IMAGE", userasterio=True):  # ^IMAGE
    """Read a PDS IMG formatted file into an array. Defaults to using
    `rasterio`, and then tries to parse the file directly.
    """
    # TODO: Check for and account for LINE_PREFIX.
    # TODO: Check for and apply BIT_MASK.
    """
    rasterio will read an ENVI file if the HDR metadata is present...
    However, it seems to read M3 L0 images incorrectly because it does
    not account for the L0_LINE_PREFIX_TABLE. So I am deprecating
    the use of rasterio until I can figure out how to produce consistent
    output."""
    if (self.filename.lower().endswith('.fits') or
            self.filename.lower().endswith('.fit')):
        try:  # Is it a FITS file?
            hdu = fits.open(self.filename)
            return hdu[pointer_to_fits_key(pointer, hdu)].data
        except:
            pass
    try:
        if 'INSTRUMENT_ID' in self.LABEL.keys():
            if (self.LABEL['INSTRUMENT_ID'] == "M3" and self.LABEL['PRODUCT_TYPE'] == "RAW_IMAGE"):
                userasterio=False # because rasterio doesn't read M3 L0 data correctly
    except:
        pass
    if pointer=='IMAGE' or self.filename.lower().endswith('qub'):
        try:
            if not userasterio:
                raise
            dataset = rasterio.open(self.filename)
            if len(dataset.indexes)==1:
                return dataset.read()[0,:,:] # Make 2D images actually 2D
            else:
                return dataset.read()
        except rasterio.errors.RasterioIOError:
            pass
    if pointer in self.LABEL.keys():
        if pointer=='QUBE': # ISIS2 QUBE format
            BYTES_PER_PIXEL = int(self.LABEL[pointer]["CORE_ITEM_BYTES"])# / 8)
            DTYPE = sample_types(self.LABEL[pointer]["CORE_ITEM_TYPE"], BYTES_PER_PIXEL)
            nrows = self.LABEL[pointer]["CORE_ITEMS"][2]
            ncols = self.LABEL[pointer]["CORE_ITEMS"][0]
            prefix_cols,prefix_bytes = 0,0
            # TODO: Handle the QUB suffix data
            BANDS = self.LABEL[pointer]["CORE_ITEMS"][1]
            band_storage_type = "ISIS2_QUBE"
        else:
            BYTES_PER_PIXEL = int(self.LABEL[pointer]["SAMPLE_BITS"] / 8)
            DTYPE = sample_types(self.LABEL[pointer]["SAMPLE_TYPE"], BYTES_PER_PIXEL)
            nrows = self.LABEL[pointer]["LINES"]
            ncols = self.LABEL[pointer]["LINE_SAMPLES"]
            if "LINE_PREFIX_BYTES" in self.LABEL[pointer].keys():
                prefix_cols = int(self.LABEL[pointer]["LINE_PREFIX_BYTES"] / BYTES_PER_PIXEL)
                prefix_bytes = prefix_cols * BYTES_PER_PIXEL
            else:
                prefix_cols = 0
                prefix_bytes = 0
            try:
                BANDS = self.LABEL[pointer]["BANDS"]
                band_storage_type = self.LABEL[pointer]["BAND_STORAGE_TYPE"]
            except KeyError:
                BANDS = 1
                band_storage_type = None
        pixels = nrows * (ncols + prefix_cols) * BANDS
        start_byte = data_start_byte(self.LABEL, f"^{pointer}")
    elif self.LABEL["INSTRUMENT_ID"] == "M3" and self.LABEL["PRODUCT_TYPE"] == "RAW_IMAGE":
        # This is handling the special case of Chandrayaan M3 L0 data, which are
        # in a deprecated ENVI format that uses "line prefixes"
        BYTES_PER_PIXEL = int(self.LABEL["L0_FILE"]["L0_IMAGE"]["SAMPLE_BITS"] / 8)
        DTYPE = sample_types(
            self.LABEL["L0_FILE"]["L0_IMAGE"]["SAMPLE_TYPE"], BYTES_PER_PIXEL
        )
        nrows = self.LABEL["L0_FILE"]["L0_IMAGE"]["LINES"]
        ncols = self.LABEL["L0_FILE"]["L0_IMAGE"]["LINE_SAMPLES"]
        prefix_bytes = int(self.LABEL["L0_FILE"]["L0_IMAGE"]["LINE_PREFIX_BYTES"])
        prefix_cols = (
            prefix_bytes / BYTES_PER_PIXEL
        )  # M3 has a prefix, but it's not image-shaped
        BANDS = self.LABEL["L0_FILE"]["L0_IMAGE"]["BANDS"]
        pixels = nrows * (ncols + prefix_cols) * BANDS
        start_byte = 0
        band_storage_type = self.LABEL["L0_FILE"]["L0_IMAGE"]["BAND_STORAGE_TYPE"]
    else:
        return None

    fmt = "{endian}{pixels}{fmt}".format(endian=DTYPE[0], pixels=pixels, fmt=DTYPE[-1])
    try:  # a little decision tree to seamlessly deal with compression
        f = decompress(self.filename)
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
            warnings.warn(f"Unknown BAND_STORAGE_TYPE={band_storage_type}. Guessing BAND_SEQUENTIAL.")
            image = np.array(struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL)))
            image = image.reshape(BANDS, nrows, (ncols + prefix_cols))
    except:
        raise
    finally:
        f.close()
    if "PREFIX" in pointer:
        return prefix
    return image

def read_table_structure(self, pointer='TABLE'):
    """Try to turn the TABLE definition into a column name / data type array.
    Requires renaming some columns to maintain uniqueness.
    Also requires unpacking columns that contain multiple entries.
    Also requires adding "placeholder" entries for undefined data (e.g. commas
    in cases where the allocated bytes is larger than given by BYTES, so we
    need to read in the "placeholder" space and then discard it later).

    If the table format is defined in an external FMT file, then this will
    attempt to locate it in the same directory as the data / label, and throw
    an error if it's not there. TODO: Grab external format files as needed.
    """
    if "^STRUCTURE" in self.LABEL[pointer]:
        if Path(fmtpath:= self.filename.replace(
            PurePath(self.filename).name,
            self.LABEL[pointer]['^STRUCTURE'])).exists():
                LABEL = pvl.load(fmtpath)
        elif Path(fmtpath:= self.filename.replace(
            PurePath(self.filename).name,
            self.LABEL[pointer]['^STRUCTURE'].lower())).exists():
                LABEL = pvl.load(fmtpath)
        else:
            warnings.warn(f'Unable to locate external table format file:\n\t{self.LABEL[pointer]["^STRUCTURE"]}')
            return None
        #print(f"Reading external format file:\n\t{fmtpath}")
    else:
        LABEL = self.LABEL[pointer]
    fmtdef = pd.DataFrame()
    for i, k in enumerate(LABEL.keys()):
        obj = {}  # reinitialize... probably unnecessary
        objdef = LABEL[i]  # use the index because the keys are not unique
        if objdef[0] == 'COLUMN':
            if objdef[1]["NAME"] == "RESERVED":
                name = "RESERVED_" + str(objdef[1]["START_BYTE"])
            else:
                name = objdef[1]["NAME"]
            try:  # Some "columns" contain a lot of columns
                for n in range(objdef[1]["ITEMS"]):
                    obj = dict(objdef[1])
                    obj['NAME'] = f"{name}_{n}"  # rename duplicate columns
            except KeyError:
                obj = dict(objdef[1])
            fmtdef = fmtdef.append(obj, ignore_index=True)
    return fmtdef

def parse_table_structure(self, pointer="TABLE"):
    """Generate an dtype array to later pass to numpy.fromfile
    to unpack the table data according to the format given in the
    label.
    """
    fmtdef = read_table_structure(self, pointer=pointer)
    dt = []
    if fmtdef is None:
        return np.dtype(dt), fmtdef
    for i in range(len(fmtdef)):
        dt += [(fmtdef.iloc[i].NAME,
                sample_types(fmtdef.iloc[i].DATA_TYPE, int(fmtdef.iloc[i].BYTES)))]
        try:
            allocation = fmtdef.iloc[i + 1].START_BYTE - fmtdef.iloc[i].START_BYTE
        except IndexError:
            # The +1 is for the carriage return... these files are badly formatted...
            allocation = self.LABEL[pointer]['ROW_BYTES'] - fmtdef.iloc[i].START_BYTE + 1
        if allocation > fmtdef.iloc[i].BYTES:
            dt += [(f'PLACEHOLDER_{i}',
                    sample_types('CHARACTER',int(allocation - fmtdef.iloc[i].BYTES)))]

    return np.dtype(dt), fmtdef

def read_table(self, pointer="TABLE"):
    """ Read a table. Will first attempt to parse it as generic CSV
    and then fall back to parsin git based on the label format definition.
    """
    if (self.filename.lower().endswith('.fits') or
            self.filename.lower().endswith('.fit')):
        try:  # Is it a FITS file?
            hdu = fits.open(self.filename)
            return hdu[pointer_to_fits_key(pointer, hdu)].data
        except:
            pass
    dt, fmtdef = parse_table_structure(self, pointer=pointer)
    try:
        # Check if this is just a CSV file
        return pd.read_csv(self.filename,
                           names=fmtdef.NAME.tolist())
    # TODO: write read_csv as it appears to not be in the code
    except (UnicodeDecodeError, AttributeError, ParserError):
        pass # This is not parseable as a CSV file
    table = pd.DataFrame(
        np.fromfile(
            self.filename,
            dtype=dt,
            offset=data_start_byte(self.LABEL, f"^{pointer}"),
            count=self.LABEL[pointer]["ROWS"],
        ).byteswap().newbyteorder()  # Pandas doesn't do non-native endian
    )
    try:
        # If there were any cruft "placeholder" columns, discard them
        return table.drop([k for k in table.keys() if 'PLACEHOLDER' in k],axis=1)
    except TypeError: # Failed to read the table
        return self.LABEL[pointer]

def read_header(self, pointer="HEADER"):
    """ Attempt to read a file header. """
    if (self.filename.lower().endswith('.fits') or
            self.filename.lower().endswith('.fit')):
        try: # Is it a FITS file?
            hdu = fits.open(self.filename)
            return hdu[pointer_to_fits_key(pointer,hdu)].header
        except:
            pass
    try:
        return pvl.load(self.filename)
    except:
        warnings.warn(f"Unable to find or parse {pointer}")
        return self.LABEL[f"^{pointer}"]

def tbd(self, pointer=""):
    """ This is a placeholder function for pointers that are
    not explicitly supported elsewhere. It throws a warning and
    passes just the value of the pointer."""
    if (self.filename.lower().endswith('.fits') or
            self.filename.lower().endswith('.fit')):
        try:  # Is it a FITS file?
            hdu = fits.open(self.filename)
            return hdu[pointer_to_fits_key(pointer, hdu)].data
        except:
            pass
    warnings.warn(f"The {pointer} pointer is not yet fully supported.")
    return self.LABEL[f"^{pointer}"]

def pointer_to_function(pointer):
    if 'DESC' in pointer: # probably points to a reference file
        return tbd
    elif 'HEADER' in pointer:
        return read_header
    elif ('IMAGE' in pointer) or ('QUB' in pointer):
        return read_image
    elif 'LINE_PREFIX_TABLE' in pointer:
        return tbd
    elif 'TABLE' in pointer:
        return read_table
    else:
        return tbd

class Data:
    def __init__(self, fn):
        index = []
        # Attempt to identify and assign the data and label files
        if fn.endswith(label_extensions):
            setattr(self, "labelname", fn)
            for dext in data_extensions:
                if Path(filename:=fn.replace(Path(fn).suffix,dext)).exists():
                    setattr(self, "filename", filename)
                    break
        elif fn.endswith(data_extensions):
            setattr(self, "filename", fn)
            for lext in label_extensions:
                if Path(labelname:=fn.replace(Path(fn).suffix, lext)).exists():
                    setattr(self, "labelname", labelname)
                    break
        else:
            warnings.warn(f"Unknown filetype: {Path(fn).suffix}")
            setattr(self, 'filename', fn)

        # Just use pds4_tools if this is a PDS4 file
        try:
            data = pds4.read(self.labelname,quiet=True)
            for struct in data.structures:
                setattr(self, struct.id.replace(' ','_'), struct.data)
                index += [struct.id.replace(' ','_')]
            setattr(self, "index", index)
            return
        except:
            # Presume that this is not a PDS4 file
            pass

        LABEL = read_label(self)
        if LABEL:
            setattr(self, "LABEL", LABEL)
            index += ['LABEL']
            setattr(self, "pointers", [k for k in self.LABEL.keys() if k[0] == "^"])
            index += [p.strip('^') for p in self.pointers]
            try:
                _ = [
                    setattr(
                        self,
                        pointer[1:] if pointer.startswith("^") else pointer,
                        pointer_to_function(pointer)(self, pointer=pointer.strip("^")),
                    )
                    for pointer in self.pointers
                ]
            except: # no pointers defined
                raise

        # Sometimes images do not have explicit pointers, so just always try
        #  to read an image out of the file no matter what.
        # Must exclude QUB files or it will reread them as an IMAGE
        if not "IMAGE" in index and not self.filename.lower().endswith('qub'):
            try:
                image = read_image(self)
                if not image is None:
                    setattr(self, "IMAGE", image)
                    index+=['IMAGE']
            except:
                pass

        # Create an index of all of the pointers to data
        setattr(self,"index",index)

    # The following two functions make this object act sort of dict-like
    #  in useful ways for data exploration.
    def keys(self):
        # Returns the keys for observational data and metadata objects
        return self.index

    # Make it possible to call the object like a dict
    def __getitem__(self, item):
         return getattr(self, item)


