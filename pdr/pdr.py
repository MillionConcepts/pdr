from __future__ import annotations
from functools import partial, cache
from itertools import chain, product
from numbers import Number
from pathlib import Path
from typing import (
    Any,
    Callable,
    Collection,
    Iterator,
    Literal,
    Mapping,
    Optional,
    Sequence,
    TYPE_CHECKING,
    Union
)
import re
import warnings


# get_annotations is new in 3.10.  this polyfill handles only
# the specific case we care about.
try:
    from inspect import get_annotations
except ImportError:
    def get_annotations(o):
        if isinstance(o, type):
            ann = o.__dict__.get('__annotations__', None)
        else:
            ann = getattr(o, '__annotations__', None)
        if ann is None:
            return {}
        if not isinstance(ann, dict):
            raise ValueError(
                f"{o!r}.__annotations__ is neither a dict nor None"
            )
        # copy the dict to match the behavior of the official get_annotations
        return { key: value for key, value in ann.items() }

from cytoolz import countby, identity
from dustgoggles.dynamic import Dynamic
from dustgoggles.func import gmap
from dustgoggles.structures import dig_for_value, listify
from dustgoggles.tracker import Tracker, TrivialTracker
from multidict import MultiDict

from pdr.errors import AlreadyLoadedError, DuplicateKeyWarning
from pdr.formats import check_special_fn, special_image_constants
from pdr.loaders.utility import DESKTOP_IMAGE_STANDARDS
from pdr.parselabel.pds3 import (
    depointerize,
    get_pds3_pointers,
    pointerize,
    read_pvl,
)
from pdr.parselabel.pds4 import reformat_pds4_tools_label
from pdr.parselabel.utils import DEFAULT_PVL_LIMIT
from pdr.pdrtypes import DataIdentifiers
from pdr.utils import (
    associate_label_file,
    catch_return_default,
    check_cases,
    check_primary_fmt,
    prettify_multidict,
)

if TYPE_CHECKING:
    import numpy as np
    import pandas as pd
    from PIL.Image import Image


class Metadata(MultiDict):
    """
    MultiDict subclass intended primarily as a helper class for Data.
    includes various convenience methods for handling metadata syntaxes,
    common access and display interfaces, etc.
    """

    def __init__(
        self,
        mapping_params: tuple[Mapping, Collection[str]],
        standard: Literal["PDS3", "PDS4", "FITS"] = "PDS3",
        **kwargs
    ):
        """"""
        mapping, params = mapping_params
        super().__init__(mapping, **kwargs)
        self.fieldcounts = countby(identity, params)
        self.standard = standard
        self.refresh_cache()
        self.identifiers = self._init_identifiers()

    # note that 'directly' caching these methods can result in recursive
    # reference chains behind the lru_cache API that can prevent the
    # Metadata object from being garbage-collected, which is why they are
    # hidden behind these wrappers. there may be a cleaner way to do this.
    def refresh_cache(self):
        self._metaget_interior = _metaget_factory(self)
        self._metablock_interior = _metablock_factory(self)

    def metaget(
        self, text: str, default: Any = None, warn: bool = True
    ) -> Any:
        """
        get the first value from this object whose key exactly matches `text`,
        even if it is nested inside a mapping. optionally evaluate it using
        `self.formatter`. raise a warning if there are multiple keys matching
        this.

        Warning:
            This function's return values are memoized for performance.
            Updating elements of a `Metadata` object's underlying mapping
            that have already been accessed with this function will not update
            future calls to this function.
        """
        count = self.fieldcounts.get(text)
        if count is None:
            return default
        if (count > 1) and (warn is True):
            warnings.warn(
                f"More than one value for {text} exists in the metadata. "
                f"Returning only the first.",
                DuplicateKeyWarning,
            )
        return self._metaget_interior(text, default)

    def metaget_(self, text: str, default: Any = None) -> Any:
        """quiet-by-default version of metaget"""
        return self.metaget(text, default, False)

    def metaget_fuzzy(self, text: str) -> Any:
        """Like `metaget()`, but fuzzy-matches key names."""
        import Levenshtein as lev
        levratio = {
            key: lev.ratio(key, text) for key in set(self.fieldcounts.keys())
        }
        if levratio == {}:
            return None
        peak = max(levratio.values())
        for k, v in filter(lambda kv: kv[1] == peak, levratio.items()):
            return self.metaget(k)

    def metablock(self, text: str, warn: bool = True) -> Optional[Mapping]:
        """
        get the first value from this object whose key exactly
        matches `text`, even if it is nested inside a mapping, if the value
        itself is a mapping (e.g., nested PVL block, XML 'area', etc.)
        evaluate it using self.formatter. raise a warning if there are
        multiple keys matching this.
        if there is no key matching 'text', will evaluate and return the
        metadata as a whole.

        Warning:
            This function's return values are memoized for performance.
            Updating elements of a `Metadata` object's underlying mapping
            that have already been accessed with this function will not update
            future calls to this function.
        """
        count = self.fieldcounts.get(text)
        if count is None:
            return None
        if (count > 1) and (warn is True):
            warnings.warn(
                f"More than one block named {text} exists in the metadata. "
                f"Returning only the first.",
                DuplicateKeyWarning,
            )
        return self._metablock_interior(text)

    def metablock_(self, text: str) -> Optional[Mapping]:
        """quiet-by-default version of metablock"""
        return self.metablock(text, False)

    def _init_identifiers(self) -> DataIdentifiers:
        """
        Initializes common PDS3 data identifiers for use in special-case
        checks.
        """
        identifiers = {
            field: self.metaget_(field, "")
            for field in get_annotations(DataIdentifiers)
        }
        # it never does us any favors to have tuples or sets in here
        for k, v in identifiers.items():
            if isinstance(v, (tuple, set)):
                identifiers[k] = str(v)
        return identifiers

    def __str__(self):
        """"""
        return f"Metadata({prettify_multidict(self)})"

    def __repr__(self):
        """"""
        return f"Metadata({prettify_multidict(self)})"

    _metaget_interior: Callable[[str, Any], Any]
    _metablock_interior: Callable[[str], Mapping]


