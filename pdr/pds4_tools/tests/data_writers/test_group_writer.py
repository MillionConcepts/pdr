from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import sys
import numpy as np

from pds4_tools import pds4_read

# We create 2 tables to test group fields. See below or label for table definitions.
# The data with-in these two tables may be accessed as follows:
#
# Table 1, column 1
# group_data1.ravel()[::2].reshape(21, 10, 5)
#
# Table 1, column 2
# group_data1.ravel()[1::2].reshape(21, 10, 5)
#
# Table 2, column 1
# group_data2.ravel()[::11].reshape(21, 10)
#
# Table 2, column 2
# same as table 1, column 1
#
# Table 2, column 3
# same as table 1, column 2

af_path = os.path.join(os.path.dirname(__file__), '..', 'data/af.xml')
structures = pds4_read(af_path, quiet=True)
original_data = structures[9]['PIXEL_CORNER_LON']

# Create a table with two columns, each of shape (21,10,5)
group_data1 = np.asarray([original_data.ravel(), original_data.ravel()]).reshape(21,10,10)

# Create a table with three columns, where the first has shape (21,10) and the other two have shapes (21,10,5)
group_data2 = group_data1.copy().ravel()
group_data2 = np.insert(group_data2, list(range(0, 21*10*10, 10)), list(range(0, 210))).reshape(21,10,11)

# Ensure data is MSB
if sys.byteorder == 'little':
    group_data1.byteswap(True)
    group_data2.byteswap(True)

path = os.path.join(os.path.dirname(__file__), '..', 'data/test_group_fields.dat')
with open(path, 'wb') as file_handler:
    file_handler.write(group_data1.tobytes() + group_data2.tobytes())
