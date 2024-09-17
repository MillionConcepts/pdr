from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import struct

signed_byte =   [struct.pack('b', val) for val in [-100, 127, 50]]
unsigned_byte = [struct.pack('B', val) for val in [150, 253, 0]]

signed_msb2 = [struct.pack('>h', val) for val in [-32237, 25020, -100]]
signed_msb4 = [struct.pack('>i', val) for val in [2147480000, -1047483647, 143352]]
signed_msb8 = [struct.pack('>q', val) for val in [9003372036854775800, -59706567879, 8379869176]]

unsigned_msb2 = [struct.pack('>H', val) for val in [502, 34542, 60535]]
unsigned_msb4 = [struct.pack('>I', val) for val in [50349235, 3994967214, 243414]]
unsigned_msb8 = [struct.pack('>Q', val) for val in [987654073709550582, 25020, 17396744073709550582]]

float_msb =  [struct.pack('>f', val) for val in [-1.3862e-43, 1.25e-41, 3.403451e+25]]
double_msb = [struct.pack('>d', val) for val in [1.79e+308, -5.7303e100, -101.432310]]

complex_msb8 = [struct.pack('>f', val) for val in [3.202823*10**38, 1.41*10**5,
                                                   1.63230, -1.2360*10**10,
                                                   1.155494*10**-38, -500.23]]
complex_msb8 = [b''.join(complex_msb8[i:i+2]) for i in range(0, 6, 2)]

complex_msb16 = [struct.pack('>d', val) for val in [2.215073858*10**-308, 1.41*10**5,
                                                    5.072014, -1.2360*10**10,
                                                    -1.65*10**308, 1.797693*10**308]]
complex_msb16 = [b''.join(complex_msb16[i:i+2]) for i in range(0, 6, 2)]

signed_lsb2 = [struct.pack('<h', val) for val in [-32237, 25020, -100]]
signed_lsb4 = [struct.pack('<i', val) for val in [2147480000, -1047483647, 143352]]
signed_lsb8 = [struct.pack('<q', val) for val in [9003372036854775800, -59706567879, 8379869176]]

unsigned_lsb2 = [struct.pack('<H', val) for val in [502, 34542, 60535]]
unsigned_lsb4 = [struct.pack('<I', val) for val in [50349235, 3994967214, 243414]]
unsigned_lsb8 = [struct.pack('<Q', val) for val in [987654073709550582, 25020, 17396744073709550582]]

float_lsb =  [struct.pack('<f', val) for val in [-1.3862e-43, 1.25e-41, 3.403451e+25]]
double_lsb = [struct.pack('<d', val) for val in [1.79e+308, -5.7303e100, -101.432310]]

complex_lsb8 = [struct.pack('<f', val) for val in [3.202823*10**38, 1.41*10**5,
                                                   1.63230, -1.2360*10**10,
                                                   1.155494*10**-38, -500.23]]
complex_lsb8 = [b''.join(complex_lsb8[i:i+2]) for i in range(0, 6, 2)]

complex_lsb16 = [struct.pack('<d', val) for val in [2.215073858*10**-308, 1.41*10**5,
                                                    5.072014, -1.2360*10**10,
                                                    -1.65*10**308, 1.797693*10**308]]
complex_lsb16 = [b''.join(complex_lsb16[i:i+2]) for i in range(0, 6, 2)]

integer_scaling = [struct.pack('>h', val) for val in [10000, -10000, 0]]
float_scaling = [struct.pack('>f', val) for val in [3.2e38, -3.2e38, 0]]

data = [signed_byte, unsigned_byte,
        signed_msb2, signed_msb4, signed_msb8,
        unsigned_msb2, unsigned_msb4, unsigned_msb8,
        float_msb, double_msb,
        complex_msb8, complex_msb16,
        signed_lsb2, signed_lsb4, signed_lsb8,
        unsigned_lsb2, unsigned_lsb4, unsigned_lsb8,
        float_lsb, double_lsb,
        complex_lsb8, complex_lsb16,
        integer_scaling, integer_scaling, float_scaling]

path = os.path.join(os.path.dirname(__file__), '..', 'data/test_array_data_types.dat')
newFile = open(path, 'wb')
for array in data:
    newFile.write(b''.join(array))
