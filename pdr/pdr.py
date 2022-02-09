import bz2
import gzip
import struct
import warnings
from functools import partial
from pathlib import Path
from typing import Mapping, Optional, Union
from zipfile import ZipFile

import Levenshtein as lev
import numpy as np
import os
import pandas as pd
import pds4_tools as pds4
import pvl
import rasterio
from astropy.io import fits
from cytoolz import groupby
from dustgoggles.structures import dig_for_value
from pandas.errors import ParserError
from pvl.exceptions import ParseError
from rasterio.errors import NotGeoreferencedWarning

from pdr.browsify import browsify, _browsify_array

from pdr.datatypes import (
    sample_types,
    PDS3_CONSTANT_NAMES,
    IMPLICIT_PDS3_CONSTANTS,
    generic_image_constants,
)
from pdr.formats import (
    LABEL_EXTENSIONS,
    DATA_EXTENSIONS,
    pointer_to_loader,
    generic_image_properties,
)
from pdr.utils import depointerize, get_pds3_pointers, pointerize, trim_label, \
    casting_to_float, check_cases

# we do not want rasterio to shout about data not being georeferenced; most
# rasters are not _supposed_ to be georeferenced.
warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)


def make_format_specifications(props):
    endian, ctype = props["sample_type"][0], props["sample_type"][-1]
    struct_fmt = f"{endian}{props['pixels']}{ctype}"
    dtype = np.dtype(f"{endian}{ctype}")
    return struct_fmt, dtype


def process_single_band_image(f, props):
    struct_fmt, numpy_dtype = make_format_specifications(props)
    image = np.array(
        struct.unpack(
            struct_fmt, f.read(props["pixels"] * props["BYTES_PER_PIXEL"])
        ),
        dtype=numpy_dtype,
    )
    image = image.reshape(
        (props["nrows"], props["ncols"] + props["prefix_cols"])
    )
    if props["prefix_cols"] > 0:
        prefix = image[:, : props["prefix_cols"]]
        image = image[:, props["prefix_cols"] :]
    else:
        prefix = None
    return image, prefix


# TODO: I think this may be wrong.
def process_band_sequential_image(f, props):
    struct_fmt, numpy_dtype = make_format_specifications(props)
    image = np.array(
        struct.unpack(
            struct_fmt, f.read(props["pixels"] * props["BYTES_PER_PIXEL"])
        ),
        dtype=numpy_dtype,
    )
    image = image.reshape(
        (props["BANDS"], props["nrows"], props["ncols"] + props["prefix_cols"])
    )
    if props["prefix_cols"] > 0:
        prefix = image[:, : props["prefix_cols"]]
        image = image[:, props["prefix_cols"] :]
    else:
        prefix = None
    return image, prefix


def process_line_interleaved_image(f, props):
    # pixels per frame
    props["pixels"] = props["BANDS"] * props["ncols"]
    struct_fmt, numpy_dtype = make_format_specifications(props)
    image, prefix = [], []
    for _ in np.arange(props["nrows"]):
        prefix.append(f.read(props["prefix_bytes"]))
        frame = np.array(
            struct.unpack(
                struct_fmt,
                f.read(props["pixels"] * props["BYTES_PER_PIXEL"]),
            ),
            dtype=numpy_dtype,
        ).reshape(props["BANDS"], props["ncols"])
        image.append(frame)
        del frame
    image = np.ascontiguousarray(np.array(image).swapaxes(0,1))
    return image, prefix