class DebugExceptionPreempted(Exception):
    """
    Stub Exception subclass for selectively ignoring Exceptions from load
    failures when not in debug mode.
    """
    pass


class Data:
    """Core `pdr` class."""
    def __init__(
        self,
        fn: Union[Path, str],
        *,
        debug: bool = False,
        label_fn: Optional[Union[Path, str]] = None,
        search_paths: Union[Collection[str], str] = (),
        skip_existence_check: bool = False,
        pvl_limit: int = DEFAULT_PVL_LIMIT,
        tracker: Optional[TrivialTracker] = None,
    ):
        """"""
        # Bail out early if someone's trying to load directly from the network.
        if isinstance(fn, str) and re.match("(?i)^(?:https?|ftp):", fn):
            raise ValueError("Read-from-url is not currently implemented.")

        # list of the product's associated data objects
        self.index = []
        # do we raise an exception rather than a warning if loading a data
        # object fails?
        self.debug = debug
        self.filename = check_cases(Path(fn).absolute(), skip_existence_check)
        self.loaders = {}
        if (self.debug is True) and (tracker is None):
            self.tracker = Tracker(
                Path(self.filename).name.replace(".", "_"),
                outdir=Path(__file__).parent / ".tracker_logs",
            )
            self.tracker.clear()
        elif tracker is None:
            self.tracker = TrivialTracker()
        else:
            self.tracker = tracker
        # mappings from data objects to local paths
        self.file_mapping = {}
        # known special constants per data object
        self.specials = {}
        # dict to flag images loaded prescaled (currently only from FITS files)
        self._scaleflags = {}
        # where can we look for files containing data objects?
        # not yet fully implemented; only uses first (automatic) one.
        self.search_paths = [self._init_search_path()] + listify(search_paths)
        self.standard = None
        # cache for pds4_tools.reader.general_objects.Structure objects.
        self._pds4_structures = None
        # cache for hdulist, for primary FITS files -- this is primarily
        # an optimization for compressed files
        self._hdulist = None
        # dict of [str, int] for cases in which we need to reindex duplicate
        # HDU names in primary FITS files
        self._hdumap = None
        # Attempt to identify and assign a label file
        self.labelname = associate_label_file(
            self.filename, label_fn, skip_existence_check
        )
        # if unlabeled, check to see if we can read it in a non-PDS format
        if self.labelname is None:
            primary_format = check_primary_fmt(self.filename)
        elif (fmt := check_primary_fmt(self.labelname)) is not None:
            primary_format = fmt
        else:
            primary_format = None
        if primary_format is not None:
            self.standard = primary_format
            if self.standard == "FITS":
                from astropy.io import fits

                # TODO: bad. need to not leave this open, although inefficient
                self._hdulist = fits.open(self.filename)
        elif str(self.labelname).endswith(".xml"):
            self.standard = "PDS4"
            self._pds4_structures = {}
            self._init_pds4()
        else:
            self.standard = "PDS3"
        try:
            self.metadata = self.read_metadata(pvl_limit=pvl_limit)
        except (UnicodeError, FileNotFoundError) as ex:
            raise ValueError(
                f"Can't load this product's metadata: {ex}, {type(ex)}"
            )
        self.load_metadata_changes()
        if self.standard == "PDS4":
            return
        if primary_format is not None:
            self._init_primary_format()
            return
        self.pointers = get_pds3_pointers(self.metadata)
        # if self.pointers is None, we've probably got a weird edge case where
        # someone directly opened a PVL file that's not an individual product
        # label (e.g. a format file or a non-PDS PVL file) -- but there's no
        # reason to not allow them to use PDR as a PVL parser.
        if self.pointers is not None:
            self._find_objects()
        self.identifiers = self.metadata.identifiers

    # noinspection PyProtectedMember
    def load_metadata_changes(self):
        if "_metaget_interior" in dir(self):
            self.metadata.refresh_cache()
        self._metaget_interior = self.metadata._metaget_interior
        self._metablock_interior = self.metadata._metablock_interior

    def _init_pds4(self):
        """use pds4_tools to open pds4 files, but in our interface idiom."""

        import pdr.pds4_tools as pds4

        structure_list = pds4.read(
            self.labelname, lazy_load=True, quiet=True, no_scale=True
        )
        for structure in structure_list.structures:
            self._pds4_structures[structure.id.replace(" ", "_")] = structure
            self.index.append(structure.id.replace(" ", "_"))
        self._pds4_structures["label"] = structure_list.label
        self.index.append("label")

    def _init_search_path(self) -> str:
        """
        Set initial path this object will check for additional files (just the
        directory that contains its "primary" file).
        """
        for target in ("labelname", "filename"):
            if (target in dir(self)) and (target is not None):
                return str(Path(self.getattr(target)).absolute().parent)
        raise FileNotFoundError

    def _find_objects(self):
        """
        Add all top-level data objects mentioned in the label to this object's
        index, except for 'trivial' one (see `loaders.utility.is_trivial()`).
        """
        from pdr.loaders.utility import is_trivial

        # TODO: make this not add objects again if called multiple times
        for pointer in self.pointers:
            object_name = depointerize(pointer)
            if is_trivial(object_name):
                continue
            self.index.append(object_name)

    def _object_to_filename(
        self, object_name: str
    ) -> Union[str, list[str], Optional[tuple[Path, ...]]]:
        """
        Construct one or more on-disk search paths for the file that contains
        a named data object. Does not actually check if files exist at those
        paths (typically performed by calls to `utils.check_cases()).
        """
        is_special, special_target = check_special_fn(
            self, object_name, self.identifiers
        )
        if is_special is True:
            return self.get_absolute_paths(special_target)
        is_comp, comp_paths = self._check_compressed_file_pointer(object_name)
        if is_comp is True:
            return comp_paths
        target = self.metaget_(pointerize(object_name))
        if isinstance(target, Sequence) and not (isinstance(target, str)):
            if isinstance(target[0], str):
                target = target[0]
        if isinstance(target, str):
            return self.get_absolute_paths(target)
        else:
            return self.filename

    def _check_compressed_file_pointer(
        self, object_name: str
    ) -> tuple[bool, Optional[tuple[Path, ...]]]:
        """
        When PDS3 labels describe data objects in compressed files, they often
        give the names that the compressed files _would_ have, were someone to
        decompress them, as the physical locations of those objects. This can
        be confusing, because you cannot load an object from a merely
        hypothetical file.

        However, this is by no means a strict convention, so we can't just
        assume that it's the case -- we have to check all the file names
        mentioned for that object in the label, including those not given as
        top-level pointers.
        """
        compkeys = {"COMPRESSED_FILE", "UNCOMPRESSED_FILE"}
        if (
            len(compkeys.intersection(self.metadata.keys())) == 2
            and object_name in self.metablock_("UNCOMPRESSED_FILE").keys()
        ):
            blocks = filter(None, [self.metaget_(k) for k in compkeys])
            filenames = filter(None, [b.get("FILE_NAME") for b in blocks])
            return True, tuple(
                chain.from_iterable(map(self.get_absolute_paths, filenames))
            )
        return False, None

    def _target_path(
        self,
        object_name: str,
        cached: bool = True,
        raise_missing: bool = False
    ) -> Optional[Union[Path, list[Path], str]]:
        """
        Considering all known search paths and treating filenames as
        case-insensitive, attempt to find a filesystem path to a
        file or files in which a particular named data object might exist.
        This autopopulates self.file_mapping[object_name] if it finds one or
        more files, and by default treats this value as cached on subsequent
        calls (which can improve performance significantly, especially on
        networked filesystems).
        """
        if cached is True and (self.file_mapping.get(object_name) is not None):
            return self.file_mapping[object_name]
        try:
            if isinstance(object_name, set):
                file_list = [self._target_path(obj) for obj in object_name]
                self.file_mapping[object_name] = file_list
                return file_list
            path = check_cases(self._object_to_filename(object_name))
            self.file_mapping[object_name] = path
            return path
        except FileNotFoundError:
            if raise_missing is True:
                raise
            return None

    def unloaded(self) -> tuple[str]:
        """Return names of all identified but unloaded data objects."""
        return tuple(filter(lambda k: k not in dir(self), self.index))

    def load(self, name: str, reload: bool = False, **load_kwargs: Any):
        """
        Explicitly load an identified data object by name; alternatively
        `name="all"` means "load every identified object". Does not return the
        object; just assigns it to the `name` attribute of `self`. The
        `Data.__getitem__()` interface lazy-loads by calling this function
        with default arguments in response to `data['NOTYETLOADED']` etc.
        """
        # prelude: don't try to load nonexistent keys; facilitate
        # load-everything behavior; don't reload by default
        if (name != "all") and (name not in self.index):
            raise KeyError(f"{name} not found in index: {self.index}.")
        if name == "all":
            return self.load_all()
        if (name in dir(self)) and (reload is False):
            raise AlreadyLoadedError(
                f"{name} is already loaded; pass reload=True to "
                f"force reload."
            )
        if self.standard == "PDS4":
            return self._load_pds4(name)
        if self.standard == "FITS":
            self._add_loaded_objects(self._load_primary_fits(name))
            return
        if self.standard in DESKTOP_IMAGE_STANDARDS:
            from pdr.loaders.handlers import handle_compressed_image

            if self.metaget("n_frames", 1) == 1:
                self._add_loaded_objects(
                    {name: handle_compressed_image(self.filename)}
                )
                return
            # TODO: hacky!
            if self.standard == 'MPO' and name == 'IMAGE':
                seek = 0
            else:
                seek = int(name.split("_")[-1])
            self._add_loaded_objects(
                {name: handle_compressed_image(self.filename, seek)}
            )
            return
        if self.file_mapping.get(name) is None:
            target = self._target_path(name)
            if target is None:
                return self._file_not_found(name)
            self.file_mapping[name] = target
        try:
            obj = self.load_from_pointer(name, **load_kwargs)
            if obj is None:
                return
            if not isinstance(obj, dict):
                raise TypeError(
                    f"loader returned non-dict object of type ({type(obj)}"
                )
            self._add_loaded_objects(obj)
            return
        except DebugExceptionPreempted:
            pass
        except KeyboardInterrupt:
            raise
        except NotImplementedError as ex:
            warnings.warn(f"This product's {name} is not yet supported: {ex}.")
        except FileNotFoundError as _ex:
            warnings.warn(f"Unable to find files required by {name}.")
        except Exception as ex:
            warnings.warn(f"Unable to load {name}: {ex}")
        setattr(self, name, self.metaget_(name))

    def _add_loaded_objects(self, obj: Mapping[str, Any]):
        """Helper for `load()`. Ingests objects returned by a `Loader`."""
        for k, v in obj.items():
            if v is not None:
                setattr(self, k, v)
                if k not in self.index:
                    self.index.append(k)

    def load_all(self):
        """Handler (and alias) for `Data.load("all")`."""
        from pdr.loaders.dispatch import OBJECTS_IGNORED_BY_DEFAULT

        for name in self.keys():
            if OBJECTS_IGNORED_BY_DEFAULT.match(name):
                continue
            try:
                self.load(name)
            except AlreadyLoadedError:
                continue

    def _file_not_found(self, object_name: str):
        """Implements default file-not-found behavior."""
        warnings.warn(
            f"{object_name} file {self._object_to_filename(object_name)} "
            f"not found in path."
        )
        return_default = self.metaget_(object_name)
        maybe = catch_return_default(
            self.debug, return_default, FileNotFoundError()
        )
        setattr(self, object_name, maybe)

    def _load_primary_fits(
        self, object_name: str
    ) -> Union[np.ndarray, pd.DataFrame, None]:
        """Handle loading an HDU from a FITS file in "primary" FITS mode."""
        from pdr.loaders.handlers import handle_fits_file

        obj = handle_fits_file(
            self.filename,
            object_name,
            self._hdumap[object_name],
            self._hdulist,
            hdu_id_is_index=True
        )
        if obj.__class__.__name__ == "ndarray":
            self._scaleflags[object_name] = True
        return obj

    def _init_primary_format(self):
        """
        Initialization handler for "primary" format modes (cases in which
        `Data` offers an interface to a file or files in a standard format).
        Currently only supports FITS and 'desktop' image formats.
        """
        if self.standard == "FITS":
            for k in self.metadata.keys():
                self.index.append(k)
            return
        elif self.standard in DESKTOP_IMAGE_STANDARDS:
            return self._add_compressed_image_objects()
        raise NotImplementedError(f"unrecognized standard {self.standard}")

    def _add_compressed_image_objects(self):
        if (nframes := self.metaget("n_frames", 1)) == 1:
            self.index.append("IMAGE")
            return
        if self.standard in ('GIF', 'WEBP'):
            self.index += [f"FRAME_{i}" for i in range(nframes)]
        elif self.standard == 'MPO':
            mpentries = [d['Attribute'] for d in self.metaget('MPEntry')]
            if mpentries[0]['MPType'] != 'Baseline MP Primary Image':
                raise NotImplementedError("Non-primary first MPO image")
            images = ['IMAGE']
            for i, d in enumerate(mpentries[1:]):
                tname = re.sub(r'[() ]', '_', d['MPType'])
                images.append(f"{tname}_{i + 1}")
            self.index += images
        else:
            raise NotImplementedError(
                f"multiframe {self.standard} images are not yet supported."
            )

    # TODO, maybe: this can result in different keys of self referring to
    #  duplicate header objects, one like "object_name_HEADER" and one like
    #  "HEADER_0", etc. This can also happen for PDS3, so maybe this is just
    #  an acceptable interface idiom.
    def _find_fits_header_pds4_id(self, start_byte: int) -> Optional[str]:
        """
        Given start byte for an HDU's data segment, check to see if the
        PDS4 product associated with self includes that HDU's header as a
        distinct data object with a local identifier. If it is, return the
        PDS4 local identifier of that object. If not, return None.
        """
        for k, v in self._pds4_structures.items():
            meta = v.meta_data
            if meta['offset'] + meta['object_length'] == start_byte:
                if 'name' not in meta.keys():
                    return None
                return meta['name'].replace(' ', '_')

        return None

    def _load_pds4(self, object_name: str):
        """
        Load this object however pds4_tools wants to load this object, then
        reformat to DataFrame, expose the array handle in accordance with our
        type conventions, etc.

        If the object is from a FITS file, preempt all that behavior and send
        it to our internal FITS-loading workflow.
        """
        structure = self._pds4_structures[object_name]
        from pdr.pds4_tools.reader.label_objects import Label

        if isinstance(structure, Label):
            setattr(self, "label", structure)
        elif check_primary_fmt(structure.parent_filename) == "FITS":
            from pdr.loaders.handlers import handle_fits_file

            offset = structure.meta_data['offset']
            result = handle_fits_file(
                structure.parent_filename, object_name, offset
            )
            if structure.is_header() is True:
                return self._add_loaded_objects(result)
            if f"{object_name}_HEADER" not in self.index:
                hid = self._find_fits_header_pds4_id(offset)
                result[hid] = result.pop(f"{object_name}_HEADER")
            if structure.is_array() is True:
                self._scaleflags[object_name] = True
            self._add_loaded_objects(result)
        elif structure.is_array():
            import numpy as np

            setattr(self, object_name, np.asarray(structure.data))
        elif structure.is_table():
            from pdr.pd_utils import structured_array_to_df

            df = structured_array_to_df(structure.data)
            df.columns = df.columns.str.replace(r"GROUP_?\d+", "", regex=True)
            df.columns = df.columns.str.strip(", ")
            setattr(self, object_name, df)
        # TODO: do other important cases exist?
        else:
            setattr(self, object_name, structure.data)

    def read_metadata(self, pvl_limit: int = DEFAULT_PVL_LIMIT) -> Metadata:
        """
        Attempt to ingest a product's metadata. if it is a PDS4 product,
        pds4_tools will already have ingested its detached XML label in
        Data._init_pds4(). In that case, simply preprocess it for
        Metadata.__init__.
        Otherwise, if it has a detached PDS3/PVL label, ingest it with
        pdr.parselabel.pds3.read_pvl.
        Then, if we found no detached label, look for an attached PVL
        label (also using read_pvl).
        If we are in a "primary" mode, ignore all that and ingest the product's
        metadata with the appropriate format-specific functions.
        Then, construct a Metadata object from whatever we loaded and add all
        the objects it implies to our index.
        """
        if self.standard == "FITS":
            from pdr.loaders.handlers import unpack_fits_headers

            mapping, params, self._hdumap = unpack_fits_headers(
                self.filename, hdulist=self._hdulist
            )
            return Metadata((mapping, params), standard="FITS")
        if self.standard == "PDS4":
            return Metadata(
                reformat_pds4_tools_label(self.label), standard="PDS4"
            )
        if self.standard in DESKTOP_IMAGE_STANDARDS:
            from pdr.pil_utils import skim_image_data, paramdig

            return Metadata(paramdig(skim_image_data(self.filename)))
        # self.labelname is None means we didn't find a detached label
        target = self.filename if self.labelname is None else self.labelname
        metadata = Metadata(read_pvl(target, max_size=pvl_limit))
        # we wait until after the read step to make these assignments in order
        # to facilitate debugging in cases where there is not in fact an
        # attached label or we couldn't read it
        self.labelname, self.file_mapping["LABEL"] = target, target
        self.index.append("LABEL")
        return metadata

    def load_from_pointer(
        self, pointer: str, **load_kwargs: Any
    ) -> dict[
        str, Union[pd.DataFrame, np.ndarray, str, MultiDict, "PVLModule"]
    ]:
        """
        PDS3 data object-loading handler. Set up the appropriate `Loader` for
        the object, set up load flow tracking, call the loader, and perform
        basic cleanup.
        """
        from pdr.loaders.dispatch import pointer_to_loader

        loader = pointer_to_loader(pointer, self)
        if self.debug is True:
            loader = Dynamic.from_function(loader, optional=True)
        self.loaders[pointer] = loader
        self.tracker.set_metadata(
            filename=self.file_mapping[pointer], obj=pointer
        )
        obj = self.loaders[pointer](
            self, pointer, tracker=self.tracker, **load_kwargs
        )
        # FITS arrays are scaled by default, and most 'desktop' images never
        # require scaling. we currently treat GeoTIFFs and JP2 as the only
        # exceptions.
        # TODO: assess whether there are non-GeoTIFF TIFFs floating around in
        #  the PDS that might still require scaling.
        unwrap = loader.func.__self__ if self.debug is True else loader
        if (
            (unwrap.__class__.__name__ == "ReadFits")
            and (obj[pointer].__class__.__name__ == "ndarray")
        ):
            self._scaleflags[pointer] = True
        if (
            (unwrap.__class__.__name__ == 'ReadCompressedImage')
            and (obj[pointer].__class__.__name__ == "ndarray")
        ):
            from pdr.loaders.handlers import _check_prescaled_desktop

            self._scaleflags[pointer] = _check_prescaled_desktop(
                self.file_mapping[pointer]
            )
        if self.debug is True and len(loader.errors) > 0:
            warnings.warn(
                f"Unable to load {pointer}: {loader.errors[-1]['exception']}"
            )
            raise DebugExceptionPreempted
        return obj

    def get_scaled(
        self,
        object_name: str,
        inplace: bool = False,
        float_dtype: Optional[np.dtype] = None
    ) -> np.ndarray:
        """
        fetches copy of data object corresponding to key, masks special
        constants, then applies any scale and offset specified in the label.
        only relevant to arrays.

        if `inplace` is True, does calculations in-place on original array,
        with attendant memory savings and destructiveness.
        """
        obj = self[object_name]
        # avoid numpy import just for type check
        if obj.__class__.__name__ != "ndarray":
            raise TypeError("get_scaled is only applicable to arrays.")
        if self._scaleflags.get(object_name) is True:
            return obj
        if self.standard == "PDS4":
            from pdr._scaling import scale_pds4_tools_struct

            # Do whatever pds4_tools would most likely do with these data.
            # TODO: shake this out much more vigorously. perhaps make
            #  the inplace and float_dtype arguments do something.
            #  check and see if implicit special constants ever still exist
            #  stealthily in PDS4 data. etc.
            return scale_pds4_tools_struct(self._pds4_structures[object_name])

        # TODO: double-check that astropy is successfully handling masking
        # TODO: most 'desktop' image formats should never contain special
        #  constants, but some (e.g. JP2) may be able to? check.
        if self.standard != "PDS3":
            return obj

        from pdr._scaling import mask_specials, scale_array

        if object_name not in self.specials:
            self.specials[object_name] = self.find_special_constants(
                object_name
            )
        if self.specials[object_name] != {}:
            obj = mask_specials(obj, list(self.specials[object_name].values()))
        return scale_array(self, obj, object_name, inplace, float_dtype)

    def find_special_constants(self, object_name: str) -> dict[str, Number]:
        """
        look up or infer special constants for one of our data objects.
        in general, only works well on ndarrays.
        """
        if len(consts := special_image_constants(self.identifiers)) > 0:
            return consts

        from pdr._scaling import find_special_constants

        return find_special_constants(self, self[object_name], object_name)

    def metaget(
        self, text: str, default: Any = None, warn: bool = True
    ) -> Any:
        """
        get the first value from this object's metadata whose key exactly
        matches `text`, even if it is nested inside a mapping. evaluate it
        using `self.metadata.formatter`.

        Warning:
            this function's return values are memoized for performance.
            updating elements of self.metadata that have already been accessed
            with this function will not update future calls to this function.
        """
        return self.metadata.metaget(text, default, warn)

    def metaget_(self, text: str, default: Any = None) -> Any:
        """quiet-by-default version of metaget"""
        return self.metadata.metaget(text, default, False)

    def metablock(self, text: str, warn: bool = True) -> Optional[Mapping]:
        """
        get the first value from this object's metadata whose key exactly
        matches `text`, even if it is nested inside a mapping, if the value
        itself is a mapping (e.g., nested PVL block, XML 'area', etc.)
        evaluate it using self.metadata.formatter. if there is no key matching
        'text', will evaluate and return the metadata as a whole.
        WARNING: this function's return values are memoized for performance.
        updating elements of self.metadata that have already been accessed
        with this function will not update future calls to this function.
        """
        return self.metadata.metablock(text, warn)

    def metablock_(self, text: str) -> Optional[Mapping]:
        """quiet-by-default version of metablock"""
        return self.metadata.metablock(text, False)

    def get_absolute_paths(self, filename: Union[str, Path]) -> list[str]:
        """
        Construct `Path`s for a filename in all our search paths. (These are
        places we can look for that file).
        """
        return gmap(
            lambda sf: Path(*sf).absolute(),
            product(self.search_paths, listify(filename)),
            evaluator=list,
        )

    # TODO: reorganize this -- common dispatch funnel with dump_browse,
    #  split up the image-gen part of _browsify_array, something like that
    def show(
        self,
        object_name: str = None,
        scaled: bool = True,
        **browse_kwargs: Any
    ) -> Image:
        """
        Produce an Image from a data object associated with this product. A
        convenient way to quickly look at data.
        """
        if object_name is None:
            raise ValueError(
                f"please specify the name of an image object. "
                f"keys include {self.index}"
            )
        if not self[object_name].__class__.__name__ == "ndarray":
            raise TypeError("Data.show only works on array data.")
        if scaled is True:
            obj = self.get_scaled(object_name)
        else:
            obj = self[object_name]
        # no need to have all this mpl stuff in the namespace normally
        from pdr.browsify import _browsify_array

        return _browsify_array(obj, save=False, outbase="", **browse_kwargs)

    def dump_browse(
        self,
        prefix: Optional[Union[str, Path]] = None,
        outpath: Optional[Union[str, Path]] = None,
        scaled: bool = True,
        purge: bool = False,
        **browse_kwargs: Any,
    ) -> None:
        """
        attempt to dump all data objects associated with this Data object
        to disk.

        By default, writes files to the working directory.

        By default, assigns filenames like:
        {filename stem}_{object name}.{file extension}

        So, for instance, a browse version of a TABLE object referenced from
        "jn23a1.lbl" would be written to  "jn23a1_TABLE.csv".

        If prefix is not None, filenames will begin with the value of prefix
        rather than the original filename stem.

        If outpath is not None, files will be written to the value of outpath
        rather than to the working directory.

        By default, attempts to apply scaling/offset factors and special
        constant masking before writing images. If scaled is False, does not
        do that. If scaled == "both", writes both scaled and unscaled
        versions, adding "_scaled" and "_unscaled" to their respective
        filenames before the file extension. Note that some types of load
        operations (like for FITS files) may have already applied scaling
        factors, in which case recovering the unscaled image is not possible.

        if purge is True, objects are deleted as soon as they are dumped,
        rendering this Data object 'empty' afterward.

        **browse_kwargs are passed directly to browsify.browsify(), and
        offer various ways to modify image dumping behavior:

        - image_clip: Union[float, tuple[float, float], None] = None
            Applies a percentile clip to the image at
            clip = (low_percentile, 100-high_percentile).
            If clip is a single value, low_percentile=high_percentile
            in the above formula. If it's a tuple, low_percentile is
            the first value in the tuple.

            The default None value causes 'nice' clipping: it clips the image
            at (1, 1), but if this results in the clipped image containing only
            a single value, it uses the original image instead. Pass 0 if
            absolutely no clipping is desired.

        - mask_color: Optional[tuple[int, int, int]] = (0, 255, 255)
            Allows specification of RGB color for masked arrays (default cyan)

        - band_ix: Optional[int] = None
            The index of the band to be exported in a multiband image. If None,
            the middle band of the image is exported. If there are 3-4 bands in
            the image and the override_rgba argument is False, this value is
            ignored.

            When set equal to "burst", returns a separate browse product for
            each band of a multiband image, appending numbers to the filenames
            prior to the file extension.

        - save: bool = True
            If False, renders images in memory but does not save them to disk.
            Not generally useful when passed to this method except for testing.

        - override_rgba: bool = False
            Allows use of band_ix when there are 3-4 bands in the image.
            Otherwise, the image will be returned as a stacked rgb image
            (the assumed 'alpha' channel is always dropped). Setting this to
            True is useful when a 3/4 band image is not actually RGB(A) (e.g.
            XYZ spatial products).

            This argument has no effect on images that do not have 3-4 bands.

        - image_format: str = "jpg"
            Sets image extension which informs the format pillow will save the
            browse image as.

        - slice_axis: int = 0
            Allows specification of which axis to slice along for the
            dump_browse image. The default slices at axis 0 (which is usually
            the axis labelled "BAND").

        """
        if prefix is None:
            prefix = Path(self.filename).stem
        if outpath is None:
            outpath = Path(".")
        for obj in filter(lambda i: i in dir(self), self.index):
            outfile = str(Path(outpath, f"{prefix}_{obj}"))
            # no need to have all this mpl stuff in the namespace normally
            from pdr.browsify import browsify

            dump_it = partial(browsify, purge=purge, **browse_kwargs)
            fdt = browse_kwargs.get("float_dtype")
            if (
                self[obj].__class__.__name__ == "ndarray"
                and len(self[obj].shape) != 1
            ):
                if scaled == "both":
                    dump_it(
                        self.get_scaled(obj, float_dtype=fdt),
                        outfile + "_scaled",
                        purge=False,
                    )
                    dump_it(self[obj], outfile + "_unscaled")
                elif scaled is True:
                    dump_it(
                        self.get_scaled(obj, inplace=purge, float_dtype=fdt),
                        outfile,
                    )
                elif scaled is False:
                    dump_it(self[obj], outfile)
                else:
                    raise ValueError(f"unknown scaling argument {scaled}")
            else:
                dump_it(self[obj], outfile)
            if purge is True:
                self.__delattr__(obj)

    def __getattribute__(self, attr: str) -> Any:
        """
        Get an attribute of self; known data objects can be referred to
        using attribute notation.
        """
        try:
            return super().__getattribute__(attr)
        except AttributeError:
            if attr not in self.index:
                raise
        self.load(attr)
        return super().__getattribute__(attr)

    # This method exists as a bypass for the special behavior of
    # __getattribute__.  All code reachable from load() must take
    # care when accessing attributes of self in order to avoid an
    # infinite lazy-load loop; this makes that more convenient.
    def getattr(self, attr):
        """
        get an attribute of self without either lazy-loading on failure or
        risking infinite loops inside lazy-load behaviors.
        """
        return super().__getattribute__(attr)

    # The following three functions make this object act sort of dict-like
    #  in useful ways for data exploration.
    def keys(self) -> list[str]:
        """
        Returns names of all data objects defined in the label (or inferred
        while loading an object, like FITS headers).
        """
        return self.index

    def __contains__(self, name: str) -> bool:
        """True if self contains a data object with the name 'name'."""
        return name in self.index

    # make it possible to get data objects with slice notation, like a dict
    def __getitem__(self, name: str) -> Any:
        """
        Return the contained data object with the name 'name'.
        """
        if name not in self.index:
            warnings.warn("in a future release Data[name] will accept only"
                          " names of data objects, not other properties",
                          DeprecationWarning, stacklevel=1)
        return self.__getattribute__(name)

    def __repr__(self):
        """"""
        rep = f"pdr.Data({self.filename})\nkeys={self.keys()}"
        if len(self.unloaded()) > 0:
            rep += f"\nnot yet loaded: {self.unloaded()}"
        return rep

    def __str__(self):
        """"""
        return self.__repr__()

    def __len__(self):
        """
        Return the number of data objects contained in self.
        """
        return len(self.index)

    def __iter__(self) -> Iterator[Any]:
        """
        Iterate over all the data objects contained in self.
        Iteration all the way to the end will cause all of the data
        objects to be loaded, which may run your computer out of memory.
        For this reason, iteration over Data objects is deprecated
        and will be removed in six months.
        """
        warnings.warn("iteration over Data objects is deprecated"
                      " as it can crash your computer",
                      DeprecationWarning, stacklevel=1)
        for key in self.keys():
            yield self[key]

    _metaget_interior: Callable[[str, Any], Any]
    _metablock_interior: Callable[[str], Mapping]


def _metaget_factory(metadata: Metadata) -> Callable[[str, Any], Any]:

    def metaget_interior(text, default):
        """"""
        value = dig_for_value(metadata, text, mtypes=(dict, MultiDict))
        return default if value is None else value

    return cache(metaget_interior)


def _metablock_factory(metadata: Metadata) -> Callable[[str], Mapping]:
    """
    Factory function for an internal component of `metablock()`. Reduces the
    risk that the metadata access cache will create reference cycles.
    """
    def metablock_interior(text):
        """"""
        value = dig_for_value(metadata, text, mtypes=(dict, MultiDict))
        if not isinstance(value, Mapping):
            return metadata
        return value

    return cache(metablock_interior)
