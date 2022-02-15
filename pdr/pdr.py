import bz2
import gzip
import os
import struct
import warnings
from functools import partial, cache
from io import StringIO
from pathlib import Path
from typing import Mapping, Optional, Union, Sequence
from zipfile import ZipFile

import Levenshtein as lev
import numpy as np
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
    LABEL_EXTENSIONS, pointer_to_loader, generic_image_properties,
    looks_like_this_kind_of_file, FITS_EXTENSIONS,
)
from pdr.utils import (
    depointerize,
    get_pds3_pointers,
    pointerize,
    trim_label,
    casting_to_float,
    check_cases,
    byte_columns_to_object,
    enforce_byteorder,
    TimelessOmniDecoder,
    booleanize_booleans,
    append_repeated_object,
    filter_duplicate_pointers, head_file
)

# we do not want rasterio to shout about data not being georeferenced; most
# rasters are not _supposed_ to be georeferenced.
warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)

cached_pvl_load = cache(partial(pvl.load, decoder=TimelessOmniDecoder()))


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


def skeptically_load_header(
    path, object_name="header", start_byte=0, length=None
):
    try:
        try:
            return cached_pvl_load(check_cases(path))
        except ValueError:
            file = open(check_cases(path))
            file.seek(start_byte)
            text = file.read(length)
            file.close()
            return text
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


def check_explicit_delimiter(block):
    if "FIELD_DELIMITER" in block.keys():
        return {
            "COMMA": ",", "VERTICAL_BAR": "|", "SEMICOLON": ";", "TAB": "\t"
        }[block["FIELD_DELIMITER"]]
    return ","


