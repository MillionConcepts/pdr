class AlreadyLoadedError(Exception):
    """
    We already loaded this object and haven't been instructed to reload it.
    """
    pass


class DuplicateKeyWarning(UserWarning):
    """This product has duplicate object names; we're renaming them."""
    pass
