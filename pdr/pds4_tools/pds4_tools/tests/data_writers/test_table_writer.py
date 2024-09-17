# coding=utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import struct
import numpy as np

signed_byte =   np.asarray([struct.pack('b', val) for val in [-100, 127, 50]], dtype='object')
unsigned_byte = np.asarray([struct.pack('B', val) for val in [150, 253, 0]], dtype='object')

signed_msb2 = np.asarray([struct.pack('>h', val) for val in [-32237, 25020, -100]], dtype='object')
signed_msb4 = np.asarray([struct.pack('>i', val) for val in [2147480000, -1047483647, 143352]], dtype='object')
signed_msb8 = np.asarray([struct.pack('>q', val) for val in [9003372036854775800, -59706567879, 8379869176]], dtype='object')

unsigned_msb2 = np.asarray([struct.pack('>H', val) for val in [502, 34542, 60535]], dtype='object')
unsigned_msb4 = np.asarray([struct.pack('>I', val) for val in [50349235, 3994967214, 243414]], dtype='object')
unsigned_msb8 = np.asarray([struct.pack('>Q', val) for val in [987654073709550582, 25020, 17396744073709550582]], dtype='object')

float_msb =  np.asarray([struct.pack('>f', val) for val in [-1.3862e-43, 1.25e-41, 3.403451e+25]], dtype='object')
double_msb = np.asarray([struct.pack('>d', val) for val in [1.79e+308, -5.7303e100, -101.432310]], dtype='object')

complex_msb8 = [struct.pack('>f', val) for val in [3.202823*10**38, 1.41*10**5,
                                                   1.63230, -1.2360*10**10,
                                                   1.155494*10**-38, -500.23]]
complex_msb8 = np.asarray([b''.join(complex_msb8[i:i+2]) for i in range(0, 6, 2)], dtype='object')

complex_msb16 = [struct.pack('>d', val) for val in [2.215073858*10**-308, 1.41*10**5,
                                                    5.072014, -1.2360*10**10,
                                                    -1.65*10**308, 1.797693*10**308]]
complex_msb16 = np.asarray([b''.join(complex_msb16[i:i+2]) for i in range(0, 6, 2)], dtype='object')

signed_lsb2 = np.asarray([struct.pack('<h', val) for val in [-32237, 25020, -100]], dtype='object')
signed_lsb4 = np.asarray([struct.pack('<i', val) for val in [2147480000, -1047483647, 143352]], dtype='object')
signed_lsb8 = np.asarray([struct.pack('<q', val) for val in [9003372036854775800, -59706567879, 8379869176]], dtype='object')

unsigned_lsb2 = np.asarray([struct.pack('<H', val) for val in [502, 34542, 60535]], dtype='object')
unsigned_lsb4 = np.asarray([struct.pack('<I', val) for val in [50349235, 3994967214, 243414]], dtype='object')
unsigned_lsb8 = np.asarray([struct.pack('<Q', val) for val in [987654073709550582, 25020, 17396744073709550582]], dtype='object')

float_lsb =  np.asarray([struct.pack('<f', val) for val in [-1.3862e-43, 1.25e-41, 3.403451e+25]], dtype='object')
double_lsb = np.asarray([struct.pack('<d', val) for val in [1.79e+308, -5.7303e100, -101.432310]], dtype='object')

complex_lsb8 = [struct.pack('<f', val) for val in [3.202823*10**38, 1.41*10**5,
                                                   1.63230, -1.2360*10**10,
                                                   1.155494*10**-38, -500.23]]
complex_lsb8 = np.asarray([b''.join(complex_lsb8[i:i+2]) for i in range(0, 6, 2)], dtype='object')

complex_lsb16 = [struct.pack('<d', val) for val in [2.215073858*10**-308, 1.41*10**5,
                                                    5.072014, -1.2360*10**10,
                                                    -1.65*10**308, 1.797693*10**308]]
complex_lsb16 = np.asarray([b''.join(complex_lsb16[i:i+2]) for i in range(0, 6, 2)], dtype='object')

unsigned_bitstring = np.asarray([b'\x1cZ\xd8', b'\xfb\xfb\x18', b'ZY\xe8'], dtype='object')
signed_bitstring = np.asarray([b'\x013', b'\xfe\x82', b'!\xfc'], dtype='object')

ascii_real =    np.asarray(['   1.79e+308 ', '  -5.7303e100', '-101.432310  '], dtype='object')
ascii_integer = np.asarray([' -9003372036854775800', '   396744073709550582', '       25020         '], dtype='object')
ascii_nonnegative_integer = np.asarray(['17396744073709550582', '               25020', '                   0'], dtype='object')
ascii_boolean = np.asarray([' false', '     0', '    1 '], dtype='object')
ascii_base2 =   np.asarray(['       101', '     10100', '1111100000'], dtype='object')
ascii_base8 =   np.asarray(['         101', '    63272100', '007301234767'], dtype='object')
ascii_base16 =  np.asarray(['      0FB8', '  ABC01FBE', 'dea111bacf'], dtype='object')
ascii_string =  np.asarray([' Test string 1  ', ' Test  2        ', ' Test longest 3 '], dtype='object')
utf8_string =   np.asarray([' Tést stríng 1  ', ' Tést  2         ', ' Tést longést 3 '], dtype='object')

dates_ymd_utc   = ['2018-10-10T05:05Z       ', '2018-01-10T05:05:05.123Z', '2014Z                   ']
dates_doy_local = ['2018-200', '2018-201', '2018-202']

ascii_base16_overflow = np.asarray([' F16DA69029D6FBF6', '1FFFFFFFFFFFFFFFF', '40000000000000001'], dtype='object')
ascii_base8_scaling_overflow = np.asarray(['7777777777777777777777', '7237737712377727777777', '7777737712377727777777'], dtype='object')
ascii_base2_scaling_overflow = np.asarray(['1111111111111111', '1111011101110011', '      0001110101'], dtype='object')
integer_scaling = np.asarray(['    10000', '   -10000', '        0'], dtype='object')
float_scaling = np.asarray([struct.pack('>f', val) for val in [3.2e38, -3.2e38, 0]], dtype='object')

binary_table = np.vstack((signed_byte, unsigned_byte,
                   signed_msb2, signed_msb4, signed_msb8,
                   unsigned_msb2, unsigned_msb4, unsigned_msb8,
                   float_msb, double_msb,
                   complex_msb8, complex_msb16,
                   signed_lsb2, signed_lsb4, signed_lsb8,
                   unsigned_lsb2, unsigned_lsb4, unsigned_lsb8,
                   float_lsb, double_lsb,
                   complex_lsb8, complex_lsb16,
                   unsigned_bitstring, signed_bitstring)).transpose()

ascii_table = np.vstack((ascii_real, ascii_integer, ascii_nonnegative_integer, ascii_boolean,
                         ascii_base2, ascii_base8, ascii_base16,
                         ascii_string, utf8_string,
                         dates_ymd_utc, dates_doy_local,
                         ascii_base16_overflow, ascii_base8_scaling_overflow, ascii_base2_scaling_overflow,
                         integer_scaling, integer_scaling)).transpose()

path = os.path.join(os.path.dirname(__file__), '..', 'data/test_table_data_types.dat')
newFile = open(path, 'wb')
for i in range(0, 3):
    newFile.write(b''.join(binary_table[i]) + ''.join(ascii_table[i]).encode('utf-8') + float_scaling[i])
