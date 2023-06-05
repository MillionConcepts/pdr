from typing import Union

from pdr.formats import (
    check_special_sample_type,
    check_special_qube_band_storage,
    check_special_position,
    check_special_structure,
    check_special_table_reader,
)
from pdr.func import get_argnames, softquery, specialize, call_kwargfiltered
from pdr.parselabel.pds3 import depointerize
from pdr.pdrtypes import LoaderFunction, PDRLike
from pdr.loaders.queries import DEFAULT_DATA_QUERIES


class Loader:
    """
    compact wrapper for loader functions, intended principally but not solely
    for library-internal use. provides a common interface, adds compactness,
    delays imports, etc.
    """

    def __init__(self, loader_function: Union[LoaderFunction, str]):
        self.loader_function = loader_function
        self.argnames = get_argnames(loader_function)

    def __call__(self, pdrlike: PDRLike, name: str, **kwargs):
        kwargdict = {"data": pdrlike, "name": depointerize(name)} | kwargs
        kwargdict["tracker"].set_metadata(loader=self.__class__.__name__)
        record_exc = {"status": "query_ok"}
        try:
            info = softquery(self.loader_function, self.queries, kwargdict)
        except Exception as exc:
            record_exc = {"status": "query_failed", "exception": str(exc)}
            raise exc
        finally:
            kwargdict["tracker"].track(self.loader_function, **record_exc)
            kwargdict["tracker"].dump()
        return {name: call_kwargfiltered(self.loader_function, **info)}
    queries = DEFAULT_DATA_QUERIES


class ReadImage(Loader):
    """wrapper for read_image"""

    def __init__(self):
        from pdr.loaders.image import read_image
        from pdr.loaders.queries import (
            base_sample_info,
            im_sample_type,
            check_if_qube,
            get_qube_band_storage_type,
            generic_image_properties,
        )

        super().__init__(read_image)
        self.queries = DEFAULT_DATA_QUERIES | {
            "base_samp_info": base_sample_info,
            "sample_type": specialize(
                im_sample_type, check_special_sample_type
            ),
            "band_storage_type": specialize(
                get_qube_band_storage_type, check_special_qube_band_storage
            ),
            "gen_props": specialize(generic_image_properties, check_if_qube),
        }


class ReadTable(Loader):
    """wrapper for read_table"""

    def __init__(self):
        from pdr.loaders.queries import table_position, parse_table_structure
        from pdr.loaders.table import read_table

        super().__init__(specialize(read_table, check_special_table_reader))
        self.queries = DEFAULT_DATA_QUERIES | {
            "table_props": specialize(table_position, check_special_position),
            "fmtdef_dt": specialize(
                parse_table_structure, check_special_structure
            ),
        }


class ReadHeader(Loader):
    """wrapper for read_header"""

    def __init__(self):
        from pdr.loaders.text import read_header
        from pdr.loaders.queries import table_position

        super().__init__(read_header)
        self.queries = DEFAULT_DATA_QUERIES | {
            "table_props": specialize(table_position, check_special_position)
        }


class ReadText(Loader):
    """wrapper for read_text"""

    def __init__(self):
        from pdr.loaders.text import read_text

        super().__init__(read_text)


class ReadLabel(Loader):
    """wrapper for read_label"""

    def __init__(self):
        from pdr.loaders.text import read_label

        super().__init__(read_label)


class ReadFits(Loader):
    """wrapper for handle_fits_file"""

    def __init__(self):
        from pdr.loaders.handlers import handle_fits_file

        super().__init__(handle_fits_file)

    def __call__(self, pdrlike: PDRLike, name: str, **kwargs):
        return super().__call__(pdrlike, name, **kwargs)[name]


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


class Trivial(Loader):
    """wrapper for trivial"""

    def __init__(self):
        from pdr.loaders.utility import trivial

        super().__init__(trivial)
