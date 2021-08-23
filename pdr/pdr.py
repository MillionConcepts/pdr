from functools import partial
from operator import contains
from pathlib import Path, PurePath
from typing import Mapping

import pds4_tools as pds4
from astropy.io import fits
import pvl
import numpy as np
import pandas as pd
import rasterio
import struct
import warnings

from dustgoggles.structures import dig_for_value
from pandas.errors import ParserError
from pvl.exceptions import ParseError
import Levenshtein as lev
import gzip
from zipfile import ZipFile
import bz2

# Define known data and label filename extensions
# This is used in order to search for companion data/metadata
from pdr.utils import get_pds3_pointers

label_extensions = (".xml", ".XML", ".lbl", ".LBL")
data_extensions = (
    ".img",
    ".IMG",
    ".fit",
    ".FIT",
    ".fits",
    ".FITS",
    ".dat",
    ".DAT",
    ".tab",
    ".TAB",
    ".QUB",
    # Compressed data... not PDS-compliant, but...
    ".gz",
    # And then the really unusual ones...
    ".n06",
    ".grn",  # Viking
    ".rgb",  # MER
    ".raw",
    ".RAW",  # Mars Express VMC
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
        "ASCII_REAL": f"S{SAMPLE_BYTES}",  # "Character string representing a real number"
        "ASCII_INTEGER": f"S{SAMPLE_BYTES}",  # ASCII character string representing an integer
        "DATE": f"S{SAMPLE_BYTES}",
        # "ASCII character string representing a date in PDS standard format" (1990-08-01T23:59:59)
        "CHARACTER": f"S{SAMPLE_BYTES}",  # ASCII character string
    }[SAMPLE_TYPE]


# TODO: watch out for cases in which individual products may be scattered
#  across multiple HDUs. I'm not certain where these are, and I think it is
#  technically illegal in every PDS3 version, but I'm almost certain they
#  exist anyway.
def pointer_to_fits_key(pointer, hdulist):
    """In some data sets with FITS, the PDS3 object names and FITS object names
    are not identical. This function attempts to use Levenshtein "fuzzy matching" to
    identify the correlation between the two. It is not guaranteed to be correct! And
    special case handling might be required in the future."""

    if pointer in ("IMAGE", "TABLE", None, ""):
        # TODO: sometimes the primary HDU contains _just_ a header.
        #  (e.g., GALEX raw6, which is not in scope, but I'm sure something in
        #  the PDS does this awful thing too.) it might be a good idea to have
        #  a heuristic for, when we are implicitly looking for data, walking
        #  forward until we find a HDU that actually has something in it...
        #  or maybe just populating multiple keys from the HDU names.
        return 0
    levratio = [
        lev.ratio(i[1].lower(), pointer.lower())
        for i in hdulist.info(output=False)
    ]
    return levratio.index(max(levratio))


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


