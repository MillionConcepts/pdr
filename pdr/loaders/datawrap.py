from typing import Union
from pdr.formats import check_special_sample_type, check_special_qube_band_storage, \
    check_special_position, check_special_structure
from pdr.func import get_argnames, softquery, specialize, call_kwargfiltered
from pdr.loaders._helpers import TrivialTracker, Tracker
from pdr.loaders.queries import DEFAULT_DATA_QUERIES, \
    base_sample_info, im_sample_type, check_if_qube, get_qube_band_storage_type, \
    generic_image_properties, get_return_default, check_debug, table_position, \
    parse_table_structure
from pdr.parselabel.pds3 import depointerize
from pdr.pdrtypes import LoaderFunction, PDRLike


class Loader:
    """
    compact wrapper for loader functions, intended principally but not solely
    for library-internal use. provides a common interface, adds compactness,
    delays imports, etc.
    """

    def __init__(self, loader_function: Union[LoaderFunction, str]):
        self.loader_function = loader_function
        self.argnames = get_argnames(loader_function)

    def __call__(self, pdrlike: PDRLike, name: str, debug_id=None, **kwargs):
        kwargdict = {'data': pdrlike, 'name': depointerize(name)} | kwargs
        if debug_id is None:
            kwargdict['tracker'] = TrivialTracker()
        else:
            kwargdict['tracker'] = Tracker(
                f"{debug_id}_{self.__class__.__name__}"
            )
        info = softquery(self.loader_function, self.queries, kwargdict)
        kwargdict['tracker'].track(self.loader_function)
        kwargdict['tracker'].dump()
        return call_kwargfiltered(self.loader_function, **info)

    queries = DEFAULT_DATA_QUERIES


class ReadImage(Loader):
    """wrapper for read_image"""

    def __init__(self):
        from pdr.loaders.image import read_image

        super().__init__(read_image)

    queries = DEFAULT_DATA_QUERIES | {

        'base_samp_info': base_sample_info,
        'sample_type': specialize(im_sample_type, check_special_sample_type),
        'band_storage_type': specialize(get_qube_band_storage_type,
                                        check_special_qube_band_storage),
        'gen_props': specialize(generic_image_properties, check_if_qube),
    }


class ReadTable(Loader):
    """wrapper for read_table"""

    def __init__(self):
        from pdr.loaders.table import read_table

        super().__init__(read_table)

    queries = DEFAULT_DATA_QUERIES | {
        'debug': check_debug,
        'return_default': get_return_default,
        'fmtdef_dt': specialize(parse_table_structure, check_special_structure),
        'table_props': specialize(table_position, check_special_position)
    }


class ReadHeader(Loader):
    """wrapper for read_header"""

    def __init__(self):
        from pdr.loaders.misc import read_header

        super().__init__(read_header)

    queries = DEFAULT_DATA_QUERIES | {
        'table_props': specialize(table_position, check_special_position)
    }


class ReadText(Loader):
    """wrapper for read_text"""

    def __init__(self):
        from pdr.loaders.misc import read_text

        super().__init__(read_text)


class ReadLabel(Loader):
    """wrapper for read_label"""

    def __init__(self):
        from pdr.loaders.misc import read_label

        super().__init__(read_label)


class ReadFits(Loader):
    """wrapper for handle_fits_file"""

    def __init__(self):
        from pdr.loaders.handlers import handle_fits_file

        super().__init__(handle_fits_file)


class ReadCompressedImage(Loader):
    """wrapper for handle_compressed_image"""

    def __init__(self):
        from pdr.loaders.handlers import handle_compressed_image

        super().__init__(handle_compressed_image)


class ReadArray(Loader):
    """wrapper for read_array"""

    def __init__(self):
        from pdr.loaders.table import read_array

        super().__init__(read_array)


class TBD(Loader):
    """wrapper for tbd"""

    def __init__(self):
        from pdr.loaders.utility import tbd

        super().__init__(tbd)