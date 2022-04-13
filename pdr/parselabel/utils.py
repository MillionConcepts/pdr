import re
from pathlib import Path
from typing import Union, IO

from pdr.utils import head_file


KNOWN_LABEL_ENDINGS = (
    b"END\r\n",  # PVL
    b"\x00{3}",  # just null bytes
)

# heuristic for max label size. we know it's not a real rule.
MAX_LABEL_SIZE = 500 * 1024


def trim_label(
    fn: Union[IO, Path, str],
    max_size: int = MAX_LABEL_SIZE,
    raise_for_failure: bool = False,
) -> Union[str, bytes]:
    head = head_file(fn, max_size).read()
    for ending in KNOWN_LABEL_ENDINGS:
        if (endmatch := re.search(ending, head)) is not None:
            return head[: endmatch.span()[1]]
    if raise_for_failure:
        raise ValueError("couldn't find a label ending")
    return head
