import warnings

from pdr.loaders.utility import trivial


def galileo_table_loader():
    warnings.warn("Galileo EDR binary tables are not yet supported.")
    return trivial
