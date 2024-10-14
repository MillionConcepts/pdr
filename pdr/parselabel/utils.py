from __future__ import annotations

from pathlib import Path
import re
from typing import Union, IO, Mapping, Hashable, Any, Optional, Callable

from dustgoggles.structures import dig_for_value, _evaluate_diglevel
from multidict import MultiDict

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


def dig_for_parent(
    mapping: Mapping,
    key: Hashable,
    value: Any,
    mtypes: tuple[type[Mapping], ...] = (dict, MultiDict)
) -> Optional[Mapping]:
    """
    like dig_for_value, but returns the mapping that contains the matched item
    rather than the value of the matched item
    """
    return dig_for_value(
        mapping,
        None,
        base_pred=lambda _, v: isinstance(v, mtypes) and v.get(key) == value,
        match='value',
        mtypes=mtypes
    )


def _levelpick_inner(
    mapping: Mapping,
    predicate: Callable[[Hashable, Any], bool],
    backup: int,
    mtypes: tuple[type[Mapping], ...],
    level: int
) -> tuple[Optional[Mapping], Optional[int]]:
    level_items, nests = _evaluate_diglevel(mapping, predicate, mtypes)
    if level_items:
        return mapping, level
    if not nests:
        return None, None
    pick, iternests, picklevel = None, iter(nests), None
    for nest in iter(nests):
        pick, picklevel = _levelpick_inner(
            nest, predicate, backup, mtypes, level + 1
        )
        if pick is not None:
            break
    if pick is None:
        return None, None
    if picklevel - level > backup:
        return pick, picklevel
    if level == 0 and picklevel - level != backup:
        raise ValueError("Can't back up this far.")
    return mapping, picklevel


def levelpick(
    mapping: Mapping,
    predicate: Callable[[Hashable, Any], bool],
    backup: int = 0,
    mtypes: tuple[type[Mapping], ...] = (dict, MultiDict)
) -> Optional[Mapping]:
    """
    Give mapping up `backup` levels from possibly-nested item that matches
    predicate. `backup=0` is roughly equivalent to `dig_for_parent`.
    """
    return _levelpick_inner(mapping, predicate, backup, mtypes, 0)[0]
