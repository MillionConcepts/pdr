from pathlib import Path
import re
from typing import Union, IO

from pdr.utils import head_file


KNOWN_LABEL_ENDINGS = (
    re.compile(b"\nEND {0,2}(\r| {8})"),  # common PVL convention
    re.compile(b"\x00{3}"),  # just null bytes, for odder cases
)
"""
Fast regex patterns for generic PVL label endings. They work for almost all PVL 
labels in the PDS.
"""

DEFAULT_PVL_LIMIT = 1000 * 1024
"""heuristic for max label size. we know it's not a real rule."""


def trim_label(
    fn: Union[IO, Path, str],
    max_size: int = DEFAULT_PVL_LIMIT,
    raise_for_failure: bool = False,
) -> bytes:
    """Look for a PVL label at the top of a file."""
    head = head_file(fn, max_size).read()
    for ending in KNOWN_LABEL_ENDINGS:
        if (endmatch := re.search(ending, head)) is not None:
            return head[: endmatch.span()[1]]
    if raise_for_failure:
        raise ValueError("couldn't find a label ending")
    return head