class Data:
    def __init__(self, fn):
        # TODO: products can have multiple data files, and in some cases one
        #  of those data files also contains the attached label -- basically,
        #  these can't be strings
        self.filename = fn
        self.labelname = None
        # index of all of the pointers to data
        self.index = []
        # Attempt to identify and assign the data and label files
        if fn.endswith(label_extensions):
            setattr(self, "labelname", fn)
            for dext in data_extensions:
                if Path(
                    filename := fn.replace(Path(fn).suffix, dext)
                ).exists():
                    setattr(self, "filename", filename)
                    break
        elif fn.endswith(data_extensions):
            setattr(self, "filename", fn)
            for lext in label_extensions:
                if Path(
                    labelname := fn.replace(Path(fn).suffix, lext)
                ).exists():
                    setattr(self, "labelname", labelname)
                    break
        else:
            warnings.warn(f"Unknown filetype: {Path(fn).suffix}")
            setattr(self, "filename", fn)
            # TODO: Can you have an unknown filetype and a known label? Should we define attribute labelname here? I
            #  guess you couldn't know if it was a file or a label because the extension didn't fit...So this will
            #  break with all M3 data or anything else that uses weird extensions...

        # Just use pds4_tools if this is a PDS4 file
        # TODO: redundant and confusing w/read_label
        try:
            data = pds4.read(self.labelname, quiet=True)
            for struct in data.structures:
                setattr(self, struct.id.replace(" ", "_"), struct.data)
                self.index += [struct.id.replace(" ", "_")]
            return
        except:
            # Presume that this is not a PDS4 file
            pass

        LABEL = self.read_label()
        if LABEL:
            setattr(self, "LABEL", LABEL)
            self.index += ["LABEL"]
            pointer_targets = get_pds3_pointers(LABEL)
            setattr(self, "pointers", [p_t[0] for p_t in pointer_targets])
            self.index += [p.strip("^") for p in self.pointers]
            try:
                _ = [
                    setattr(
                        self,
                        pointer[1:] if pointer.startswith("^") else pointer,
                        self.pointer_to_function(pointer)(
                            pointer=pointer.strip("^")
                        ),
                    )
                    for pointer in self.pointers
                ]
            except:  # no pointers defined
                raise

        # Sometimes images do not have explicit pointers, so just always try
        #  to read an image out of the file no matter what.
        # Must exclude QUB files or it will reread them as an IMAGE
        if not any(
            "IMAGE" in key for key in self.index
        ) and not self.filename.lower().endswith("qub"):
            try:
                if self.looks_like_a_fits_file():
                    image = self.handle_fits_file()
                else:
                    # TODO: this will presently break if passed an unlabeled
                    #  image file. read_image() should probably be made more
                    #  permissive in some way to handle this, or we should at
                    #  least give a useful error message.
                    image = self.read_image()
                if image is not None:
                    setattr(self, "IMAGE", image)
                    self.index += ["IMAGE"]
            except:
                pass

    def read_label(self):
        """Attempts to read the data label, checking first whether this is a
        PDS4 file, then whether it has a detached label, then whether it
        has an attached label. Returns None if all of these attempts are
        unsuccessful.
        """
        if self.labelname:  # a detached label exists
            if Path(self.labelname).suffix.lower() == ".xml":
                return pds4.read(self.labelname, quiet=True).label.to_dict()
            return pvl.load(self.labelname)
        try:

            return pvl.load(
                decompress(self.filename)
            )  # check for an attached label
        except:
            return

    def pointer_to_function(self, pointer):
        # send both compressed and uncompressed fits files to astropy.io.fits
        # TODO, maybe: dispatch to decompress() for weirdo compression formats,
        #  but possibly not right here?
        if self.looks_like_a_fits_file():
            return self.handle_fits_file
        if "DESC" in pointer:  # probably points to a reference file
            return self.tbd
        elif "HEADER" in pointer:
            return self.read_header
        elif ("IMAGE" in pointer) or ("QUB" in pointer):
            return self.read_image
        elif "LINE_PREFIX_TABLE" in pointer:
            return self.tbd
        elif "TABLE" in pointer:
            return self.read_table
        return self.tbd

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
        try:
            if "INSTRUMENT_ID" in self.LABEL.keys():
                if (
                    self.LABEL["INSTRUMENT_ID"] == "M3"
                    and self.LABEL["PRODUCT_TYPE"] == "RAW_IMAGE"
                ):
                    userasterio = False  # because rasterio doesn't read M3 L0 data correctly
        except (KeyError, AttributeError):
            pass
        if pointer == "IMAGE" or self.filename.lower().endswith("qub"):
            try:
                if not userasterio:
                    raise
                dataset = rasterio.open(self.filename)
                if len(dataset.indexes) == 1:
                    return dataset.read()[
                        0, :, :
                    ]  # Make 2D images actually 2D
                else:
                    return dataset.read()
            except rasterio.errors.RasterioIOError:
                pass
        block = self.labelblock(pointer)
        if block:
            if pointer == "QUBE":  # ISIS2 QUBE format
                BYTES_PER_PIXEL = int(block["CORE_ITEM_BYTES"])  # / 8)
                DTYPE = sample_types(block["CORE_ITEM_TYPE"], BYTES_PER_PIXEL)
                nrows = block["CORE_ITEMS"][2]
                ncols = block["CORE_ITEMS"][0]
                prefix_cols, prefix_bytes = 0, 0
                # TODO: Handle the QUB suffix data
                BANDS = block["CORE_ITEMS"][1]
                band_storage_type = "ISIS2_QUBE"
            else:
                BYTES_PER_PIXEL = int(block["SAMPLE_BITS"] / 8)
                DTYPE = sample_types(block["SAMPLE_TYPE"], BYTES_PER_PIXEL)
                nrows = block["LINES"]
                ncols = block["LINE_SAMPLES"]
                if "LINE_PREFIX_BYTES" in block.keys():
                    prefix_cols = int(
                        block["LINE_PREFIX_BYTES"] / BYTES_PER_PIXEL
                    )
                    prefix_bytes = prefix_cols * BYTES_PER_PIXEL
                else:
                    prefix_cols = 0
                    prefix_bytes = 0
                try:
                    BANDS = block["BANDS"]
                    band_storage_type = block["BAND_STORAGE_TYPE"]
                except KeyError:
                    BANDS = 1
                    band_storage_type = None
            pixels = nrows * (ncols + prefix_cols) * BANDS
            # TODO: handle cases where image blocks are nested inside file
            #  blocks and info such as RECORD_BYTES is found only there
            #  -- previously I did this by making pointers lists, but this may
            #  be an unwieldy solution
            start_byte = self.data_start_byte(pointer)
        elif (
            self.LABEL["INSTRUMENT_ID"] == "M3"
            and self.LABEL["PRODUCT_TYPE"] == "RAW_IMAGE"
        ):
            # This is handling the special case of Chandrayaan M3 L0 data, which are
            # in a deprecated ENVI format that uses "line prefixes"
            BYTES_PER_PIXEL = int(
                self.LABEL["L0_FILE"]["L0_IMAGE"]["SAMPLE_BITS"] / 8
            )
            DTYPE = sample_types(
                self.LABEL["L0_FILE"]["L0_IMAGE"]["SAMPLE_TYPE"],
                BYTES_PER_PIXEL,
            )
            nrows = self.LABEL["L0_FILE"]["L0_IMAGE"]["LINES"]
            ncols = self.LABEL["L0_FILE"]["L0_IMAGE"]["LINE_SAMPLES"]
            prefix_bytes = int(
                self.LABEL["L0_FILE"]["L0_IMAGE"]["LINE_PREFIX_BYTES"]
            )
            prefix_cols = (
                prefix_bytes / BYTES_PER_PIXEL
            )  # M3 has a prefix, but it's not image-shaped
            BANDS = self.LABEL["L0_FILE"]["L0_IMAGE"]["BANDS"]
            pixels = nrows * (ncols + prefix_cols) * BANDS
            start_byte = 0
            band_storage_type = self.LABEL["L0_FILE"]["L0_IMAGE"][
                "BAND_STORAGE_TYPE"
            ]
        else:
            return None

        fmt = "{endian}{pixels}{fmt}".format(
            endian=DTYPE[0], pixels=pixels, fmt=DTYPE[-1]
        )
        try:  # a little decision tree to seamlessly deal with compression
            if isinstance(self.labelget(f"^{pointer}"), str):
                f = decompress(
                    self.get_relative_path(self.labelget(f"^{pointer}"))
                )
            else:
                f = decompress(self.filename)
            # Make sure that single-band images are 2-dim arrays.
            f.seek(start_byte)
            prefix = None
            if BANDS == 1:
                image = np.array(
                    struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL))
                )
                image = image.reshape(nrows, (ncols + prefix_cols))
                if prefix_cols:
                    # Ignore the prefix data, if any.
                    # TODO: Also return the prefix
                    prefix = image[:, :prefix_cols]
                    if pointer == "LINE_PREFIX_TABLE":
                        return prefix
                    image = image[:, prefix_cols:]
            # TODO: I think the ndarray.reshape call signatures in the next three
            #  cases may be wrong.
            elif band_storage_type == "BAND_SEQUENTIAL":
                image = np.array(
                    struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL))
                )
                image = image.reshape(BANDS, nrows, (ncols + prefix_cols))
            elif band_storage_type == "LINE_INTERLEAVED":
                pixels_per_frame = BANDS * ncols
                endian, length = (DTYPE[0], DTYPE[-1])
                fmt = f"{endian}{pixels_per_frame}{length}"
                image, prefix = [], []
                for _ in np.arange(nrows):
                    prefix.append(f.read(prefix_bytes))
                    frame = np.array(
                        struct.unpack(
                            fmt, f.read(pixels_per_frame * BYTES_PER_PIXEL)
                        )
                    ).reshape(BANDS, ncols)
                    image.append(frame)
                    del frame
                image = np.swapaxes(
                    np.stack([frame for frame in image], axis=2), 1, 2
                )
            else:
                warnings.warn(
                    f"Unknown BAND_STORAGE_TYPE={band_storage_type}. "
                    f"Guessing BAND_SEQUENTIAL."
                )
                image = np.array(
                    struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL))
                )
                image = image.reshape(BANDS, nrows, (ncols + prefix_cols))
        except:
            raise
        finally:
            f.close()
        if "PREFIX" in pointer:
            return prefix
        return image

    def read_table_structure(self, pointer):
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
        # TODO: this will generally fail for PDS4 --
        #  but maybe it never needs to be called?
        block = dig_for_value(self.LABEL, pointer)
        if "^STRUCTURE" in block:
            if Path(
                fmtpath := self.filename.replace(
                    PurePath(self.filename).name, block["^STRUCTURE"]
                )
            ).exists():
                structure = pvl.load(fmtpath)
            elif Path(
                fmtpath := self.filename.replace(
                    PurePath(self.filename).name, block["^STRUCTURE"].lower()
                )
            ).exists():
                structure = pvl.load(fmtpath)
            else:
                warnings.warn(
                    f'Unable to locate external table format file:\n\t{block["^STRUCTURE"]}'
                )
                return None
            # print(f"Reading external format file:\n\t{fmtpath}")
        else:
            structure = block
        fmtdef = pd.DataFrame()
        for i, k in enumerate(structure.keys()):
            obj = {}  # reinitialize... probably unnecessary
            objdef = structure[
                i
            ]  # use the index because the keys are not unique
            if objdef[0] == "COLUMN":
                if objdef[1]["NAME"] == "RESERVED":
                    name = "RESERVED_" + str(objdef[1]["START_BYTE"])
                else:
                    name = objdef[1]["NAME"]
                try:  # Some "columns" contain a lot of columns
                    for n in range(objdef[1]["ITEMS"]):
                        obj = dict(objdef[1])
                        obj["NAME"] = f"{name}_{n}"  # rename duplicate columns
                except KeyError:
                    obj = dict(objdef[1])
                fmtdef = fmtdef.append(obj, ignore_index=True)
        return fmtdef

    def parse_table_structure(self, pointer):
        """Generate an dtype array to later pass to numpy.fromfile
        to unpack the table data according to the format given in the
        label.
        """
        fmtdef = self.read_table_structure(pointer)
        dt = []
        if fmtdef is None:
            return np.dtype(dt), fmtdef
        for i in range(len(fmtdef)):
            try:
                data_type = sample_types(
                    fmtdef.iloc[i].DATA_TYPE, int(fmtdef.iloc[i].BYTES)
                )
            except KeyError:
                raise KeyError(
                    f"{fmtdef.iloc[i].DATA_TYPE} "
                    f"is not a currently-supported data type."
                )
            dt += [(fmtdef.iloc[i].NAME, data_type)]
            try:
                allocation = (
                    fmtdef.iloc[i + 1].START_BYTE - fmtdef.iloc[i].START_BYTE
                )
            except IndexError:
                # The +1 is for the carriage return... these files are badly formatted...
                allocation = (
                    dig_for_value(self.LABEL, pointer)["ROW_BYTES"]
                    - fmtdef.iloc[i].START_BYTE
                    + 1
                )
            if allocation > fmtdef.iloc[i].BYTES:
                dt += [
                    (
                        f"PLACEHOLDER_{i}",
                        sample_types(
                            "CHARACTER", int(allocation - fmtdef.iloc[i].BYTES)
                        ),
                    )
                ]

        return np.dtype(dt), fmtdef

    def read_table(self, pointer="TABLE"):
        """Read a table. Will first attempt to parse it as generic CSV
        and then fall back to parsing it based on the label format definition.
        """
        try:
            dt, fmtdef = self.parse_table_structure(pointer)
        except KeyError:
            warnings.warn(f"Unable to find or parse {pointer}")
            return self.labelget(pointer)
        # TODO: mess with this control flow to allow graceful failure in
        #  format-finding but also passing names to read_csv
        # Check if this is just a CSV file
        try:
            return pd.read_csv(self.filename, names=fmtdef.NAME.tolist())
        # TODO: write read_csv as it appears to not be in the code
        except (UnicodeDecodeError, AttributeError, ParserError):
            pass  # This is not parseable as a CSV file
        table = pd.DataFrame(
            np.fromfile(
                self.filename,
                dtype=dt,
                offset=self.data_start_byte(pointer),
                count=self.labelblock(pointer)["ROWS"],
            )
            .byteswap()
            .newbyteorder()  # Pandas doesn't do non-native endian
        )
        try:
            # If there were any cruft "placeholder" columns, discard them
            return table.drop(
                [k for k in table.keys() if "PLACEHOLDER" in k], axis=1
            )
        except TypeError:  # Failed to read the table
            return self.labelget(pointer)

    def read_header(self, pointer="HEADER"):
        """Attempt to read a file header."""
        try:
            return pvl.load(self.filename)
        except:
            warnings.warn(f"Unable to find or parse {pointer}")
            return self.labelget(pointer)

    def handle_fits_file(self, pointer=""):
        """
        This function attempts to read all FITS files, compressed or
        uncompressed, with astropy.io.fits. Files with 'HEADER' pointer
        return the header, all others return data.
        """
        try:
            hdulist = fits.open(self.filename)
            if "HEADER" in pointer:
                return hdulist[pointer_to_fits_key(pointer, hdulist)].header
            return hdulist[pointer_to_fits_key(pointer, hdulist)].data
        except:
            # TODO: assuming this does not need to be specified as f-string
            #  (like in read_header/tbd) -- maybe! must determine and specify
            #  what cases this exception was needed to handle
            return self.labelget(pointer)

    def looks_like_a_fits_file(self):
        is_fits_extension = partial(contains, [".fits", ".fit"])
        return any(
            map(is_fits_extension, Path(self.filename.lower()).suffixes)
        )

    def tbd(self, pointer=""):
        """This is a placeholder function for pointers that are
        not explicitly supported elsewhere. It throws a warning and
        passes just the value of the pointer."""
        warnings.warn(f"The {pointer} pointer is not yet fully supported.")
        return self.labelget(pointer)

    def labelget(self, text):
        """
        get the first value from this object's label whose key exactly matches
        `text`. if only_block is passed, will only return this value if it's a
        mapping (e.g. nested PVL block) and otherwise returns key from top
        label level. TODO: very crude. needs to work with XML.
        """
        return dig_for_value(self.LABEL, text)

    def labelblock(self, text):
        """
        get the first value from this object's label whose key
        exactly matches `text` iff it is a mapping (e.g. nested PVL block);
        otherwise, returns the label as a whole.
        TODO: very crude. needs to work with XML.
        """
        what_got_dug = dig_for_value(self.LABEL, text)
        if not isinstance(what_got_dug, Mapping):
            return self.LABEL
        return what_got_dug

    def data_start_byte(self, pointer):
        """Determine the first byte of the data in an IMG file from its
        pointer."""
        # TODO: hacky, make this consistent -- actually this pointer notation
        #  is hacky across the module, primarily because it's horrible in the
        #  first place :shrug: -- previously I did this by making pointers
        #  lists, but this may be unwieldy
        target = self.labelget(pointer)
        if isinstance(target, Mapping):
            target = self.labelget(f"^{pointer}")
        labelblock = self.labelblock(pointer)
        if isinstance(target, int):
            return labelblock["RECORD_BYTES"] * (labelblock[pointer] - 1)
        elif isinstance(target, list):
            if isinstance(target[0], int):
                return target[0]
            elif isinstance(target[-1], int):
                return labelblock["RECORD_BYTES"] * (target[-1] - 1)
            else:
                return 0
        elif type(target) is str:
            return 0
        else:
            try:
                # This is to handle the PVL "Quantity" object... should
                # probably
                # do this better
                return target.value
            except:
                raise ParseError(f"Unknown data pointer format: {target}")

    # The following two functions make this object act sort of dict-like
    #  in useful ways for data exploration.
    def keys(self):
        # Returns the keys for observational data and metadata objects
        return self.index

    def get_relative_path(self, file):
        if self.labelname:
            return str(Path(Path(self.labelname).parent, file))
        elif self.filename:
            return str(Path(Path(self.filename).parent, file))
        else:
            return file

    # Make it possible to call the object like a dict
    def __getitem__(self, item):
        return getattr(self, item)

    # TODO, maybe: do __str__ and __repr__ better

    def __repr__(self):
        return f"pdr.Data({self.filename})\nkeys={self.keys()}"

    def __str__(self):
        return self.__repr__()

    def __len__(self):
        return len(self.index)

    def __iter__(self):
        for key in self.keys():
            yield self[key]
