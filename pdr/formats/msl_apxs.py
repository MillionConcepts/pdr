import warnings

from pdr.loaders.utility import trivial


def table_loader(pointer):
    # we don't support these right now, or maybe ever
    warnings.warn(
        f"The MSL APXS {pointer} tables are not currently " f"supported."
    )
    return trivial