def skeptically_load_header(path, object_name="header"):
    try:
        try:
            return pvl.load(check_cases(path))
        except ValueError:
            with open(check_cases(path), "r") as file:
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
    filename = check_cases(filename)
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
            pt_groups = groupby(lambda pt: pt[0], get_pds3_pointers(LABEL))
            pointers = []
            for pointer, group in pt_groups.items():
                if len(group) > 1:
                    warnings.warn(
                        f"Duplicate handling for {pointer} not yet "
                        f"implemented, ignoring"
                    )
                else:
                    pointers.append(group[0][0])
            setattr(self, "pointers", pointers)
            for pointer in self.pointers:
                object_name = depointerize(pointer)
                self.index.append(object_name)
                try:
                    setattr(
                        self, object_name, self.load_from_pointer(object_name)
                    )
                except FileNotFoundError:
                    warnings.warn(f"Unable to find or load {object_name}.")
                    setattr(self, object_name, self.labelget(pointerize(object_name)))
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
            # look for attached label
            return pvl.loads(trim_label(decompress(self.filename)))
        # TODO: specify
        except Exception as ex:
            return

    def load_from_pointer(self, pointer):
        return pointer_to_loader(pointer, self)(pointer)

    def open_with_rasterio(self):
        dataset = rasterio.open(check_cases(self.filename))
        if len(dataset.indexes) == 1:
            # Make 2D images actually 2D
            return dataset.read()[0, :, :]
        else:
            return dataset.read()

    def read_image(
        self, object_name="IMAGE", userasterio=True, special_properties=None
    ):  # ^IMAGE
        """
        Read a PDS IMG formatted file into an array. Defaults to using
        `rasterio`, and then tries to parse the file directly.
        """
        # TODO: Check for and apply BIT_MASK.
        object_name = depointerize(object_name)
        if object_name == "IMAGE" or self.filename.lower().endswith("qub"):
            # TODO: we could generalize this more by trying to find filenames.
            if userasterio is True:
                try:
                    return self.open_with_rasterio()
                except rasterio.errors.RasterioIOError:
                    pass
        if special_properties is not None:
            props = special_properties
        else:
            block = self.labelblock(object_name)
            if block is None:
                return None  # not much we can do with this!
            props = generic_image_properties(object_name, block, self)
        # a little decision tree to seamlessly deal with compression
        if isinstance(self.labelget(pointerize(object_name)), str):
            fn = self.get_absolute_path(self.labelget(pointerize(object_name)))
        else:
            fn = self.filename
        f = decompress(fn)
        f.seek(props["start_byte"])
        try:
            # Make sure that single-band images are 2-dim arrays.
            if props["BANDS"] == 1:
                image, prefix = process_single_band_image(f, props)
            # TODO: I think the ndarray.reshape call in this case may be wrong
            elif props["band_storage_type"] == "BAND_SEQUENTIAL":
                image, prefix = process_band_sequential_image(f, props)
            elif props["band_storage_type"] == "LINE_INTERLEAVED":
                image, prefix = process_line_interleaved_image(f, props)
            else:
                warnings.warn(
                    f"Unknown BAND_STORAGE_TYPE={props['band_storage_type']}. "
                    f"Guessing BAND_SEQUENTIAL."
                )
                image, prefix = process_band_sequential_image(f, props)
        except Exception as ex:
            raise ex
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
            try:
                fmtpath = check_cases(
                    self.get_absolute_path(block["^STRUCTURE"])
                )
                structure = pvl.load(fmtpath)
            except FileNotFoundError:
                warnings.warn(
                    f"Unable to locate external table format file:\n\t"
                    f"{block['^STRUCTURE']}. Try retrieving this file and "
                    f"placing it in the same path as the {object_name} file."
                )
                raise FileNotFoundError
            # print(f"Reading external format file:\n\t{fmtpath}")
        else:
            structure = block
        fields = []
        for i, k in enumerate(structure.keys()):
            obj = {}  # reinitialize... probably unnecessary
            objdef = structure[
                i
            ]  # use the index because the keys are not unique
            if objdef[0] in ("COLUMN", "FIELD"):
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
                # fmtdef = pd.concat([fmtdef, obj], axis=0, ignore_index=True)
                fields.append(obj)
        fmtdef = pd.DataFrame.from_records(fields)
        return fmtdef

    def parse_table_structure(self, pointer):
        """
        Generate a dtype array to later pass to numpy.fromfile
        to unpack the table data according to the format given in the
        label.
        """
        fmtdef = self.read_table_structure(pointer)
        if fmtdef['DATA_TYPE'].str.contains('ASCII').any():
            # don't try to load it as a binary file
            # TODO: kind of a hack
            return None, fmtdef
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

    # TODO: refactor this. see issue #27.
    def read_table(self, pointer="TABLE"):
        """
        Read a table. Will first attempt to parse it as generic CSV
        and then fall back to parsing it based on the label format definition.
        """
        if isinstance(self.labelget(pointerize(pointer)), str):
            fn = check_cases(
                self.get_absolute_path(self.labelget(pointerize(pointer)))
            )
        else:
            fn = check_cases(self.filename)
        try:
            dt, fmtdef = self.parse_table_structure(pointer)
        except KeyError:
            warnings.warn(f"Unable to find or parse {pointer}")
            return self.labelget(pointer)
        # Check if this is just a CSV file
        try:
            # TODO: look for commas more intelligently or dispatch to astropy
            #  or whatever
            table = pd.read_csv(fn)
        except (UnicodeDecodeError, AttributeError, ParserError):
            # This is not parseable as a CSV file
            if dt is not None:
                table = pd.DataFrame(
                    np.fromfile(
                        fn,
                        dtype=dt,
                        offset=self.data_start_byte(pointer),
                        count=self.labelblock(pointer)["ROWS"],
                    )
                    .byteswap()
                    .newbyteorder('=')  # Pandas doesn't do non-native endian
                )
            else:
                table = pd.DataFrame(
                    np.loadtxt(fn,
                               delimiter=',',  # this is probably a poor assumption to hard code.
                               skiprows=self.labelget("LABEL_RECORDS"),
                               )
                    .byteswap()
                    .newbyteorder('=')
                )
        if len(table.columns) < len(fmtdef.NAME.tolist()):
            table = pd.read_fwf(fn)
        table.columns = fmtdef.NAME.tolist()
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
            return open(check_cases(local_path)).read()
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
            hdulist = fits.open(check_cases(self.filename))
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
            if (
                (name in block.keys())
                and not (block[name] == 'N/A')
            )
        }
        # ignore uint8 implicit constants (0, 255) for now -- too problematic
        # TODO: maybe add an override
        if obj.dtype.name == 'uint8':
            self.specials[key] = specials
            return
        # check for implicit constants appropriate to the sample type
        implicit_possibilities = IMPLICIT_PDS3_CONSTANTS[obj.dtype.name]
        specials |= {
            possibility: constant
            for possibility, constant in implicit_possibilities.items()
            if constant in obj
        }
        self.specials[key] = specials

    def get_scaled(self, key: str, inplace=False) -> np.ndarray:
        """
        fetches copy of data object corresponding to key, masks special
        constants, then applies any scale and offset specified in the label.
        only relevant to arrays.

        if inplace is True, does calculations in-place on original array,
        with attendant memory savings and destructiveness.

        TODO: as above, does nothing for PDS4.
        """
        obj, block = self._init_array_method(key)
        if key not in self.specials:
            consts = generic_image_constants(self)
            self.specials[key] = consts
            if not consts:
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
        # meaningfully better for enormous unscaled arrays
        if (scale == 1) and (offset == 0):
            return obj
        # try to perform the operation in-place if requested, although if
        # we're casting to float, we can't
        # TODO: detect rollover cases, etc.
        if (
            (inplace is True)
            and not casting_to_float(obj, scale, offset)
        ):
            obj *= scale
            obj += offset
            return obj
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

    def trivial(self, pointer=""):
        """This is a trivial loader. It does not load. The purpose is to use
        for any pointers we don't want to load and instead simply want ignored."""
        pass

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
            if record_bytes is None and isinstance(target, int):
                # Counts up from the bottom of the file
                rows = self.labelget("ROWS")
                row_bytes = self.labelget("ROW_BYTES")
                tab_size = rows * row_bytes
                file_size = os.path.getsize(self.filename)
                return file_size-tab_size
        if record_bytes is not None and isinstance(target, int):
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
                # probably do this better
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

    # TODO: reorganize this -- common dispatch funnel with dump_browse,
    #  split up the image-gen part of _browsify_array, something like that
    def show(self, object_name=None, scaled=True, **browse_kwargs):
        if object_name is None:
            object_name = [
                obj for obj in self.index if "IMAGE" in obj
            ]
            if object_name is None:
                raise ValueError("please specify the name of an image object.")
            object_name = object_name[0]
        if not isinstance(self[object_name], np.ndarray):
            raise TypeError("Data.show only works on array data.")
        if scaled is True:
            obj = self.get_scaled(object_name)
        else:
            obj = self[object_name]
        return _browsify_array(obj, save=False, outbase="", **browse_kwargs)

    def _dump_scaled_array(
        self, object_name, purge, outfile, **browse_kwargs
    ):
        obj = self.get_scaled(object_name, inplace=purge)
        browsify(obj, outfile, purge, **browse_kwargs)

    def dump_browse(
        self,
        prefix: Optional[Union[str, Path]] = None,
        outpath: Optional[Union[str, Path]] = None,
        scaled=True,
        purge=False,
        **browse_kwargs,
    ) -> None:
        """
        attempt to dump all data objects associated with this Data object
        to disk.

        if purge is True, objects are deleted as soon as they are dumped,
        rendering this Data object 'empty' afterwards.

        browse_kwargs are passed directly to pdr.browisfy.dump_browse.
        """
        if prefix is None:
            prefix = Path(self.filename).stem
        if outpath is None:
            outpath = Path(".")
        for obj in self.index:
            outfile = str(Path(outpath, f"{prefix}_{obj}"))
            dump_it = partial(browsify, purge=purge, **browse_kwargs)
            if isinstance(self[obj], np.ndarray):
                if scaled == "both":
                    dump_it(
                        self.get_scaled(obj), outfile + "_scaled", purge=False
                    )
                    dump_it(self[obj], outfile + "_unscaled")
                elif scaled is True:
                    dump_it(self.get_scaled(obj, inplace=purge), outfile)
                elif scaled is False:
                    dump_it(self[obj], outfile)
                else:
                    raise ValueError(f"unknown scaling argument {scaled}")
            else:
                dump_it(self[obj], outfile)
            if (purge is True) and (obj != "LABEL"):
                self.__delattr__(obj)

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
