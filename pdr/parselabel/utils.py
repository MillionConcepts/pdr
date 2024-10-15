from pathlib import Path
import re
from typing import Union, IO


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


class InvalidAttachedLabel(ValueError):
    pass


def _scan_to_end_of_label(
    buf: IO, max_size: int, text: bytes, raise_no_ending: bool
):
    """Subroutine of trim_label()"""
    length = 0
    while length < max_size:
        if (chunk := buf.read(50 * 1024)) == b'':
            break
        for ending in KNOWN_LABEL_ENDINGS:
            if (endmatch := re.search(ending, text[:-15] + chunk)) is not None:
                return text + chunk[: endmatch.span()[1]]
        text, length = text + chunk, length + 50 * 1024
    if raise_no_ending is True:
        raise InvalidAttachedLabel("Couldn't find a label ending.")
    return text


def trim_label(
    fn: Union[IO, Path, str],
    max_size: int = DEFAULT_PVL_LIMIT,
    strict_decode: bool = True,
    raise_no_ending: bool = False
) -> str:
    """Look for a PVL label at the top of a file."""
    target_is_fn = isinstance(fn, (Path, str))
    try:
        if target_is_fn is True:
            fn = open(fn, 'rb')
        text = fn.read(20)
        if strict_decode is True:
            try:
                text.decode('ascii')
            except UnicodeDecodeError:
                raise InvalidAttachedLabel("File head appears to be binary.")
        text = _scan_to_end_of_label(fn, max_size, text, raise_no_ending)
    finally:
        if target_is_fn is True:
            fn.close()
    policy = "strict" if strict_decode is True else "replace"
    try:
        return text.decode("utf-8", errors=policy)
    except UnicodeDecodeError:
        raise InvalidAttachedLabel("Invalid characters in label.")
