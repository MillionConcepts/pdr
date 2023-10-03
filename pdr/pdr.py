import warnings
from functools import partial, cache
from itertools import chain, product
from pathlib import Path
from typing import (
    Mapping,
    Optional,
    Union,
    Sequence,
    Collection,
)

import Levenshtein as lev
from cytoolz import countby, identity
from dustgoggles.dynamic import Dynamic
from dustgoggles.func import gmap
from dustgoggles.structures import dig_for_value, listify
from dustgoggles.tracker import Tracker, TrivialTracker
from multidict import MultiDict

from pdr.errors import AlreadyLoadedError, DuplicateKeyWarning
from pdr.formats import (
    check_special_fn,
    special_image_constants,
)
from pdr.parselabel.pds3 import (
    get_pds3_pointers,
    pointerize,
    depointerize,
    read_pvl,
    literalize_pvl,
)
from pdr.parselabel.pds4 import reformat_pds4_tools_label
from pdr.parselabel.utils import DEFAULT_PVL_LIMIT
from pdr.utils import (
    check_cases,
    prettify_multidict,
    associate_label_file,
    catch_return_default, check_primary_fmt,
)


ID_FIELDS = (
    # used during special case checks
    "INSTRUMENT_ID",
    "INSTRUMENT_NAME",
    "SPACECRAFT_NAME",
    "PRODUCT_TYPE",
    "DATA_SET_NAME",
    "DATA_SET_ID",
    "STANDARD_DATA_PRODUCT_ID",
    "FILE_NAME",
    "INSTRUMENT_HOST_NAME",
    "PRODUCT_TYPE",
    "PRODUCT_ID",
    "RECORD_BYTES",
    "RECORD_TYPE",
    "ROW_BYTES",
    "ROWS",
    "FILE_RECORDS",
    "LABEL_RECORDS",
    "NOTE",
)


class Metadata(MultiDict):
    """
    MultiDict subclass intended primarily as a helper class for Data.
    includes various convenience methods for handling metadata syntaxes,
    common access and display interfaces, etc.
    """

    def __init__(self, mapping_params, standard="PDS3", **kwargs):
        mapping, params = mapping_params
        super().__init__(mapping, **kwargs)
        self.fieldcounts = countby(identity, params)
        self.standard = standard
        if self.standard == "PDS3":
            self.formatter = literalize_pvl
        elif self.standard in ("PDS4", "FITS"):
            # we're trusting that pds4_tools and/or our astropy wrapper
            # stringified everything correctly.
            # also note that this has no
            # default capacity to describe PDS4 units -- you have to
            # explicitly check the 'attrib' attribute of the XML node,
            # which is not preserved by Label.to_dict().
            # TODO: replace pds4_tools' Label.to_dict() with our own
            #  literalizer function.
            self.formatter = identity
        else:
            raise NotImplementedError(
                "Syntaxes other than PDS3-style PVL, preprocessed PDS4 XML,"
                "and preprocessed FITS headers are not yet implemented."
            )
        # note that 'directly' caching these methods can result in recursive
        # reference chains behind the lru_cache API that can prevent the
        # Metadata object from being garbage-collected, which is why they are
        # hidden behind these wrappers. there may be a cleaner way to do this.
        self._metaget_interior = _metaget_factory(self)
        self._metablock_interior = _metablock_factory(self)

    def __getitem__(self, key):
        value = super().__getitem__(key)
        return self.formatter(value)

    def metaget(self, text, default=None, evaluate=True, warn=True):
        """
        get the first value from this object whose key exactly
        matches `text`, even if it is nested inside a mapping. optionally
        evaluate it using self.formatter. raise a warning if there are
        multiple keys matching this.
        WARNING: this function's return values are memoized for performance.
        updating elements of self that have already been accessed
        with this function will not update future calls to this function.
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
        return self._metaget_interior(text, default, evaluate)

    def metaget_(self, text, default=None, evaluate=True):
        """quiet-by-default version of metaget"""
        return self.metaget(text, default, evaluate, False)

    def metaget_fuzzy(self, text, evaluate=True):
        levratio = {
            key: lev.ratio(key, text) for key in set(self.fieldcounts.keys())
        }
        if levratio == {}:
            return None
        peak = max(levratio.values())
        for k, v in levratio.items():
            if v == peak:
                return self.metaget(k, None, evaluate)

    def metablock(self, text, evaluate=True, warn=True):
        """
        get the first value from this object whose key exactly
        matches `text`, even if it is nested inside a mapping, if the value
        itself is a mapping (e.g., nested PVL block, XML 'area', etc.)
        evaluate it using self.formatter. raise a warning if there are
        multiple keys matching this.
        if there is no key matching 'text', will evaluate and return the
        metadata as a whole.
        WARNING: this function's return values are memoized for performance.
        updating elements of self that have already been accessed
        with this function and then calling it again will result in
        unpredictable behavior.
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
        return self._metablock_interior(text, evaluate)

    def metablock_(self, text, evaluate=True):
        """quiet-by-default version of metablock"""
        return self.metablock(text, evaluate, False)

    def __str__(self):
        return f"Metadata({prettify_multidict(self)})"

    def __repr__(self):
        return f"Metadata({prettify_multidict(self)})"


