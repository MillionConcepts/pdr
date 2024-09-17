from pds4_tools.__about__ import (__version__, __author__, __email__, __copyright__)

from .reader import pds4_read
from .reader import pds4_read as read

from .utils.logging import set_loglevel

try:
    from .viewer import pds4_viewer
    from .viewer import pds4_viewer as view
except ImportError as e:

    def _missing_optional_deps(exception, *args, **kwargs):
        raise exception

    import functools as _functools
    pds4_viewer = view = _functools.partial(_missing_optional_deps, e)
