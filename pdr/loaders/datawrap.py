from inspect import getfullargspec
from itertools import chain
from typing import Union, Sequence

from cytoolz import keyfilter

from pdr.formats import check_special_sample_type
from pdr.func import get_argnames, softquery, specialize
from pdr.loaders.queries import DEFAULT_DATA_QUERIES, bytes_per_pixel, \
    base_sample_info, im_sample_type
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

    def __call__(self, pdrlike: PDRLike, name: str, **kwargs):
        kwargdict = {'data': pdrlike, 'name': depointerize(name)} | kwargs
        info = softquery(self.loader_function, self.queries, kwargdict)
        return self.loader_function(**info)

    queries = DEFAULT_DATA_QUERIES


class ReadImage(Loader):
    """wrapper for read_image"""

    def __init__(self):
        from pdr.loaders.image import read_image

        super().__init__(read_image)

    queries = DEFAULT_DATA_QUERIES | {
        'is_qube': is_qube,
        'base_samp_info': base_sample_info,
        # TODO: need to be able to pass the for_numpy kwarg through without triggering softquery
        'sample_type': specialize(im_sample_type, check_special_sample_type),
        'gen_props':
    }


class ReadTable(Loader):
    """wrapper for read_table"""

    def __init__(self):
        from pdr.loaders.table import read_table

        super().__init__(read_table)


class ReadHeader(Loader):
    """wrapper for read_header"""

    def __init__(self):
        from pdr.loaders.misc import read_header

        super().__init__(read_header)


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
        from pdr.loaders.dispatch import handle_fits_file

        super().__init__(handle_fits_file)


class ReadCompressedImage(Loader):
    """wrapper for handle_compressed_image"""

    def __init__(self):
        from pdr.loaders.dispatch import handle_compressed_image

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