class DebugExceptionPreempted(Exception):
    pass


class Data:
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
        self.search_paths = [self._init_search_paths()] + listify(search_paths)
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
        self._metaget_interior = _metaget_factory(self.metadata)
        self._metablock_interior = _metablock_factory(self.metadata)
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
        self.identifiers = {
            field: self.metaget_(field, "") for field in ID_FIELDS
        }

    def _init_pds4(self):
        # Just use pds4_tools if this is a PDS4 file
        import pds4_tools as pds4

        structure_list = pds4.read(
            self.labelname, lazy_load=True, quiet=True, no_scale=True
        )
        for structure in structure_list.structures:
            self._pds4_structures[structure.id.replace(" ", "_")] = structure
            self.index.append(structure.id.replace(" ", "_"))
        self._pds4_structures["label"] = structure_list.label
        self.index.append("label")

    def _init_search_paths(self):
        for target in ("labelname", "filename"):
            if (target in dir(self)) and (target is not None):
                return str(Path(self.getattr(target)).absolute().parent)
        raise FileNotFoundError

    def _find_objects(self):
        from pdr.loaders.utility import is_trivial

        # TODO: make this not add objects again if called multiple times
        for pointer in self.pointers:
            object_name = depointerize(pointer)
            if is_trivial(object_name):
                continue
            self.index.append(object_name)

    def _object_to_filename(self, object_name):
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
        # TODO: should we move every check_cases call here?
        if isinstance(target, str):
            return self.get_absolute_paths(target)
        else:
            return self.filename

    def _check_compressed_file_pointer(self, object_name):
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

    def _target_path(self, object_name, cached=True, raise_missing=False):
        """
        find the path on the local filesystem to the file containing a named
        data object. autopopulate the file_mapping
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

    def unloaded(self):
        return tuple(filter(lambda k: k not in dir(self), self.index))

    def load(self, name, reload=False, **load_kwargs):
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
                raise TypeError(f"loader returned non-dict object of type ({type(obj)}")
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

    def _add_loaded_objects(self, obj):
        for k, v in obj.items():
            if v is not None:
                setattr(self, k, v)
                if k not in self.index:
                    self.index.append(k)

    def load_all(self):
        from pdr.loaders.dispatch import OBJECTS_IGNORED_BY_DEFAULT

        for name in self.keys():
            if OBJECTS_IGNORED_BY_DEFAULT.match(name):
                continue
            try:
                self.load(name)
            except AlreadyLoadedError:
                continue

    def _file_not_found(self, object_name):
        warnings.warn(
            f"{object_name} file {self._object_to_filename(object_name)} "
            f"not found in path."
        )
        return_default = self.metaget_(object_name)
        maybe = catch_return_default(
            self.debug, return_default, FileNotFoundError()
        )
        setattr(self, object_name, maybe)

    def _load_primary_fits(self, object_name):
        from pdr.loaders.handlers import handle_fits_file

        obj = handle_fits_file(
            self.filename,
            object_name,
            self._hdumap[object_name],
            self._hdulist
        )
        if obj.__class__.__name__ == "ndarray":
            self._scaleflags[object_name] = True
        return obj

    def _init_primary_format(self):
        if self.standard == "FITS":
            for k in self.metadata.keys():
                self.index.append(k)
            return
        raise NotImplementedError

    def _load_pds4(self, object_name):
        """
        load this object however pds4_tools wants to load this object, then
        reformat to df or expose the array handle in accordance with our type
        conventions.
        """
        structure = self._pds4_structures[object_name]
        from pds4_tools.reader.label_objects import Label

        if isinstance(structure, Label):
            setattr(self, "label", structure)
        elif structure.is_array():
            setattr(self, object_name, structure.data)
        elif structure.is_table():
            from pdr.pd_utils import structured_array_to_df

            df = structured_array_to_df(structure.data)
            df.columns = df.columns.str.replace(r"GROUP_?\d+", "", regex=True)
            df.columns = df.columns.str.strip(", ")
            setattr(self, object_name, df)
        # TODO: do other important cases exist?
        else:
            setattr(self, object_name, structure.data)

    def read_metadata(self, pvl_limit=DEFAULT_PVL_LIMIT):
        """
        Attempt to ingest a product's metadata. if it is a PDS4 product,
        pds4_tools will already have ingested its detached XML label in
        Data._init_pds4(). In that case, simply preprocess it for
        Metadata.__init__.
        Otherwise, if it has a detached PDS3/PVL label, ingest it with
        pdr.parselabel.pds3.read_pvl_label.
        Finally, if we have found no detached label, look for an attached PVL
        label (also using read_pvl_label).
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
        # self.labelname is None means we didn't find a detached label
        target = self.filename if self.labelname is None else self.labelname
        metadata = Metadata(read_pvl(target, max_size=pvl_limit))
        # we wait until after the read step to make these assignments in order
        # to facilitate debugging in cases where there is not in fact an
        # attached label or we couldn't read it
        self.labelname, self.file_mapping["LABEL"] = target, target
        self.index.append("LABEL")
        return metadata

    def load_from_pointer(self, pointer, **load_kwargs):
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
        # FITS arrays are scaled by default
        if (
            (loader.__class__.__name__ == "ReadFits")
            and (obj.__class__.__name__ == "ndarray")
        ):
            self._scaleflags[pointer] = True
        if self.debug is True and len(loader.errors) > 0:
            warnings.warn(
                f"Unable to load {pointer}: {loader.errors[-1]['exception']}"
            )
            raise DebugExceptionPreempted
        return obj

    def get_scaled(
        self, object_name: str, inplace=False, float_dtype=None
    ) -> "np.ndarray":
        """
        fetches copy of data object corresponding to key, masks special
        constants, then applies any scale and offset specified in the label.
        only relevant to arrays.

        if inplace is True, does calculations in-place on original array,
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

        from pdr._scaling import (
            find_special_constants,
            mask_specials,
            scale_array,
        )

        if object_name not in self.specials:
            consts = special_image_constants(self.identifiers)
            self.specials[object_name] = consts
            if not consts:
                self.specials[object_name] = find_special_constants(
                    self.metadata, obj, object_name
                )
        if self.specials[object_name] != {}:
            obj = mask_specials(obj, list(self.specials[object_name].values()))
        return scale_array(self, obj, object_name, inplace, float_dtype)

    def metaget(self, text, default=None, evaluate=True, warn=True):
        """
        get the first value from this object's metadata whose key exactly
        matches `text`, even if it is nested inside a mapping. evaluate it
        using self.metadata.formatter.
        WARNING: this function's return values are memoized for performance.
        updating elements of self.metadata that have already been accessed
        with this function will not update future calls to this function.
        """
        return self.metadata.metaget(text, default, evaluate, warn)

    def metaget_(self, text, default=None, evaluate=True):
        """quiet-by-default version of metaget"""
        return self.metadata.metaget(text, default, evaluate, False)

    def metablock(self, text, evaluate=True, warn=True):
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
        return self.metadata.metablock(text, evaluate, warn)

    def metablock_(self, text, evaluate=True):
        """quiet-by-default version of metablock"""
        return self.metadata.metablock(text, evaluate, False)

    def get_absolute_paths(self, filename: Union[str, Path]) -> list[str]:
        return gmap(
            lambda sf: Path(*sf).absolute(),
            product(self.search_paths, listify(filename)),
            evaluator=list,
        )

    # TODO: reorganize this -- common dispatch funnel with dump_browse,
    #  split up the image-gen part of _browsify_array, something like that
    def show(self, object_name=None, scaled=True, **browse_kwargs):
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
        for obj in filter(lambda i: i in dir(self), self.index):
            outfile = str(Path(outpath, f"{prefix}_{obj}"))
            # no need to have all this mpl stuff in the namespace normally
            from pdr.browsify import browsify

            dump_it = partial(browsify, purge=purge, **browse_kwargs)
            fdt = browse_kwargs.get("float_dtype")
            if self[obj].__class__.__name__ == "ndarray" and len(self[obj].shape) != 1:
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

    def __getattribute__(self, attr):
        # provide a way to sidestep special behavior
        if attr == "getattr":
            return super().__getattribute__
        # do not infinitely check if the index is in itself
        if attr == "index":
            return self.getattr("index")
        # do not attempt to lazy-load attributes that are not data objects
        if attr not in self.getattr("index"):
            return self.getattr(attr)
        try:
            return self.getattr(attr)
        except AttributeError:
            # if an attribute name corresponds to the name of a known data
            # object and that attribute hasn't been assigned, load and return
            # the data object
            self.load(attr)
            return self.getattr(attr)

    # this is redundant with __getattribute__. it is repeated here for
    # clarity and to help enable static analysis.
    def getattr(self, attr):
        """
        get an attribute of self without either lazy-loading on failure or
        risking infinite loops inside lazy-load behaviors.
        """
        return super().__getattribute__(attr)

    # The following two functions make this object act sort of dict-like
    #  in useful ways for data exploration.
    def keys(self):
        # Returns the keys for observational data and metadata objects
        return self.index

    # make it possible to get data objects with slice notation, like a dict
    def __getitem__(self, item):
        return self.__getattribute__(item)

    def __repr__(self):
        rep = f"pdr.Data({self.filename})\nkeys={self.keys()}"
        if len(self.unloaded()) > 0:
            rep += f"\nnot yet loaded: {self.unloaded()}"
        return rep

    def __str__(self):
        return self.__repr__()

    def __len__(self):
        return len(self.index)

    def __iter__(self):
        for key in self.keys():
            yield self[key]


def _metaget_factory(metadata, cached=True):
    def metaget_interior(text, default, evaluate):
        value = dig_for_value(metadata, text, mtypes=(dict, MultiDict))
        if value is not None:
            return metadata.formatter(value) if evaluate is True else value
        return default

    if cached is True:
        return cache(metaget_interior)
    return metaget_interior


def _metablock_factory(metadata, cached=True):
    def metablock_interior(text, evaluate):
        value = dig_for_value(metadata, text, mtypes=(dict, MultiDict))
        if not isinstance(value, Mapping):
            value = metadata
        return metadata.formatter(value) if evaluate is True else value

    if cached is True:
        return cache(metablock_interior)
    return metablock_interior
