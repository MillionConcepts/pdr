from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

from .deprecation import PDS4ToolsDeprecationWarning


class PDS4StandardsException(Exception):
    """ Custom exception thrown when PDS4 Standards are violated. """
    pass
