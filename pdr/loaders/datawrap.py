"""Classes to wrap and manage complex data-loading workflows."""
from typing import Any

from dustgoggles.dynamic import exc_report
from dustgoggles.func import constant

from pdr.formats import (
    check_special_sample_type,
    check_special_qube_band_storage,
    check_special_position,
    check_special_structure,
    check_special_table_reader,
    check_special_fits_start_byte
)
from pdr.func import get_argnames, softquery, specialize, call_kwargfiltered
from pdr.parselabel.pds3 import depointerize
from pdr.pdrtypes import LoaderFunction, PDRLike
from pdr.loaders.queries import (
    DEFAULT_DATA_QUERIES,
    get_identifiers,
    get_file_mapping,
    get_fits_start_byte,
    get_hdulist,
    get_target
)


def _format_exc_report(exc: Exception) -> dict:
    """format an exception report for inclusion in another dict"""
    report = exc_report(exc)
    for k, v in tuple(report.items()):
        if k != 'exception':
            del report[k]
            report[f"exception_{k}"] = v
    return report


class Loader:
    """
    compact wrapper for loader functions, intended principally but not solely
    for library-internal use. provides a common interface, adds compactness,
    delays imports, etc.
    """

    def __init__(self, loader_function: LoaderFunction):
        self.loader_function = loader_function
        self.argnames = get_argnames(loader_function)

    def __call__(
        self, pdrlike: PDRLike, name: str, **kwargs
    ) -> dict[str, Any]:
        kwargdict = {"data": pdrlike, "name": depointerize(name)} | kwargs
        kwargdict["tracker"].set_metadata(loader=self.__class__.__name__)
        record_exc = {"status": "query_ok"}
        try:
            info = softquery(self.loader_function, self.queries, kwargdict)
        except Exception as exc:
            record_exc = {"status": "query_failed"} | _format_exc_report(exc)
            raise exc
        finally:
            kwargdict["tracker"].track(self.loader_function, **record_exc)
            kwargdict["tracker"].dump()
        load_exc = {"status": "load_ok"}
        try:
            return {name: call_kwargfiltered(self.loader_function, **info)}
        except Exception as exc:
            load_exc = {"status": "load_failed"} | _format_exc_report(exc)
            raise exc
        finally:
            kwargdict["tracker"].track(self.loader_function, **load_exc)
            kwargdict["tracker"].dump()
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
            # just modifies gen_props in place, triggers transform in load step
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

        # noinspection PyTypeChecker
        super().__init__(handle_fits_file)

    def __call__(self, pdrlike: PDRLike, name: str, **kwargs):
        # slightly hacky but works with how we've done dictionary construction
        return tuple(super().__call__(pdrlike, name, **kwargs).values())[0]

    queries = DEFAULT_DATA_QUERIES | {
        "fn": get_file_mapping,
        'target': get_target,
        "identifiers": get_identifiers,
        'hdulist': get_hdulist,
        "hdu_id": specialize(
            get_fits_start_byte, check_special_fits_start_byte
        ),
        'hdu_id_is_index': constant(False)
    }


class ReadCompressedImage(Loader):
    """wrapper for handle_compressed_image"""

    def __init__(self):
        from pdr.loaders.handlers import handle_compressed_image

        super().__init__(handle_compressed_image)


class ReadArray(Loader):
    """wrapper for read_array"""

    def __init__(self):
        from pdr.loaders.table import read_array
        from pdr.loaders.queries import parse_array_structure

        super().__init__(read_array)
        self.queries = DEFAULT_DATA_QUERIES | {
            "fmtdef_dt": specialize(
                parse_array_structure, check_special_structure
            ),
        }


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
