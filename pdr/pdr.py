import bz2
import gzip
import struct
import warnings
from pathlib import Path, PurePath
from typing import Mapping, Optional, Union
from zipfile import ZipFile

import Levenshtein as lev
import numpy as np
import pandas as pd
import pds4_tools as pds4
import pvl
import rasterio
from astropy.io import fits
from dustgoggles.structures import dig_for_value
from pandas.errors import ParserError
from pvl.exceptions import ParseError
from rasterio.errors import NotGeoreferencedWarning

from pdr.browsify import browsify

from pdr.datatypes import (
    LABEL_EXTENSIONS,
    DATA_EXTENSIONS,
    sample_types,
    PDS3_CONSTANT_NAMES,
    IMPLICIT_PDS3_CONSTANTS,
    pointer_to_method_name,
)
from pdr.utils import depointerize, get_pds3_pointers, pointerize

# we do not want rasterio to shout about data not being georeferenced; most
# rasters are not _supposed_ to be georeferenced.
warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)


def skeptically_load_header(path, object_name="header"):
    try:
        try:
            return pvl.load(path)
        except ValueError:
            with open(path, "r") as file:
                return file.read()
    except (ParseError, ValueError, OSError):
        warnings.warn(f"unable to parse {object_name}")


# TODO: watch out for cases in which individual products may be scattered
#  across multiple HDUs. I'm not certain where these are, and I think it is
#  technically illegal in every PDS3 version, but I'm almost certain they
#  exist anyway.
def pointer_to_fits_key(pointer, hdulist):
    """
    In some data sets with FITS, the PDS3 object names and FITS object
    names are not identical. This function attempts to use Levenshtein
    "fuzzy matching" to identify the correlation between the two. It is not
    guaranteed to be correct! And special case handling might be required in
    the future.
    """
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
        # known special constants per pointer
        self.specials = {}
        # Attempt to identify and assign the data and label files
        if fn.endswith(LABEL_EXTENSIONS):
            setattr(self, "labelname", fn)
            for dext in DATA_EXTENSIONS:
                if Path(
                    filename := fn.replace(Path(fn).suffix, dext)
                ).exists():
                    setattr(self, "filename", filename)
                    break
        elif fn.endswith(DATA_EXTENSIONS):
            setattr(self, "filename", fn)
            for lext in LABEL_EXTENSIONS:
                if Path(
                    labelname := fn.replace(Path(fn).suffix, lext)
                ).exists():
                    setattr(self, "labelname", labelname)
                    break
        else:
            warnings.warn(f"Unknown filetype: {Path(fn).suffix}")
            setattr(self, "filename", fn)
            # TODO: Can you have an unknown filetype and a known label?
            #  Should we define attribute labelname here? I guess you
            #  couldn't know if it was a file or a label because the
            #  extension didn't fit...So this will break with all M3 data or
            #  anything else that uses weird extensions...

        # Just use pds4_tools if this is a PDS4 file
        # TODO: redundant and confusing w/read_label
        try:
            data = pds4.read(self.labelname, quiet=True)
            for structure in data.structures:
                setattr(self, structure.id.replace(" ", "_"), struct.data)
                self.index += [structure.id.replace(" ", "_")]
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
            for pointer in self.pointers:
                object_name = depointerize(pointer)
                self.index.append(object_name)
                setattr(
                    self,
                    object_name,
                    self.load_from_pointer(object_name),
                )

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

    def load_from_pointer(self, pointer):
        loader = getattr(self, pointer_to_method_name(pointer, self.filename))
        return loader(pointer)

    def read_image(self, object_name="IMAGE", userasterio=True):  # ^IMAGE
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
        object_name = depointerize(object_name)
        try:
            if "INSTRUMENT_ID" in self.LABEL.keys():
                if (
                    self.LABEL["INSTRUMENT_ID"] == "M3"
                    and self.LABEL["PRODUCT_TYPE"] == "RAW_IMAGE"
                ):
                    # because rasterio doesn't read M3 L0 data correctly
                    userasterio = False
        except (KeyError, AttributeError):
            pass
        if object_name == "IMAGE" or self.filename.lower().endswith("qub"):
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
        block = self.labelblock(object_name)
        if block:
            if object_name == "QUBE":  # ISIS2 QUBE format
                BYTES_PER_PIXEL = int(block["CORE_ITEM_BYTES"])  # / 8)
                sample_type = sample_types(
                    block["CORE_ITEM_TYPE"], BYTES_PER_PIXEL
                )
                nrows = block["CORE_ITEMS"][2]
                ncols = block["CORE_ITEMS"][0]
                prefix_cols, prefix_bytes = 0, 0
                # TODO: Handle the QUB suffix data
                BANDS = block["CORE_ITEMS"][1]
                band_storage_type = "ISIS2_QUBE"
            else:
                BYTES_PER_PIXEL = int(block["SAMPLE_BITS"] / 8)
                sample_type = sample_types(
                    block["SAMPLE_TYPE"], BYTES_PER_PIXEL
                )
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
            start_byte = self.data_start_byte(object_name)
        elif (
            self.LABEL["INSTRUMENT_ID"] == "M3"
            and self.LABEL["PRODUCT_TYPE"] == "RAW_IMAGE"
        ):
            # This is handling the special case of Chandrayaan M3 L0 data,
            # which are in a deprecated ENVI format that uses "line prefixes"
            BYTES_PER_PIXEL = int(
                self.LABEL["L0_FILE"]["L0_IMAGE"]["SAMPLE_BITS"] / 8
            )
            sample_type = sample_types(
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
            endian=sample_type[0], pixels=pixels, fmt=sample_type[-1]
        )
        numpy_dtype = np.dtype(f"{sample_type[0]}{sample_type[-1]}")
        try:  # a little decision tree to seamlessly deal with compression
            if isinstance(self.labelget(pointerize(object_name)), str):
                f = decompress(
                    self.get_absolute_path(
                        self.labelget(pointerize(object_name))
                    )
                )
            else:
                f = decompress(self.filename)
            # Make sure that single-band images are 2-dim arrays.
            f.seek(start_byte)
            prefix = None
            if BANDS == 1:
                image = np.array(
                    struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL)),
                    dtype=numpy_dtype,
                )
                image = image.reshape((nrows, ncols + prefix_cols))
                if prefix_cols:
                    # Ignore the prefix data, if any.
                    # TODO: Also return the prefix
                    prefix = image[:, :prefix_cols]
                    if object_name == "LINE_PREFIX_TABLE":
                        return prefix
                    image = image[:, prefix_cols:]
            # TODO: I think the ndarray.reshape calls in the next
            #  three cases may be wrong.
            elif band_storage_type == "BAND_SEQUENTIAL":
                image = np.array(
                    struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL)),
                    dtype=numpy_dtype,
                )
                image = image.reshape((BANDS, nrows, ncols + prefix_cols))
            elif band_storage_type == "LINE_INTERLEAVED":
                pixels_per_frame = BANDS * ncols
                endian, length = (sample_type[0], sample_type[-1])
                fmt = f"{endian}{pixels_per_frame}{length}"
                image, prefix = [], []
                for _ in np.arange(nrows):
                    prefix.append(f.read(prefix_bytes))
                    frame = np.array(
                        struct.unpack(
                            fmt,
                            f.read(pixels_per_frame * BYTES_PER_PIXEL),
                        ),
                        dtype=numpy_dtype,
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
                    struct.unpack(fmt, f.read(pixels * BYTES_PER_PIXEL)),
                    dtype=numpy_dtype,
                )
                image = image.reshape((BANDS, nrows, ncols + prefix_cols))
        except:
            raise
        finally:
            f.close()
        if "PREFIX" in object_name:
            return prefix
        return image

    def read_table_structure(self, object_name):
        """
        Try to turn the TABLE definition into a column name / data type
        array. Requires renaming some columns to maintain uniqueness. Also
        requires unpacking columns that contain multiple entries. Also
        requires adding "placeholder" entries for undefined data (e.g.
        commas in cases where the allocated bytes is larger than given by
        BYTES, so we need to read in the "placeholder" space and then
        discard it later).

        If the table format is defined in an external FMT file, then this
        will attempt to locate it in the same directory as the data / label,
        and throw an error if it's not there.
        TODO: Grab external format files as needed.
        """
        # TODO: this will generally fail for PDS4 -- but maybe it never needs
        #  to be called?
        block = self.labelblock(depointerize(object_name))
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
                    f"Unable to locate external table format "
                    f'file:\n\t{block["^STRUCTURE"]}'
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
                # The +1 is for the carriage return... these files are badly
                # formatted...
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
        """
        Read a table. Will first attempt to parse it as generic CSV
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

    def read_text(self, object_name):
        target = self.labelget(pointerize(object_name))
        local_path = self.get_absolute_path(
            self.labelget(pointerize(object_name))
        )
        try:
            return open(local_path).read()
        except FileNotFoundError:
            warnings.warn(f"couldn't find {target}")
        except UnicodeDecodeError:
            warnings.warn(f"couldn't parse {target}")
        return self.labelget(object_name)

    def read_header(self, object_name="HEADER"):
        """Attempt to read a file header."""
        target = self.labelget(pointerize(object_name))
        if isinstance(target, (list, int)):
            warnings.warn(
                "headers with specified byte/record offsets are not presently "
                "supported"
            )
            return self.labelget(object_name)
        local_path = self.get_absolute_path(
            self.labelget(pointerize(object_name))
        )
        if Path(local_path).exists():
            return skeptically_load_header(local_path, object_name)
        warnings.warn(f"Unable to find {object_name}")
        return self.labelget(pointerize(object_name))

    def handle_fits_file(self, pointer=""):
        """
        This function attempts to read all FITS files, compressed or
        uncompressed, with astropy.io.fits. Files with 'HEADER' pointer
        return the header, all others return data.
        TODO, maybe: dispatch to decompress() for weirdo compression
          formats, but possibly not right here? hopefully we shouldn't need
          to handle compressed FITS files too often anyway.
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

    def find_special_constants(self, key):
        """
        attempts to find special constants in the associated object
        by referencing the label and "standard" implicit special constant
        values, then populates self.special_constants as appropriate.
        TODO: doesn't do anything for PDS4 products at present. Also, we
         need an attribute for distinguishing PDS3 from PDS4 products.
        """
        obj, block = self._init_array_method(key)
        # check for explicitly-defined special constants
        specials = {
            name: block[name]
            for name in PDS3_CONSTANT_NAMES
            if name in block.keys()
        }
        # check for implicit constants appropriate to the sample type
        implicit_possibilities = IMPLICIT_PDS3_CONSTANTS[obj.dtype.name]
        specials |= {
            possibility: constant
            for possibility, constant in implicit_possibilities.items()
            if constant in obj
        }
        self.specials[key] = specials

    def get_scaled(self, key: str, inplace: bool = False) -> np.ndarray:
        """
        fetches copy of data object corresponding to key, masks special
        constants, then applies any scale and offset specified in the label.
        only relevant to arrays.

        if inplace is True, modifies object in place.

        TODO: as above, does nothing for PDS4.
        """
        obj, block = self._init_array_method(key)
        if inplace is not True:
            obj = obj.copy()
        if key not in self.specials:
            self.find_special_constants(key)
        if self.specials[key] != {}:
            obj = np.ma.MaskedArray(obj)
            obj.mask = np.isin(obj.data, list(self.specials[key].values()))
        scale = 1
        offset = 0
        if "SCALING_FACTOR" in block.keys():
            scale = block["SCALING_FACTOR"]
        if "OFFSET" in block.keys():
            offset = block["OFFSET"]
        return obj * scale + offset

    def _init_array_method(
        self, object_name: str
    ) -> tuple[np.ndarray, Mapping]:
        """
        helper function -- grab an array-type object and its label "block".
        specifying a generic return type because eventually we would like this
        to work with XML trees as well as PVL
        """
        obj = self[object_name]
        if not isinstance(obj, np.ndarray):
            raise TypeError("this method is only applicable to arrays.")
        return obj, self.labelblock(object_name)

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

    def data_start_byte(self, object_name):
        """
        Determine the first byte of the data in an IMG file from its
        pointer.
        """
        # TODO: hacky, make this consistent -- actually this pointer notation
        #  is hacky across the module, primarily because it's horrible in the
        #  first place :shrug: -- previously I did this by making pointers
        #  lists, but this may be unwieldy
        # TODO: like similar functions, this will currently break with PDS4
        target = self.labelget(object_name)
        if isinstance(target, Mapping):
            target = self.labelget(pointerize(object_name))
        labelblock = self.labelblock(object_name)
        # TODO: I am positive this will break sometimes; need to find the
        #  correct RECORD_BYTES in some cases...sequence pointers
        if "RECORD_BYTES" in labelblock.keys():
            record_bytes = labelblock["RECORD_BYTES"]
        else:
            record_bytes = self.labelget("RECORD_BYTES")
        if isinstance(target, int):
            return record_bytes * (target - 1)
        elif isinstance(target, list):
            if isinstance(target[0], int):
                return target[0]
            elif isinstance(target[-1], int):
                return record_bytes * (target[-1] - 1)
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

    def get_absolute_path(self, file):
        if self.labelname:
            return str(Path(Path(self.labelname).parent, file))
        elif self.filename:
            return str(Path(Path(self.filename).parent, file))
        else:
            return file

    def dump_browse(
        self,
        prefix: Optional[Union[str, Path]] = None,
        outpath: Optional[Union[str, Path]] = None,
        scaled=True,
        delete=False,
        **browse_kwargs,
    ) -> None:
        """
        attempt to dump all data objects associated with this Data object
        to disk.

        if delete is True, objects are deleted as soon as they are dumped,
        rendering this Data object 'empty' afterwards.

        browse_kwargs are passed directly to pdr.browisfy.dump_browse.
        """
        if prefix is None:
            prefix = Path(self.filename).stem
        if outpath is None:
            outpath = Path(".")
        for object_name in self.index:
            obj = self[object_name]
            if isinstance(obj, np.ndarray) and (scaled is True):
                obj = self.get_scaled(object_name, inplace=delete)
            outfile = str(Path(outpath, f"{prefix}_{object_name}"))
            browsify(obj, outfile, **browse_kwargs)
            if delete is True:
                del obj

    # make it possible to get data objects with slice notation, like a dict
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
