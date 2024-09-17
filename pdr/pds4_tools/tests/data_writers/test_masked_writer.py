from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import struct
import numpy as np

# Table masked data writer
signed_msb4 = np.asarray([struct.pack('>i', val) for val in [2147480000, -1047483647, -99999, -99999]], dtype='object')
double_msb = np.asarray([struct.pack('>d', val) for val in [1.79e+308, -5.7303e100, -5.7303e100, -101.432310]], dtype='object')

ascii_real =    np.asarray(['   1.79e+308 ', '        -9.99', '-101.432310  ', '        -9.99'], dtype='object')
ascii_integer = np.asarray([' -9003372036854775800', '            100000000', '   396744073709550582', '       25020         '], dtype='object')
ascii_base_overflow = np.asarray([' F16DA69029D6FBF6', '1FFFFFFFFFFFFFFFF', '40000000000000001', ' F16DA69029D6FBF6'], dtype='object')

binary_table = np.vstack((signed_msb4, double_msb)).transpose()
ascii_table = np.vstack((ascii_real, ascii_integer, ascii_base_overflow)).transpose()

path = os.path.join(os.path.dirname(__file__), '..', 'data/test_masked_data.dat')
newFile = open(path, 'wb')
for i in range(0, 4):
    newFile.write(b''.join(binary_table[i]) + ''.join(ascii_table[i]).encode('utf-8'))


# Array masked data writer
unsigned_msb4 = [struct.pack('>I', val) for val in [50349235, 3994967214, 3994967214, 243414]]
double_lsb = [struct.pack('<d', val) for val in [1.79e+200, -5.7303e+100, -101.432310, 1.79e+200]]

data = [unsigned_msb4, double_lsb]

for array in data:
    newFile.write(b''.join(array))
