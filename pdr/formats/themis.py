import warnings

from dustgoggles.structures import listify

from pdr.parselabel.pds3 import pointerize


def get_visgeo_qube_offset(data):
    return True, data.metaget_('^QUBE')[1] - 1


def trivial_themis_geo_loader(data, pointer):
    warnings.warn(f"THEMIS {pointer} objects are not currently supported.")
    return data.trivial


def check_gzip_fn(data, object_name):
    """
    some THEMIS QUBES are stored in gzipped formats. The labels do not always
    bother to mention this.
    """
    target = data.metaget(pointerize(object_name))
    if isinstance(target, dict):
        return target
    filename = listify(target)[0]
    if filename.endswith("gz"):
        return filename
    return True, [filename, f"{filename}.gz"]
