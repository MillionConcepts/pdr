from pdr.loaders.datawrap import TBD


def table_loader(pointer):
    # we don't support these right now, or maybe ever
    if pointer == "ERROR_CONTROL_TABLE":
        return TBD
