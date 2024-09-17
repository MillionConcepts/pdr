from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import xml.etree.ElementTree as ET

PY26 = sys.version_info[0:2] == (2, 6)

ET_Element = ET._Element if PY26 else ET.Element