class Data:
    def __init__(
        self,
        fn: Union[Path, str],
        *,
        debug: bool = False,
        lazy: Optional[bool] = None,
        label_fn: Optional[Union[Path, str]] = None
    ):
        # TODO: products can have multiple data files, and in some cases one
        #  of those data files also contains the attached label -- basically,
        #  these can't be strings
        self.debug = debug
        self.filename = fn
        self.file_mapping = {}
        self.labelname = None
        # index of all of the pointers to data
        self.index = []
        # known special constants per pointer
        self.specials = {}
        implicit_lazy_exception = None
        # Attempt to identify and assign a label file
        if label_fn is not None:
            self.labelname = label_fn
            lazy = False if lazy is None else lazy
        elif fn.endswith(LABEL_EXTENSIONS):
            self.labelname = fn
            lazy = False if lazy is None else lazy
        else:
            implicit_lazy_exception = fn
            lazy = True if lazy is None else lazy
        while self.labelname is None:
            for lext in LABEL_EXTENSIONS:
                try:
                    self.labelname = check_cases(
                        fn.replace(Path(fn).suffix, lext)
                    )
                except FileNotFoundError:
                    continue
            break
        label = self.read_label()
        setattr(self, "LABEL", label)
        self.index += ["LABEL"]
        if self.labelname.endswith(".xml"):
            # Just use pds4_tools if this is a PDS4 file
            # TODO: do this better, including lazy
            data = pds4.read(self.labelname, quiet=True)
            for structure in data.structures:
                setattr(self, structure.id.replace(" ", "_"), structure.data)
                self.index += [structure.id.replace(" ", "_")]
            return

        pt_groups = groupby(lambda pt: pt[0], get_pds3_pointers(label))
        pointers = []
        # noinspection PyArgumentList
        pointers = filter_duplicate_pointers(pointers, pt_groups)
        setattr(self, "pointers", pointers)
        self._handle_initial_load(lazy, implicit_lazy_exception)
        if (lazy is False) or (implicit_lazy_exception == fn):
            non_labels = [i for i in self.index if i != "LABEL"]
            if all((self[i] is None for i in non_labels)):
                self._fallback_image_load()

    def _handle_initial_load(self, lazy, implicit_lazy_exception):
        for pointer in self.pointers:
            object_name = depointerize(pointer)
            # TODO: sloppy?
            if 'STRUCTURE' in object_name:
                continue
            self.index.append(object_name)
            fn = self._object_to_filename(object_name)
            self.file_mapping[object_name] = fn
            if lazy is False:
                self.load(object_name)
            elif (lazy is True) and (fn == implicit_lazy_exception):
                self.load(object_name)
            else:
                setattr(self, object_name, None)

    def _object_to_filename(self, object_name, raise_missing=False):
        target = self.labelget(pointerize(object_name))
        if isinstance(target, Sequence) and not (isinstance(target, str)):
            if isinstance(target[0], str):
                target = target[0]
        try:
            if isinstance(target, str):
                return check_cases(self.get_absolute_path(target))
            else:
                return check_cases(self.filename)
        except FileNotFoundError:
            if raise_missing is True:
                raise
            return None

    def _fallback_image_load(self):
        """
        sometimes images do not have explicit pointers, so we may want to
        try to read an image out of the file anyway.
        """
        if looks_like_this_kind_of_file(self.filename, FITS_EXTENSIONS):
            image = self.handle_fits_file(self.filename)
        else:
            # TODO: this will presently break if passed an unlabeled
            #  image file. read_image() should probably be made more
            #  permissive in some way to handle this, or we should at
            #  least give a useful error message.
            image = self.read_image()
        # TODO: this will presently break if passed an unlabeled
        #  image file. read_image() should probably be made more
        #  permissive in some way to handle this, or we should at
        #  least give a useful error message.
        if image is not None:
            setattr(self, "IMAGE", image)
            self.index += ["IMAGE"]

    def load(self, object_name, reload=False):
        if object_name not in self.index:
            raise KeyError(f"{object_name} not found in index: {self.index}.")
        if hasattr(self, object_name):
            if (self[object_name] is not None) and (reload is False):
                raise ValueError(
                    f"{object_name} is already loaded; pass reload=True to "
                    f"force reload."
                )
        try:
            setattr(self, object_name, self.load_from_pointer(object_name))
        except KeyboardInterrupt:
            raise
        except FileNotFoundError as ex:
            warnings.warn(f"Unable to find some requirement of {object_name}.")
            setattr(
                self, object_name, self._catch_return_default(object_name, ex)
            )
        except Exception as ex:
            warnings.warn(f"Unable to load {object_name}.")
            setattr(
                self, object_name, self._catch_return_default(object_name, ex)
            )

    def read_label(self):
        """
        Attempts to read the data label, checking first whether this is a
        PDS4 file, then whether it has a detached label, then whether it
        has an attached label. Returns None if all of these attempts are
        unsuccessful.
        """
        if self.labelname:  # a detached label exists
            if Path(self.labelname).suffix.lower() == ".xml":
                label = pds4.read(self.labelname, quiet=True).label.to_dict()
            else:
                label = cached_pvl_load(self.labelname)
            self.file_mapping["LABEL"] = self.labelname
            return label
        # look for attached label
        label = pvl.loads(
            trim_label(decompress(self.filename)),
            decoder=TimelessOmniDecoder()
        )
        self.file_mapping["LABEL"] = self.filename
        self.labelname = self.filename
        return label

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
    ):
        """
        Read an image file as a numpy array. Defaults to using `rasterio`,
        and then tries to parse the file directly.
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
        # TODO: does not work with referenced images with headers right now?
        #  (works for images attached to the _specific header we're reading_)
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
        fields = self.read_format_block(block, object_name)
        # give columns unique names so that none of our table handling explodes
        fmtdef = pd.DataFrame.from_records(fields)
        namegroups = fmtdef.groupby("NAME")
        for name, field_group in namegroups:
            if len(field_group) == 1:
                continue
            if name == "RESERVED":
                name = f"RESERVED_{field_group['START_BYTE'].iloc[0]}"
            names = [f"{name}_{ix}" for ix in range(len(field_group))]
            fmtdef.loc[field_group.index, "NAME"] = names
        return fmtdef

    def load_format_file(self, format_file, object_name):
        try:
            fmtpath = check_cases(
                self.get_absolute_path(format_file)
            )
            return cached_pvl_load(fmtpath)
        except FileNotFoundError:
            warnings.warn(
                f"Unable to locate external table format file:\n\t"
                f"{format_file}. Try retrieving this file and "
                f"placing it in the same path as the {object_name} "
                f"file."
            )
            raise FileNotFoundError

    def read_format_block(self, block, object_name):
        # load external structure specifications
        format_block = list(block.items())
        while "^STRUCTURE" in [obj[0] for obj in format_block]:
            format_block = self.inject_format_files(format_block, object_name)
        fields = []
        for item_type, definition in format_block:
            if item_type in ("COLUMN", "FIELD"):
                obj = dict(definition)
                repeat_count = definition.get("ITEMS")
            elif item_type == "CONTAINER":
                obj = self.read_format_block(definition, object_name)
                repeat_count = definition.get("REPETITIONS")
            else:
                continue
            # TODO: what is our working example of a table that
            #  uses ITEMS that isn't being punted to a FITS
            #  library?
            # containers can have REPETITIONS,
            # and some "columns" contain a lot of columns (ITEMS)
            # repeat the definition, renaming duplicates, for these cases
            # TODO, maybe: index containers appropriately so that we can check
            #  for accuracy of start byte values...but I am not very confident
            #  that files like this will be formatted consistently enough
            #  that checking to insert placeholders will be useful
            if repeat_count is not None:
                fields = append_repeated_object(obj, fields, repeat_count)
            else:
                fields.append(obj)
        return fields

    def inject_format_files(self, block, object_name):
        format_filenames = {
            ix: kv[1]
            for ix, kv in enumerate(block)
            if kv[0] == "^STRUCTURE"
        }
        # make sure to insert the structure blocks in the correct order --
        # and remember that keys are not unique, so we have to use the index
        assembled_structure = []
        last_ix = 0
        for ix, filename in format_filenames.items():
            fmt = list(self.load_format_file(filename, object_name).items())
            assembled_structure += block[last_ix:ix] + fmt
            last_ix = ix + 1
        assembled_structure += block[last_ix:]
        return assembled_structure

    def parse_table_structure(self, pointer):
        """
        Generate a dtype array to later pass to numpy.fromfile
        to unpack the table data according to the format given in the
        label.
        """
        fmtdef = self.read_table_structure(pointer)
        if fmtdef['DATA_TYPE'].str.contains('ASCII').any():
            # don't try to load it as a binary file -- TODO: kind of a hack
            return None, fmtdef
        dt = []
        if fmtdef is None:
            return np.dtype(dt), fmtdef
        fmtdef['dt'] = None
        if 'ITEM_BYTES' not in fmtdef.columns:
            fmtdef['ITEM_BYTES'] = np.nan
        data_types = tuple(
            fmtdef.groupby(['DATA_TYPE', 'ITEM_BYTES', 'BYTES'], dropna=False)
        )
        for data_type, group in data_types:
            dt, item_bytes, total_bytes = data_type
            sample_bytes = total_bytes if np.isnan(item_bytes) else item_bytes
            try:
                fmtdef.loc[group.index, 'dt'] = sample_types(
                    dt, sample_bytes, for_numpy=True
                )
            except KeyError:
                raise KeyError(
                    f"{data_type} is not a currently-supported data type."
                )
        dt = fmtdef[['NAME', 'dt']].to_records(index=False).tolist()
        return np.dtype(dt), fmtdef

    # TODO: refactor this. see issue #27.
    def read_table(self, pointer="TABLE"):
        """
        Read a table. Will first attempt to parse it as generic CSV
        and then fall back to parsing it based on the label format definition.
        """
        # TODO: this is not correctly loading the table fn when passed the
        #  label in the CCAM case, and probably some others
        target = self.labelget(pointerize(pointer))
        if isinstance(target, Sequence) and not (isinstance(target, str)):
            if isinstance(target[0], str):
                target = target[0]
        if isinstance(target, str):
            fn = check_cases(self.get_absolute_path(target))
        else:
            fn = check_cases(self.filename)
        try:
            dt, fmtdef = self.parse_table_structure(pointer)
        except KeyError as ex:
            warnings.warn(f"Unable to find or parse {pointer}")
            return self._catch_return_default(pointer, ex)
        # Check if this is just a DSV file
        try:
            # TODO: look for commas more intelligently or dispatch to astropy
            #  or whatever
            sep = check_explicit_delimiter(self.labelblock(pointer))
            start_byte = self.data_start_byte(pointer)
            # TODO: handle length (here and elsewhere)
            bytes_buffer = head_file(fn, nbytes=None, offset=start_byte)
            string_buffer = StringIO(bytes_buffer.read().decode())
            string_buffer.seek(0)
            table = pd.read_csv(string_buffer, sep=sep, header=None)
        except (UnicodeDecodeError, AttributeError, ParserError):
            # This is not parseable as a CSV file
            if dt is not None:
                array = np.fromfile(
                    fn,
                    dtype=dt,
                    offset=self.data_start_byte(pointer),
                    count=self.labelblock(pointer)["ROWS"],
                )
                swapped = enforce_byteorder(array, inplace=False)
                table = pd.DataFrame(swapped)
                table = byte_columns_to_object(table)
                table = booleanize_booleans(table, fmtdef)
            else:
                table = pd.DataFrame(
                    np.loadtxt(
                        fn,
                        # this is probably a poor assumption to hard code.
                        delimiter=',',
                        skiprows=self.labelget("LABEL_RECORDS"),
                    )
                    .copy()
                    .newbyteorder('=')
                )
        if len(table.columns) < len(fmtdef.NAME.tolist()):
            table = pd.read_fwf(fn)
        else:
            table.columns = fmtdef.NAME.tolist()
        try:
            # If there were any cruft "placeholder" columns, discard them
            table = table.drop(
                [k for k in table.keys() if "PLACEHOLDER" in k], axis=1
            )
        except TypeError as ex:  # Failed to read the table
            return self._catch_return_default(pointer, ex)
        # lp.print_stats()
        return table

    def read_text(self, object_name):
        target = self.labelget(pointerize(object_name))
        local_path = self.get_absolute_path(
            self.labelget(pointerize(object_name))
        )
        try:
            return open(check_cases(local_path)).read()
        except FileNotFoundError as ex:
            exception = ex
            warnings.warn(f"couldn't find {target}")
        except UnicodeDecodeError as ex:
            exception = ex
            warnings.warn(f"couldn't parse {target}")
        return self._catch_return_default(object_name, exception)

    def read_header(self, object_name="HEADER"):
        """Attempt to read a file header."""
        # TODO: not currently raising this in debug mode. probably shouldn't
        start_byte = self.data_start_byte(object_name)
        block = self.labelblock(object_name)
        if 'BYTES' in block.keys():
            length = block['BYTES']
        elif (
            ('RECORDS' in block.keys())
            and ('RECORD_BYTES' in self.LABEL.keys())
        ):
            length = block['RECORDS'] * self.LABEL['RECORD_BYTES']
        else:
            # TODO: I'm sure there are other cases to handle here.
            length = None
        return skeptically_load_header(
            self.file_mapping[object_name], object_name, start_byte, length
        )

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
        except Exception as ex:
            # TODO: assuming this does not need to be specified as f-string
            #  (like in read_header/tbd) -- maybe! must determine and specify
            #  what cases this exception was needed to handle
            self._catch_return_default(self.labelget(pointer), ex)

    def _catch_return_default(self, pointer: str, exception: Exception):
        """
        if we are in debug mode, reraise an exception. otherwise, return
        the label block only.
        """
        if self.debug is True:
            raise exception
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
        """
        This is a placeholder function for pointers that are
        not explicitly supported elsewhere. It throws a warning and
        passes just the value of the pointer.
        """
        warnings.warn(f"The {pointer} pointer is not yet fully supported.")
        return self.labelget(pointer)

    def trivial(self, pointer=""):
        """
        This is a trivial loader. It does not load. The purpose is to use
        for any pointers we don't want to load and instead simply want ignored.
        """
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
            # TODO: should be the filename of the target
            file_size = os.path.getsize(self.filename)
            return file_size-tab_size
        if record_bytes is not None and isinstance(target, int):
            return record_bytes * max(target - 1, 0)
        elif isinstance(target, list):
            if isinstance(target[0], int):
                return target[0]
            elif isinstance(target[-1], int):
                return record_bytes * max(target[-1] - 1, 0)
            elif isinstance(target[-1], pvl.Quantity):
                if target[-1].units == 'BYTES':
                    return target[-1].value
                return record_bytes * max(target[-1].value - 1, 0)
            else:
                return 0
        elif type(target) is str:
            return 0
        else:
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
        not_loaded = []
        for k in self.keys():
            if not hasattr(self, k):
                not_loaded.append(k)
            elif self[k] is None:
                not_loaded.append(k)
        return f"pdr.Data({self.filename})\nkeys={self.keys()}" \
               f"\nnot yet loaded: {not_loaded}"

    def __str__(self):
        return self.__repr__()

    def __len__(self):
        return len(self.index)

    def __iter__(self):
        for key in self.keys():
            yield self[key]
