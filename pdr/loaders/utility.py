import warnings

from multidict import MultiDict


def trivial(*_, **__):
    """
    This is a trivial loader. It does not load. The purpose is to use
    for any pointers we don't want to load and instead simply want ignored.
    """
    pass


def tbd(name: str, block: MultiDict, *_, **__):
    """
    This is a placeholder function for pointers that are
    not explicitly supported elsewhere. It throws a warning and
    passes just the value of the pointer.
    """
    warnings.warn(f"The {name} pointer is not yet fully supported.")
    return block

