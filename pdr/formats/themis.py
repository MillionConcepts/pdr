import warnings


def get_visgeo_qube_offset(data):
    return True, data.metaget_('^QUBE')[1] - 1


def trivial_visgeo_btr_loader(data, pointer):
    warnings.warn(
        f"THEMIS VIS/IR ABR/BTR {pointer} objects are not currently supported."
    )
    return data.trivial
