"""extra checking functions. mostly examples right now."""

from typing import Callable

import pdr
from pdr.tests.definitions import dimensions as dimensions


def dimension_checker(dataset: str) -> Callable[[pdr.Data], None]:
    """
    dispatch function: check against defined canonical dimensions for a given
    data set. this is entirely redundant with hashing and is here primarily
    as an example of how we could systematically implement this sort of thing
    -- although it could also be used as a warning light for why a hash
    comparison failed.
    """
    # TODO, if it comes up: replace all illegal characters with underscores,
    #  not just spaces
    return getattr(dimensions, dataset.lower().replace(" ", "_"))


# TODO: obviously this fails in like 10000 cases, mostly an example right now
def specified_image_size(data):
    if (data.labelget("LINES"), data.labelget("LINE_SAMPLES")) == data['IMAGE'].shape:
        return None
    return "image read from product doesn't match dimensions in label"
