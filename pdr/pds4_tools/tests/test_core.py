# coding=utf-8
from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import pytest
import warnings
import numpy as np

from . import PDS4ToolsTestCase

from pdr.pds4_tools import pds4_read
from pdr.pds4_tools.reader.data import PDS_ndarray, PDS_marray
from pdr.pds4_tools.reader.data_types import data_type_convert_dates
from pdr.pds4_tools.reader.array_objects import ArrayStructure
from pdr.pds4_tools.reader.table_objects import TableStructure, TableManifest
from pdr.pds4_tools.reader.label_objects import Label

from pdr.pds4_tools.utils import compat
from pdr.pds4_tools.utils.compat import OrderedDict
from pdr.pds4_tools.utils.deprecation import (PDS4ToolsDeprecationWarning, deprecated,
                                          rename_parameter, delete_parameter)

from pdr.pds4_tools.extern import six
from pdr.pds4_tools.extern.six.moves import collections_abc


class TestStructureList(PDS4ToolsTestCase):

    def setup_class(self):

        self.structures = pds4_read(self.data('äf.xml'), lazy_load=True, quiet=True)

    def test_get(self):

        # Test LID and int retrieval
        assert isinstance(self.structures[1], ArrayStructure)
        assert self.structures[1] is self.structures['data_Primary']

        assert isinstance(self.structures[7], TableStructure)
        assert self.structures[7] is self.structures['data_Binning']

        # Test name and int retrieval
        assert isinstance(self.structures[13], TableStructure)
        assert self.structures[13] is self.structures['data_Observation']

        # Test retrieval when both LID and name are set
        assert self.structures[5] is self.structures['data_Engineering']
        assert self.structures[5] is self.structures['data_Engineering_name']

        # Test retrieval of structures with UTF-8 characters in name
        assert isinstance(self.structures[3], TableStructure)
        assert self.structures[3] is self.structures['data¥_Integration']

        # Test slice retrieval
        assert len(self.structures[1:3]) == 2
        two_structures = [self.structures[1], self.structures[2]]

        for i, structure in enumerate(self.structures[1:3]):
            assert structure is two_structures[i]

        # Test retrieval of structures with duplicate names/LIDs
        assert self.structures['data_PixelGeometry', 0] is self.structures[9]
        assert self.structures['data_PixelGeometry', 1] is self.structures[11]

        # Test retrieval of a structure without a name/LID in the label
        assert self.structures['HEADER_2'] is self.structures[4]

        # Test proper return types on retrieval attempt of non-existent structure
        with pytest.raises(IndexError):
            self.structures[15]

        with pytest.raises(KeyError):
            self.structures['non_existent']

        with pytest.raises(KeyError):
            self.structures['data_PixelGeometry', 2]

    def test_len(self):

        assert len(self.structures) == 14


class TestArrayStructure(PDS4ToolsTestCase):

    def setup_class(self):

        structures = pds4_read(self.data('äf.xml'), lazy_load=True, quiet=True)
        self.structure = structures[1]

    def test_is_array(self):

        assert self.structure.is_array()
        assert not self.structure.is_table()

    def test_id(self):

        assert self.structure.id == 'data_Primary'

    def test_type(self):

        assert self.structure.type == 'Array_3D_Spectrum'

    def test_data_loaded(self):

        if self.structure.data_loaded:
            del self.structure.data

        assert not self.structure.data_loaded
        self.structure.data
        assert self.structure.data_loaded

    def test_data(self):

        data = self.structure.data

        assert isinstance(data, PDS_ndarray)
        assert data.shape == (21, 10, 36)

        _check_array_equal(data[0, 0, 0:5], [5160, 5550, 6432, 4752, 3470], 'int32')
        _check_array_equal(data[10, 5, 6:11], [9284,  6546,  7293,  8380, 10138], 'int32')
        _check_array_equal(data[-1, -1, -5:], [21028, 25200, 22548, 18596, 20444], 'int32')


class TestTableStructure(PDS4ToolsTestCase):

    def setup_class(self):

        structures = pds4_read(self.data('äf.xml'), lazy_load=True, quiet=True)
        self.structure = structures[11]

    def test_is_table(self):

        assert self.structure.is_table()
        assert not self.structure.is_array()

    def test_id(self):

        assert self.structure.id == 'data_PixelGeometry'

    def test_type(self):

        assert self.structure.type == 'Table_Binary'

    def test_len(self):

        # Test number of fields obtained from meta data
        assert len(self.structure) == 36

        # Test number of fields obtained from data
        self.structure.data
        assert len(self.structure) == 36

    def test_get(self):

        structure = self.structure

        # Test retrieval by field name
        assert np.array_equal(structure['SUB_SPACECRAFT_LAT'], structure.field('SUB_SPACECRAFT_LAT'))
        assert np.array_equal(structure['INST_SUN_ANGLE'], structure.field('INST_SUN_ANGLE'))

        # Test retrieval of UTF-8 field names
        assert np.array_equal(structure['VZÄ_INSTRUMENT_MSO'], structure.field('VZÄ_INSTRUMENT_MSO'))

        # Test retrieval by full field name
        assert np.array_equal(structure['V_SUN'], structure.field('V_SUN'))
        assert np.array_equal(structure['GROUP_2, V_SUN'], structure.field('GROUP_2, V_SUN'))
        assert np.array_equal(structure['V_SUN'], structure.field('GROUP_2, V_SUN'))

        # Test retrieval of fields with repetitions
        assert np.array_equal(structure['SUB_SOLAR_LAT'], structure.field('SUB_SOLAR_LAT'))
        assert np.array_equal(structure['SUB_SOLAR_LAT'], structure.field('SUB_SOLAR_LAT [0]'))

        # Test retrieval of multiple fields by name
        assert np.array_equal(structure[['SUB_SPACECRAFT_LAT', 'V_SUN']].field(0), structure.field('SUB_SPACECRAFT_LAT'))
        assert np.array_equal(structure[['SUB_SPACECRAFT_LAT', 'V_SUN']].field(1), structure.field('V_SUN'))

        # Test retrieval of records by index and slice
        assert np.array_equal(structure[10], structure.data[10])
        assert np.array_equal(structure[50:150], structure.data[50:150])

        # Test retrieval of records by specifying particular indexes
        assert np.array_equal(structure[[0, 1, 10]], structure.data[[0, 1, 10]])
        assert np.array_equal(structure[np.asarray([0, 1, 10])], structure.data[[0, 1, 10]])

        # Test proper error types on retrieval attempt of non-existent field or record
        with pytest.raises(IndexError):
            structure[36]

        with pytest.raises(ValueError):
            structure['V_SUN0']

        with pytest.raises(ValueError):
            structure[['SUB_SPACECRAFT_LAT', 'V_SUN0']]

    def test_field(self):

        structure = self.structure

        # Test retrieval by field name
        assert isinstance(structure.field('SUB_SPACECRAFT_LAT'), PDS_ndarray)
        assert isinstance(structure.field('INST_SUN_ANGLE'), PDS_ndarray)

        # Test retrieval of UTF-8 field names
        assert isinstance(structure.field('VZÄ_INSTRUMENT_MSO'), PDS_ndarray)

        # Test retrieval by full field name
        assert isinstance(structure.field('VZ_INSTRUMENT_INERTIAL'), PDS_ndarray)
        assert isinstance(structure.field('GROUP_27, VZ_INSTRUMENT_INERTIAL'), PDS_ndarray)
        assert np.array_equal(structure.field('VZ_INSTRUMENT_INERTIAL'), structure.field('GROUP_27, VZ_INSTRUMENT_INERTIAL'))

        # Test retrieval by index
        assert np.array_equal(structure.field('SUB_SPACECRAFT_LAT'), structure.field(0))
        assert np.array_equal(structure.field('INST_SUN_ANGLE'), structure.field(35))
        assert np.array_equal(structure.field('V_SUN'), structure.field(7))

        # Test retrieval by of repetitions
        assert np.array_equal(structure.field('SUB_SOLAR_LAT'), structure.field(2))
        assert np.array_equal(structure.field('SUB_SOLAR_LAT', repetition=1), structure.field(3))

        # Test retrieval of all
        two_fields = [structure.field(2), structure.field(3)]

        for i, field in enumerate(structure.field('SUB_SOLAR_LAT', all=True)):
            assert np.array_equal(field, two_fields[i])

        # Test proper return types on retrieval attempt of non-existent fields
        with pytest.raises(IndexError):
            structure.field(36)

        with pytest.raises(ValueError):
            structure.field('SUB_SOLAR_LAT', repetition=2)

        with pytest.raises(ValueError):
            structure.field('V_SUN0')

        with pytest.raises(ValueError):
            structure[['SUB_SPACECRAFT_LAT', 'V_SUN0']]

        assert structure.field('non_existent', all=True) == []

    def test_uniformly_sampled(self):

        structures = pds4_read(self.data('test_uniformly_sampled.xml'), lazy_load=True, quiet=True)

        # Test Linear uniformly sampled field
        _check_array_equal(structures['UniSampled Linear'].field(0), [1, 3, 5, 7], 'float64')

        # Test Exponential uniformly sampled field
        _check_array_equal(structures['UniSampled Exponential'].field(0), [np.log10(1), np.log10(2), np.log10(3), np.log10(4)], 'float64')

        # Test Logarithmic uniformly sampled field
        _check_array_equal(structures['UniSampled Logarithmic'].field(0), [1, 10, 100, 1000], 'float64')

    def test_data_loaded(self):

        if self.structure.data_loaded:
            del self.structure.data

        assert not self.structure.data_loaded
        self.structure.data
        assert self.structure.data_loaded


class TestHeaderStructure(PDS4ToolsTestCase):

    def setup_class(self):

        structures = pds4_read(self.data('äf.xml'), lazy_load=True, quiet=True)
        self.structure = structures[0]

    def test_is_header(self):

        assert self.structure.is_header()
        assert not self.structure.is_array()

    def test_id(self):

        assert self.structure.id == 'header_Primary'

    def test_type(self):

        assert self.structure.type == 'Header'

    def test_data(self):

        data = self.structure.data

        assert isinstance(data, six.binary_type)

        assert data[0:9] == b'SIMPLE  ='
        assert data[800:838] == b'COMMENT University of Colorado Boulder'
        assert data[2640:2650] == b'END       '

        assert len(data) == 2880

    def test_parsers(self):

        parser = self.structure.parser()
        data_string = parser.to_string()

        assert isinstance(data_string, six.text_type)

        assert data_string.startswith('SIMPLE  =')
        assert data_string.endswith('END')

    def test_data_loaded(self):

        if self.structure.data_loaded:
            del self.structure.data

        assert not self.structure.data_loaded
        self.structure.data
        assert self.structure.data_loaded


class TestCharacterTable(PDS4ToolsTestCase):

    def setup_class(self):

        structures = pds4_read(self.data('colors.xml'), lazy_load=True, quiet=True)
        self.structure = structures[0]

    def test_data(self):

        structure = self.structure

        # Test ASCII_Integer
        _check_array_equal(structure.field(0)[-5:], [238,   1,  96,  96,   1], 'uint8')

        # Test ASCII_Real
        _check_array_equal(structure.field(8)[0:5], [0.02,  0.05,  0.06,  0.09,  0.06], 'float64')

        # Test ASCII_String
        strings = ['Lamy et al. (2009)          ', 'Snodgrass et al. (2008)     ']
        _check_array_equal(structure.field(-1)[30:32], strings, 'U28')

        # Test miscellaneous
        assert isinstance(structure.data, PDS_ndarray)
        assert len(structure.data.dtype) == 13
        assert len(structure.data) == 76


class TestDelimitedTable(PDS4ToolsTestCase):

    def setup_class(self):

        self.structures = pds4_read(self.data('Product_DelimitedTable.xml'), lazy_load=True, quiet=True)

    def test_data(self):

        structure = self.structures[0]

        # Test ASCII_Strings
        strings1 = ['a', 'b', 'c', 'd', 'e']
        strings2 = ['MODE 6', 'MODE 11', 'MODE 12']

        _check_array_equal(structure.field(0)[0:5], strings1, 'U4')
        _check_array_equal(structure.field(3)[9:12], strings2, 'U8')

        # Test ASCII_Real
        _check_array_equal(structure.field(2)[-5:], [1., 2., 3., 4., -5.], 'float64')

        # Ensure that a newline or linefeed in a character field, whether bounded by double quotes
        # or otherwise, works
        assert structure.field(3)[16] == 'MODE \r15'
        assert structure.field(3)[17] == 'MODE \n13'

        # Ensure empty character and numeric fields get proper value depending on their data type
        assert structure.field(0)[12] == ''
        assert structure.field(0)[13] == ''
        assert structure.field(2)[13] is np.ma.masked
        assert structure.field(2)[14] is np.ma.masked
        assert structure.field(5)[7, 2] is np.ma.masked
        assert structure.field(2).fill_value == 0
        assert np.count_nonzero(structure.field(5).fill_value) == 0

        # Ensure blankspace is preserved, both before and after, for strings
        assert structure.field(0)[14] == ' l '
        assert structure.field(0)[15] == ' m '
        assert structure.field(0)[16] == '   '

        # Ensure that quotes, both surrounding double quotes and otherwise, work correctly in unusual cases
        assert structure.field(1)[12] == '2004-03-04T00:00:20.01"'
        assert structure.field(1)[13] == '2"004-03-04T00:00:25.01'
        assert structure.field(1)[14] == '2004-03-04"T00":00:30.0'
        assert structure.field(1)[15] == '2004-03-04T00:00:35.017'
        assert structure.field(3)[13] == 'MODE 13"'
        assert structure.field(3)[14] == 'M"D" 13'

        # Test miscellaneous
        assert len(structure.data.dtype) == 6
        assert len(structure.data) == 20

        # Test line-feed as record delimiter
        structure = self.structures[2]

        assert structure.field(0)[1] == 2
        assert structure.field(3)[2] == 'SPICE kernels'

        # Ensure empty boolean fields get proper value
        assert structure.field(2)[1] is np.ma.masked
        _check_array_equal(structure.field(2).filled(), [True, False, False], 'bool')


class TestBinaryTable(PDS4ToolsTestCase):

    def setup_class(self):

        structures = pds4_read(self.data('äf.xml'), lazy_load=True, quiet=True)
        self.structure = structures[3]

    def test_data(self):

        structure = self.structure

        # Test IEEE754MSBDouble
        _check_array_equal(structure.field(0)[0:3], [4.86390955e+08, 4.86390970e+08, 4.86390985e+08], 'float64')

        # Test SignedMSB2
        _check_array_equal(structure.field(-1)[-5:],  [2603, 2602, 2603, 2603, 2604], 'int16')

        # Test ASCII_String
        string = ['2015/152 Jun 01 00:37:38.03714UTC', '2015/152 Jun 01 00:37:53.03715UTC']
        _check_array_equal(structure.field(2)[5:7], string, 'U33')

        # Test miscellaneous
        assert len(structure.data.dtype) == 9
        assert len(structure.data) == 21


class TestGroupFields(PDS4ToolsTestCase):

    def test_simple_groups(self):

        # Test via binary tables
        structures = pds4_read(self.data('äf.xml'),  lazy_load=True, quiet=True)

        # Test single nested, 1D group fields
        structure = structures[11]
        _check_array_equal(structure.field(10)[0], [-0.08405675,  0.60469515, -0.79200899], 'float64')

        structure = structures[13]
        string = ['mvn_app_rel_150601_150607_v01.bc', 'mvn_sc_rel_150601_150607_v01.bc ']
        _check_array_equal(structure.field(-1)[0, 3:5], string, 'U32')

        # Test via delimited table
        structures = pds4_read(self.data('Product_DelimitedTable.xml'), lazy_load=True, quiet=True)

        # Test single nested, 1D group fields
        structure = structures[0]
        _check_array_equal(structure.field(-1)[-1], [5,  1,  1,  1,  1,  1,  0,  0,  0,  0], 'int8')

    def test_complicated_groups(self):

        # Test via fixed width tables

        # Test a deeply nested field (nested with-in 3 group fields)
        structures = pds4_read(self.data('äf.xml'), lazy_load=True, quiet=True)
        structure = structures[9]
        _check_array_equal(structure.field(0)[11, 2, 5, 2:5], [-0.52061242, -0.51312923, -0.50972084], 'float64')

        # Test two fields with-in one group field
        structures = pds4_read(self.data('test_group_fields.xml'), lazy_load=True, quiet=True)

        structure = structures[0]
        _check_array_equal(structure.field(0)[9, 5, 2:5], [331.28526671,  328.97851487,  327.87342654], 'float64')
        _check_array_equal(structure.field(1)[3, 7, 1:4], [277.80563195,  281.21064631,  279.24594501], 'float64')

        # Test three fields with-in one group field
        structure = structures[1]

        _check_array_equal(structure.field(0)[20, 7:10], [207.,  208.,  209.], 'float64')
        _check_array_equal(structure.field(1)[9, 5, 2:5], [331.28526671,  328.97851487,  327.87342654], 'float64')
        _check_array_equal(structure.field(2)[3, 7, 1:4], [277.80563195,  281.21064631,  279.24594501], 'float64')

        # Test via delimited tables
        structures = pds4_read(self.data('Product_DelimitedTable.xml'), lazy_load=True, quiet=True)
        structure = structures[1]

        # Test multiple fields with-in one group field
        field1 = structure.field(1)
        assert np.all(field1 == 1)
        assert field1.shape == (3, 3)

        # Test multiple fields with-in one group field
        field4 = structure.field(4)
        assert np.all(field4 == 4)
        assert field4.shape == (3, 3, 2, 3, 2)

        # Test a less-nested field with-in a group appearing after a more nested case
        field7 = structure.field(7)
        assert np.all(field7 == 7)
        assert field7.shape == (3, 3, 2)


class TestLabel(PDS4ToolsTestCase):

    def setup_class(self):

        self.label = Label.from_file(self.data('test_label.xml'))

    def test_getters(self):

        # Test on unmodified root
        # (where whitespace is always significant and tags include URI since everything is unmodified)
        self.label.default_root = 'unmodified'

        one_liner1 = self.label[0][3]
        assert isinstance(one_liner1, Label)
        assert isinstance(one_liner1.getroot(), compat.ET_Element)

        assert one_liner1.tag == '{http://pds.nasa.gov/pds4/pds/v1}test_getters'
        assert one_liner1.text == '  is_space_significant  '
        assert one_liner1.attrib == {'attrib1': '  is_space_significant  ', 'attrib2': '1'}
        assert one_liner1.get('attrib1') == '  is_space_significant  '
        assert one_liner1.get('attrib2') == '1'

        multi_liner1 = self.label[0][4]
        assert isinstance(multi_liner1, Label)

        assert multi_liner1.text == '  is_space_significant\n               multiline          '
        assert multi_liner1.get('attrib1') == '  is_space_significant\n               multiline          '

        # Test on convenient root
        # (where whitespace is stripped on one-liners and core PDS URI is stripped)
        self.label.default_root = 'convenient'

        one_liner2 = self.label[0][3]
        assert isinstance(one_liner2, Label)
        assert isinstance(one_liner1.getroot(), compat.ET_Element)

        assert one_liner2.tag == 'test_getters'
        assert one_liner2.text == 'is_space_significant'
        assert one_liner2.attrib == {'attrib1': 'is_space_significant', 'attrib2': '1'}
        assert one_liner2.get('attrib1') == 'is_space_significant'
        assert one_liner2.get('attrib2') == '1'

        multi_liner2 = self.label[0][4]
        assert isinstance(multi_liner2, Label)

        assert multi_liner2.text == '  is_space_significant\n               multiline          '
        assert multi_liner2.get('attrib1') == '  is_space_significant\n               multiline          '

    def test_len(self):

        assert len(self.label) == 3
        assert len(self.label.find('.//File')) == 4

    def test_getroot(self):

        # Unmodified root
        self.label.default_root = 'unmodified'
        object_length1 = self.label.find('.//pds:object_length')

        assert isinstance(object_length1, Label)
        assert xml_equal(object_length1, object_length1.getroot())
        assert xml_equal(object_length1.getroot(unmodified=True), object_length1.getroot())

        # Convenient root
        self.label.default_root = 'convenient'
        object_length2 = self.label.find('.//object_length')

        assert isinstance(object_length2, Label)
        assert xml_equal(object_length2, object_length2.getroot())
        assert xml_equal(object_length2.getroot(unmodified=False), object_length2.getroot())

    def test_find(self):

        # Direct path and descendant search matching
        start_date_time1 = self.label.find('Observation_Area/Time_Coordinates/start_date_time')
        start_date_time2 = self.label.find('.//start_date_time')

        assert xml_equal(start_date_time1, start_date_time2)
        assert start_date_time1.text == '2015-06-01T00:36:23.03Z'
        assert isinstance(start_date_time1, Label)

        # Searches with multiple results (obtain first result)
        axis_name = self.label.find('.//axis_name')
        assert axis_name.text == 'Time'

        # Namespace searching (for non-PDS namespace)
        local_reference_type1 = self.label.find('.//disp:local_reference_type', unmodified=False)
        local_reference_type2 = self.label.find('.//disp:local_reference_type', unmodified=True)

        assert local_reference_type1.text == local_reference_type2.text == 'display_settings_to_array'

        # Namespace searching (for PDS namespace)
        discipline_name1 = self.label.find('.//discipline_name', unmodified=False)
        discipline_name2 = self.label.find('.//pds:discipline_name', unmodified=True)

        assert discipline_name1.text == discipline_name2.text == 'Atmospheres'

        # Namespace searching (when prefix does not match)
        bin_width_desc1 = self.label.find('.//sp:bin_width_desc', unmodified=False)
        bin_width_desc2 = self.label.find('.//sp_wrong:bin_width_desc', unmodified=True)

        assert bin_width_desc1.text == bin_width_desc2.text == 'some description'

        # Namespace searching (via namespace argument)
        namespaces = {'pds_wrong': 'http://pds.nasa.gov/pds4/pds/v1',
                      'fake_prefix': 'http://pds.nasa.gov/pds4/fake_prefix/v1'}

        start_date_time3 = self.label.find('.//start_date_time', unmodified=False, namespaces=namespaces)
        start_date_time4 = self.label.find('.//pds_wrong:start_date_time', unmodified=True, namespaces=namespaces)

        assert start_date_time3.text == start_date_time4.text == '2015-06-01T00:36:23.03Z'

        label_keyword1 = self.label.find('.//fake_prefix:label_keyword', unmodified=False, namespaces=namespaces)
        label_keyword2 = self.label.find('.//fake_prefix:label_keyword', unmodified=True, namespaces=namespaces)

        assert label_keyword1.text == label_keyword2.text == 'test element'

        # Ensure that returned result still has both unmodified and convenient root
        file1 = self.label.find('.//File_Area_Observational')[0]
        file2 = self.label.find('.//File')

        assert isinstance(file1, Label)
        assert xml_equal(file1.getroot(unmodified=True), file2.getroot(unmodified=True))
        assert xml_equal(file1.getroot(unmodified=False), file2.getroot(unmodified=False))

        # Test return_ET argument
        title1 = self.label.find('.//title', return_ET=False)
        title2 = self.label.find('.//title', return_ET=True)
        assert xml_equal(title1, title2)
        assert isinstance(title2, compat.ET_Element)

    def test_findall(self):

        # Direct path and descendant search matching
        start_date_time1 = self.label.findall('Observation_Area/Time_Coordinates/start_date_time')
        start_date_time2 = self.label.findall('.//start_date_time')

        assert xml_equal(start_date_time1[0], start_date_time2[0])
        assert start_date_time1[0].text == '2015-06-01T00:36:23.03Z'

        # Ensure we get a list back even with one result
        assert isinstance(start_date_time1, list)
        assert isinstance(start_date_time2, list)
        assert len(start_date_time1) == len(start_date_time2) == 1

        # Searches with multiple results
        axis_names = self.label.findall('.//axis_name')
        assert len(axis_names) == 3
        assert (axis_names[0].text, axis_names[1].text, axis_names[2].text) == ('Time', 'Line', 'Sample')

        for axis_name in axis_names:
            assert isinstance(axis_name, Label)

        # Namespace searching (for non-PDS namespace)
        local_reference_type1 = self.label.findall('.//disp:local_reference_type', unmodified=False)
        local_reference_type2 = self.label.findall('.//disp:local_reference_type', unmodified=True)

        assert local_reference_type1[0].text == local_reference_type2[0].text == 'display_settings_to_array'

        # Namespace searching (for PDS namespace)
        discipline_name1 = self.label.findall('.//discipline_name', unmodified=False)
        discipline_name2 = self.label.findall('.//pds:discipline_name', unmodified=True)

        assert discipline_name1[0].text == discipline_name2[0].text == 'Atmospheres'

        # Namespace searching (when prefix does not match)
        bin_width_desc1 = self.label.findall('.//sp:bin_width_desc', unmodified=False)
        bin_width_desc2 = self.label.findall('.//sp_wrong:bin_width_desc', unmodified=True)

        assert bin_width_desc1[0].text == bin_width_desc2[0].text == 'some description'

        # Namespace searching (via namespace argument)
        namespaces = {'pds_wrong': 'http://pds.nasa.gov/pds4/pds/v1',
                      'fake_prefix': 'http://pds.nasa.gov/pds4/fake_prefix/v1'}

        start_date_time3 = self.label.findall('.//start_date_time', unmodified=False, namespaces=namespaces)
        start_date_time4 = self.label.findall('.//pds_wrong:start_date_time', unmodified=True, namespaces=namespaces)

        assert start_date_time3[0].text == start_date_time4[0].text == '2015-06-01T00:36:23.03Z'

        label_keyword1 = self.label.findall('.//fake_prefix:label_keyword', unmodified=False, namespaces=namespaces)
        label_keyword2 = self.label.findall('.//fake_prefix:label_keyword', unmodified=True, namespaces=namespaces)

        assert label_keyword1[0].text == label_keyword2[0].text == 'test element'

        # Ensure that returned result still has both unmodified and convenient root
        file1 = self.label.findall('.//File_Area_Observational')[0]
        file2 = self.label.findall('.//File')

        assert isinstance(file1[0], Label)
        assert xml_equal(file1[0].getroot(unmodified=True), file2[0].getroot(unmodified=True))
        assert xml_equal(file1[0].getroot(unmodified=False), file2[0].getroot(unmodified=False))

        # Test return_ET argument
        title1 = self.label.findall('.//title', return_ET=False)
        title2 = self.label.findall('.//title', return_ET=True)
        assert xml_equal(title1[0], title2[0])
        assert isinstance(title2, list)
        assert isinstance(title2[0], compat.ET_Element)

    def test_findtext(self):

        # Direct path and descendant search matching
        start_date_time1 = self.label.findtext('Observation_Area/Time_Coordinates/start_date_time')
        start_date_time2 = self.label.findtext('.//start_date_time')

        assert start_date_time1 == start_date_time2 == '2015-06-01T00:36:23.03Z'

        # Ensure we get the first value back in a search with multiple results
        first_axis_name = self.label.findtext('.//axis_name')
        assert first_axis_name == 'Time'

        # Default value when no result is found
        nonexistent_element = self.label.findtext('nonexistent_element', default='not found')
        assert nonexistent_element == 'not found'

        # Namespace searching
        discipline_name1 = self.label.findtext('.//discipline_name', unmodified=False)
        discipline_name2 = self.label.findtext('.//pds:discipline_name', unmodified=True)

        assert discipline_name1 == discipline_name2 == 'Atmospheres'

    def test_iter(self):

        # Test without tag filtering

        label_iterator = self.label.iter()
        element_iterator = self.label.getroot().iter()

        # Ensure result is an iterator with same number of values
        assert isinstance(label_iterator, collections_abc.Iterator)
        assert len(list(label_iterator)) == len(list(element_iterator))

        # Ensure each value is a label identical to the element
        for i, element in enumerate(label_iterator):
            assert isinstance(element, Label)
            assert element.getroot() == element_iterator[i]

        # Test with tag filtering

        label_iterator = self.label.iter(tag="Axis_Array")
        element_iterator = self.label.getroot().iter(tag="Axis_Array")

        # Ensure result is an iterator with same number of values
        assert isinstance(label_iterator, collections_abc.Iterator)
        assert len(list(label_iterator)) == len(list(element_iterator))

        # Ensure each value is a label identical to the element
        for i, element in enumerate(label_iterator):
            assert isinstance(element, Label)
            assert element.getroot() == element_iterator[i]

        # Test with non-existent tag
        label_iterator = self.label.iter(tag="nonexistent")

        assert isinstance(label_iterator, collections_abc.Iterator)
        assert len(list(label_iterator)) == 0

    def test_itertext(self):

        text_iterator1 = self.label.itertext()
        text_iterator2 = self.label.getroot().itertext()

        assert isinstance(text_iterator1, collections_abc.Iterator)
        assert list(text_iterator1) == list(text_iterator2)

    def test_unicode(self):

        # Test unicode element tag and text
        unicode_element = self.label.find('.//unicode_elemènt')
        assert unicode_element.tag == 'unicode_elemènt'
        assert unicode_element.text == 'elemènt value'

        # Test unicode attribute name and value
        attribute1 = unicode_element.get('ằttribute')
        attribute2 = unicode_element.attrib['ằttribute']
        assert attribute1 == attribute2 == 'attrįbute value'

    def test_namespace_map(self):

        unmodified_map = self.label.get_namespace_map(unmodified=True)
        convenient_map = self.label.get_namespace_map(unmodified=False)

        assert unmodified_map == {'http://pds.nasa.gov/pds4/pds/v1': '',
                                  'http://pds.nasa.gov/pds4/disp/v1': 'disp',
                                  'http://pds.nasa.gov/pds4/sp/v1': 'sp_wrong',
                                  'http://pds.nasa.gov/pds4/fake_prefix/v1': 'fake_prefix',
                                  'http://www.w3.org/2001/XMLSchema-instance': 'xsi'}

        assert convenient_map == {'http://pds.nasa.gov/pds4/pds/v1': '',
                                  'http://pds.nasa.gov/pds4/disp/v1': 'disp',
                                  'http://pds.nasa.gov/pds4/sp/v1': 'sp',
                                  'http://pds.nasa.gov/pds4/fake_prefix/v1': 'fake_prefix',
                                  'http://www.w3.org/2001/XMLSchema-instance': 'xsi'}

    def test_to_dict(self):

        target_ident = self.label.find('.//Target_Identification')

        # Test convenient root, with cast values off and without skipping attributes
        dict1 = target_ident.to_dict(unmodified=False, cast_values=False, skip_attributes=False)
        expected_dict1 = OrderedDict([
            ('Target_Identification',
                OrderedDict([
                    ('name', 'MARS'),
                    ('type', 'Planet'),
                    ('cast', '1'),
                    ('spaces', 'test text'),
                    ('Internal_Reference',
                        OrderedDict([
                            ('lid_reference', 'urn:nasa:pds:context:target:planet.mars'),
                            ('reference_type', 'data_to_target')
                        ])
                    ),
                    ('unicode_elemènt',
                        OrderedDict([
                            ('@ằttribute', 'attrįbute value'),
                            ('_text', 'elemènt value')
                        ])
                     ),
                    ('fake_prefix:label_keyword', 'test element')
                ])
             )
        ])

        assert dict1 == expected_dict1

        # Test unmodified root, with cast values on and skipping attributes
        dict2 = target_ident.to_dict(unmodified=True, cast_values=True, skip_attributes=True)
        expected_dict2 = OrderedDict([
            ('Target_Identification',
                OrderedDict([
                    ('name', 'MARS'),
                    ('type', 'Planet'),
                    ('cast', 1),
                    ('spaces', '  test  text  '),
                    ('Internal_Reference',
                        OrderedDict([
                            ('lid_reference', 'urn:nasa:pds:context:target:planet.mars'),
                            ('reference_type', 'data_to_target')
                        ])
                    ),
                    ('unicode_elemènt', 'elemènt value'),
                    ('fake_prefix:label_keyword', 'test element')
                ])
             )
        ])

        assert dict2 == expected_dict2

    def test_to_string(self):

        target_ident = self.label.find('.//Target_Identification')

        # Make Python 2.6 adjustments, which includes prefix in more local spot than later Python versions
        namespace = ' xmlns:fake_prefix="http://pds.nasa.gov/pds4/fake_prefix/v1"'
        PY26 = sys.version_info[0:2] == (2, 6)
        py26_namespace = namespace if PY26 else ''
        py27plus_namespace = namespace if (not PY26) else ''

        # Test convenient root, with pretty_print off
        string1 = target_ident.to_string(unmodified=False, pretty_print=False)
        expected_string1 = (
            '    <Target_Identification{0}>'                                                        '\n'
            '      <name>MARS</name>'                                                               '\n'
            '      <type>Planet</type>'                                                             '\n'
            '      <cast>1</cast>'                                                                  '\n'
            '        <spaces>test text</spaces>'                                                    '\n'
            '      <Internal_Reference>'                                                            '\n'
            '        <lid_reference>urn:nasa:pds:context:target:planet.mars</lid_reference>'        '\n'
            '        <reference_type>data_to_target</reference_type>'                               '\n'
            '      </Internal_Reference>'                                                           '\n'
            '      <unicode_elemènt ằttribute="attrįbute value">elemènt value</unicode_elemènt>'    '\n'
            '      <fake_prefix:label_keyword{1}>test element</fake_prefix:label_keyword>'          '\n'
            '    </Target_Identification>'
        ).format(py27plus_namespace, py26_namespace)

        assert string1 == expected_string1

        # Test unmodified root, with pretty_print on
        string2 = target_ident.to_string(unmodified=True, pretty_print=True)
        expected_string2 = (
            '<Target_Identification xmlns="http://pds.nasa.gov/pds4/pds/v1"{0}>'                '\n'
            '  <name>MARS</name>'                                                               '\n'
            '  <type>Planet</type>'                                                             '\n'
            '  <cast>1</cast>'                                                                  '\n'
            '  <spaces>  test  text  </spaces>'                                                 '\n'
            '  <Internal_Reference>'                                                            '\n'
            '    <lid_reference>urn:nasa:pds:context:target:planet.mars</lid_reference>'        '\n'
            '    <reference_type>data_to_target</reference_type>'                               '\n'
            '  </Internal_Reference>'                                                           '\n'
            '  <unicode_elemènt ằttribute="attrįbute value">elemènt value</unicode_elemènt>'    '\n'
            '  <fake_prefix:label_keyword{1}>test element</fake_prefix:label_keyword>'          '\n'
            '</Target_Identification>'
        ).format(py27plus_namespace, py26_namespace)

        assert string2 == expected_string2


class TestTableManifest(PDS4ToolsTestCase):

    def setup_class(self):

        label = Label().from_file(self.data('manifest_tester.xml'))
        table_label = label.find('.//Table_Character')

        self.manifest = TableManifest.from_label(table_label)

    def test_len(self):

        assert len(self.manifest) == self.manifest.num_items == 25


class TestTableDataTypes(PDS4ToolsTestCase):

    def setup_class(self):

        structures = pds4_read(self.data('test_table_data_types.xml'), lazy_load=True, quiet=True)
        self.table = structures[0]

    def test_msb_types(self):

        table = self.table

        # Test SignedByte
        _check_array_equal(table['SignedByte'], [-100, 127, 50], 'int8')

        # Test UnsignedByte
        _check_array_equal(table['UnsignedByte'], [150, 253, 0], 'uint8')

        # Test SignedMSB2
        _check_array_equal(table['SignedMSB2'], [-32237, 25020, -100], 'int16')

        # Test SignedMSB4
        _check_array_equal(table['SignedMSB4'], [2147480000, -1047483647, 143352], 'int32')

        # Test SignedMSB8
        _check_array_equal(table['SignedMSB8'], [9003372036854775800, -59706567879, 8379869176], 'int64')

        # Test UnsignedMSB2
        _check_array_equal(table['UnsignedMSB2'], [502, 34542, 60535], 'uint16')

        # Test UnsignedMSB4
        _check_array_equal(table['UnsignedMSB4'], [50349235, 3994967214, 243414], 'uint32')

        # Test UnsignedMSB8
        _check_array_equal(table['UnsignedMSB8'], [987654073709550582, 25020, 17396744073709550582], 'uint64')

        # Test IEEE754MSBSingle
        _check_array_equal(table['IEEE754MSBSingle'], [-1.3862e-43, 1.25e-41, 3.403451e+25], 'float32')

        # Test IEEE754MSBDouble
        _check_array_equal(table['IEEE754MSBDouble'], [1.79e+308, -5.7303e100, -101.432310], 'float64')

        # Test ComplexMSB8
        complex_msb8 = [complex(3.202823e38, 1.41e5), complex(1.63230, -1.2360e10),
                        complex(1.155494e-38, -500.23)]

        _check_array_equal(table['ComplexMSB8'], complex_msb8, 'complex64')

        # Test ComplexMSB16
        complex_msb16 = [complex(2.215073858e-308, 1.41e5), complex(5.072014, -1.2360e10),
                         complex(-1.65e308, 1.797693e308)]

        _check_array_equal(table['ComplexMSB16'], complex_msb16, 'complex128')

    def test_lsb_types(self):

        table = self.table

        # Test SignedLSB2
        _check_array_equal(table['SignedLSB2'], [-32237, 25020, -100], 'int16')

        # Test SignedLSB4
        _check_array_equal(table['SignedLSB4'], [2147480000, -1047483647, 143352], 'int32')

        # Test SignedLSB8
        _check_array_equal(table['SignedLSB8'], [9003372036854775800, -59706567879, 8379869176], 'int64')

        # Test UnsignedLSB2
        _check_array_equal(table['UnsignedLSB2'], [502, 34542, 60535], 'uint16')

        # Test UnsignedLSB4
        _check_array_equal(table['UnsignedLSB4'], [50349235, 3994967214, 243414], 'uint32')

        # Test UnsignedLSB8
        _check_array_equal(table['UnsignedLSB8'], [987654073709550582, 25020, 17396744073709550582], 'uint64')

        # Test IEEE754LSBSingle
        _check_array_equal(table['IEEE754LSBSingle'], [-1.3862e-43, 1.25e-41, 3.403451e+25], 'float32')

        # Test IEEE754LSBDouble
        _check_array_equal(table['IEEE754LSBDouble'], [1.79e+308, -5.7303e100, -101.432310], 'float64')

        # Test ComplexLSB8
        complex_lsb8 = [complex(3.202823e38, 1.41e5), complex(1.63230, -1.2360e10),
                        complex(1.155494e-38, -500.23)]

        _check_array_equal(table['ComplexLSB8'], complex_lsb8, 'complex64')

        # Test ComplexLSB16
        complex_lsb16 = [complex(2.215073858e-308, 1.41e5), complex(5.072014, -1.2360e10),
                         complex(-1.65e308, 1.797693e308)]

        _check_array_equal(table['ComplexLSB16'], complex_lsb16, 'complex128')

    def test_ascii_types(self):

        table = self.table

        # Test ASCII_Real
        _check_array_equal(table['ASCII_Real'], [1.79e+308, -5.7303e100, -101.432310], 'float64')

        # Test ASCII_Integer
        _check_array_equal(table['ASCII_Integer'], [-9003372036854775800, 396744073709550582, 25020], 'int64')

        # Test ASCII_NonNegative_Integer
        _check_array_equal(table['ASCII_NonNegative_Integer'], [17396744073709550582, 25020, 0], 'uint64')

        # Test ASCII_Boolean
        _check_array_equal(table['ASCII_Boolean'], [False, False, True], 'bool')

        # Test ASCII_Numeric_Base2
        _check_array_equal(table['ASCII_Numeric_Base2'], [5, 20, 992], 'int16')

        # Test ASCII_Numeric_Base8
        _check_array_equal(table['ASCII_Numeric_Base8'], [65, 13464640, 990198263], 'int32')

        # Test ASCII_Numeric_Base16
        _check_array_equal(table['ASCII_Numeric_Base16'], [4024, 2881494974, 956185033423], 'int64')

        # Test ASCII_String
        ascii_string = [' Test string 1  ', ' Test  2        ', ' Test longest 3 ']
        _check_array_equal(table['ASCII_String'], ascii_string, 'U16')

        # Test UTF8_String
        utf8_string = [' Tést stríng 1  ', ' Tést  2         ', ' Tést longést 3 ']
        _check_array_equal(table['UTF8_String'], utf8_string, 'U18')

    @pytest.mark.xfail(tuple(map(int, np.__version__.split('.')[:2])) < (1, 11),
                       reason="NumPy datetime64 API changes.")
    def test_dates(self):

        table = self.table

        # Test ASCII_Date_Time_YMD_UTC
        date_string_ymd = table['Dates_YMD_UTC']
        date_ymd = [np.datetime64('2018-10-10T05:05'), np.datetime64('2018-01-10T05:05:05.123'),
                    np.datetime64('2014')]

        _check_array_equal(data_type_convert_dates(date_string_ymd), date_ymd, 'datetime64[us]')

        # Test ASCII_Date_DOY
        date_string_doy = table['Dates_DOY_Local']
        date_doy = [np.datetime64('2018-07-19'), np.datetime64('2018-07-20'), np.datetime64('2018-07-21')]

        _check_array_equal(data_type_convert_dates(date_string_doy), date_doy, 'datetime64[D]')

    def test_bitstrings(self):

        # Test bit strings with decode_strings on
        structures1 = pds4_read(self.data('test_table_data_types.xml'),
                                decode_strings=True, lazy_load=True, quiet=True)

        # Test via UnsignedBitString
        unsigned_bitstring = [b'\x1cZ\xd8', b'\xfb\xfb\x18', b'ZY\xe8']
        _check_array_equal(structures1[0]['UnsignedBitString'], unsigned_bitstring, 'S3')

        # Test bit strings with decode_strings off
        structures2 = pds4_read(self.data('test_table_data_types.xml'),
                                decode_strings=True, lazy_load=True, quiet=True)

        # Test via SignedBitString
        signed_bitstring = [b'\x013', b'\xfe\x82', b'!\xfc']
        _check_array_equal(structures2[0]['SignedBitString'], signed_bitstring, 'S2')

    def test_overflow(self):

        table = self.table

        # Test overflow to 'object' dtype (bigger than int64 or uint64) when allowed by standard

        # Test with data being over uint64
        overflow_base16 = [17396744073709550582, 36893488147419103231, 73786976294838206465]
        _check_array_equal(table['Overflow ASCII_Numeric_Base16'], overflow_base16, 'object')

        # Test with scaling/offset decreasing data from over uint64 to under
        overflow_base8 = [0, -6342197851746992128, -1129576409333760]
        _check_array_equal(table['Overflow/Scaling ASCII_Numeric_Base8'], overflow_base8, 'int64')

        # Test with scaling/offset increasing data from under uint64 to over
        overflow_base2 = [100000000000000065535, 100000000000000063347, 100000000000000000117]
        _check_array_equal(table['Overflow/Scaling ASCII_Numeric_Base2'], overflow_base2, 'object')

    def test_scaling(self):

        table = self.table

        # Test Integer Scaling/Offsets
        scaled_integers1 = [987654540100, -987654539900, 100]
        scaled_integers2 = [987654539899.5, -987654540100.5, -100.5]

        _check_array_equal(table['Scaling/Offset Integer 1'], scaled_integers1, 'int64')
        _check_array_equal(table['Scaling/Offset Integer 2'], scaled_integers2, 'float64')

        # Test Float Scaling/Offset
        _check_array_equal(table['Scaling/Offset Float'], [-3.2e+48, 3.2e+48, 1234.0], 'float64')


class TestArrayDataTypes(PDS4ToolsTestCase):

    def setup_class(self):

        self.structures = pds4_read(self.data('test_array_data_types.xml'), lazy_load=True, quiet=True)

    def test_msb_types(self):

        structures = self.structures

        # Test SignedByte
        _check_array_equal(structures['SignedByte'].data, [-100, 127, 50], 'int8')

        # Test UnsignedByte
        _check_array_equal(structures['UnsignedByte'].data, [150, 253, 0], 'uint8')

        # Test SignedMSB2
        _check_array_equal(structures['SignedMSB2'].data, [-32237, 25020, -100], 'int16')

        # Test SignedMSB4
        _check_array_equal(structures['SignedMSB4'].data, [2147480000, -1047483647, 143352], 'int32')

        # Test SignedMSB8
        _check_array_equal(structures['SignedMSB8'].data, [9003372036854775800, -59706567879, 8379869176], 'int64')

        # Test UnsignedMSB2
        _check_array_equal(structures['UnsignedMSB2'].data, [502, 34542, 60535], 'uint16')

        # Test UnsignedMSB4
        _check_array_equal(structures['UnsignedMSB4'].data, [50349235, 3994967214, 243414], 'uint32')

        # Test UnsignedMSB8
        _check_array_equal(structures['UnsignedMSB8'].data,  [987654073709550582, 25020, 17396744073709550582], 'uint64')

        # Test IEEE754MSBSingle
        _check_array_equal(structures['IEEE754MSBSingle'].data, [-1.3862e-43, 1.25e-41, 3.403451e+25], 'float32')

        # Test IEEE754MSBDouble
        _check_array_equal(structures['IEEE754MSBDouble'].data, [1.79e+308, -5.7303e100, -101.432310], 'float64')

        # Test ComplexMSB8
        complex_msb8 = [complex(3.202823e38, 1.41e5), complex(1.63230, -1.2360e10),
                        complex(1.155494e-38, -500.23)]

        _check_array_equal(structures['ComplexMSB8'].data, complex_msb8, 'complex64')

        # Test ComplexMSB16
        complex_msb16 = [complex(2.215073858e-308, 1.41e5), complex(5.072014, -1.2360e10),
                         complex(-1.65e308, 1.797693e308)]

        _check_array_equal(structures['ComplexMSB16'].data, complex_msb16, 'complex128')

    def test_lsb_types(self):

        structures = self.structures

        # Test SignedLSB2
        _check_array_equal(structures['SignedLSB2'].data, [-32237, 25020, -100], 'int16')

        # Test SignedLSB4
        _check_array_equal(structures['SignedLSB4'].data, [2147480000, -1047483647, 143352], 'int32')

        # Test SignedLSB8
        _check_array_equal(structures['SignedLSB8'].data, [9003372036854775800, -59706567879, 8379869176], 'int64')

        # Test UnsignedLSB2
        _check_array_equal(structures['UnsignedLSB2'].data, [502, 34542, 60535], 'uint16')

        # Test UnsignedLSB4
        _check_array_equal(structures['UnsignedLSB4'].data, [50349235, 3994967214, 243414], 'uint32')

        # Test UnsignedLSB8
        _check_array_equal(structures['UnsignedLSB8'].data, [987654073709550582, 25020, 17396744073709550582], 'uint64')

        # Test IEEE754LSBSingle
        _check_array_equal(structures['IEEE754LSBSingle'].data, [-1.3862e-43, 1.25e-41, 3.403451e+25], 'float32')

        # Test IEEE754LSBDouble
        _check_array_equal(structures['IEEE754LSBDouble'].data, [1.79e+308, -5.7303e100, -101.432310], 'float64')

        # Test ComplexLSB8
        complex_lsb8 = [complex(3.202823e38, 1.41e5), complex(1.63230, -1.2360e10),
                        complex(1.155494e-38, -500.23)]

        _check_array_equal(structures['ComplexLSB8'].data, complex_lsb8, 'complex64')

        # Test ComplexLSB16
        complex_lsb16 = [complex(2.215073858e-308, 1.41e5), complex(5.072014, -1.2360e10),
                         complex(-1.65e308, 1.797693e308)]

        _check_array_equal(structures['ComplexLSB16'].data, complex_lsb16, 'complex128')

    def test_scaling(self):

        structures = self.structures

        # Test Integer Scaling/Offsets
        scaled_integers1 = [987654540100, -987654539900, 100]
        scaled_integers2 = [987654539899.5, -987654540100.5, -100.5]

        _check_array_equal(structures['Integer Scaling/Offset 1'].data, scaled_integers1, 'int64')
        _check_array_equal(structures['Integer Scaling/Offset 2'].data, scaled_integers2, 'float64')

        # Test Float Scaling/Offset
        _check_array_equal(structures['Float Scaling/Offset'].data, [-3.2e+48, 3.2e+48, 1234.0], 'float64')


class TestMaskedData(PDS4ToolsTestCase):

    def setup_class(self):

        self.structures = pds4_read(self.data('test_masked_data.xml'), lazy_load=True, quiet=True)

    def test_table_as_masked(self):

        table = self.structures[0].as_masked()

        # Test as_masked in binary fields (SignedMSB4)
        signed_msb4 = np.ma.MaskedArray([2147480000, -1047483647, -99999, -99999],
                                        mask=[False, False, True, True])

        _check_array_equal(table['SignedMSB4'], signed_msb4, 'int32')
        _check_array_equal(table['SignedMSB4'].filled(), np.asarray(signed_msb4), 'int32')
        assert np.array_equal(table['SignedMSB4'].mask, signed_msb4.mask)

        # Test as_masked in binary fields (IEEE754MSBDouble)
        double = np.ma.MaskedArray([1.79e+308, -5.7303e100, -5.7303e100, -101.43231],
                                   mask=[False, True, True, False])

        _check_array_equal(table['IEEE754MSBDouble'], double, 'float64')
        _check_array_equal(table['IEEE754MSBDouble'].filled(), np.asarray(double), 'float64')
        assert np.array_equal(table['IEEE754MSBDouble'].mask, double.mask)

        # Test as_masked in character fields (ASCII_Real)
        ascii_real = np.ma.MaskedArray([1.79e+308, -9.99, -101.432310, -9.99],
                                       mask=[False, True, False, True])

        _check_array_equal(table['ASCII_Real'], ascii_real, 'float64')
        _check_array_equal(table['ASCII_Real'].filled(), np.asarray(ascii_real), 'float64')
        assert np.array_equal(table['ASCII_Real'].mask, ascii_real.mask)

        # Test as_masked in character fields (ASCII_Integer)
        ascii_integer = np.ma.MaskedArray([-9003372036854775800, 100000000, 396744073709550582, 25020],
                                          mask=[False, True, False, False])

        _check_array_equal(table['ASCII_Integer'], ascii_integer, 'int64')
        _check_array_equal(table['ASCII_Integer'].filled(), np.asarray(ascii_integer), 'int64')
        assert np.array_equal(table['ASCII_Integer'].mask, ascii_integer.mask)

        # Test as_masked in character fields (ASCII_Numeric_Base16 that does not fit into int64)
        ascii_integer = np.ma.MaskedArray([17396744073709550582, 36893488147419103231, 73786976294838206465, 17396744073709550582],
                                          mask=[True, False, False, True])

        _check_array_equal(table['ASCII_Numeric_Base16'], ascii_integer, 'object')
        _check_array_equal(table['ASCII_Numeric_Base16'].filled(), np.asarray(ascii_integer), 'object')
        assert np.array_equal(table['ASCII_Numeric_Base16'].mask, ascii_integer.mask)

        # Test as_masked, with Special_Constants together with scaling/offset
        signed_msb4 = np.ma.MaskedArray([2.14748000e+10,  -1.04748365e+10, -99999, -99999],
                                        mask=[False, False, True, True])

        _check_array_equal(table['SignedMSB4 with Scaling/Offset'], signed_msb4, 'float64')
        _check_array_equal(table['SignedMSB4 with Scaling/Offset'].filled(), np.asarray(signed_msb4), 'float64')
        assert np.array_equal(table['SignedMSB4 with Scaling/Offset'].mask, signed_msb4.mask)

        # Test retrieval of individual elements from records in as_masked() data
        assert np.equal(table[0][0], 2147480000)
        assert np.equal(table.data.filled()[3][-2], -99999.0)

    def test_table_scaling_with_special_constants(self):

        table = self.structures[0]

        # Test that Special_Constants are ignored during scaling/offset for binary fields
        signed_msb4 = [2.14748000e+10,  -1.04748365e+10, -99999, -99999]
        _check_array_equal(table['SignedMSB4 with Scaling/Offset'], signed_msb4, 'float64')

        # Test that Special_Constants are ignored during scaling/offset for character fields
        ascii_real = [1.79000000e+307,  -9.99,  -10.143231, -9.99]
        _check_array_equal(table['ASCII_Real with Scaling'], ascii_real, 'float64')

    def test_array_as_masked(self):

        # Test as_masked in array fields (UnsignedMSB4)
        array_unsigned_msb4 = self.structures[1].as_masked()
        unsigned_msb4 = np.ma.MaskedArray([50349235, 3994967214, 3994967214, 243414],
                                          mask=[False, True, True, False])

        _check_array_equal(array_unsigned_msb4.data, unsigned_msb4, 'uint32')
        assert np.array_equal(array_unsigned_msb4.data.mask, unsigned_msb4.mask)

        # Test as_masked in array fields (IEEE754LSBDouble)
        array_lsb_double = self.structures[2].as_masked()
        lsb_double = np.ma.MaskedArray([1.79e+200, -5.7303e100, -101.432310, 1.79e+200],
                                       mask=[True, False, False, True])

        _check_array_equal(array_lsb_double.data, lsb_double, 'float64')
        assert np.array_equal(array_lsb_double.data.mask, lsb_double.mask)

        # Test as_masked, with Special_Constants together with scaling/offset
        array_lsb_double = self.structures[4].as_masked()
        lsb_double = np.ma.MaskedArray([1.79e+200, -5.730300000000001e+102, -10133.231, 1.79e+200],
                                       mask=[True, False, False, True])

        assert np.array_equal(array_lsb_double.data.mask, lsb_double.mask)
        _check_array_equal(array_lsb_double.data, lsb_double, 'float64')

    def test_array_scaling_with_special_constants(self):

        # Test that Special_Constants are ignored during scaling/offset for arrays (integers)
        array_unsigned_msb4 = self.structures[3]

        unsigned_msb4 = [251746175, 3994967214, 3994967214, 1217070]
        _check_array_equal(array_unsigned_msb4.data, unsigned_msb4, 'uint32')

        # Test that Special_Constants are ignored during scaling/offset for arrays (reals)
        array_lsb_double = self.structures[4]

        lsb_double = [1.79e+200, -5.730300000000001e+102, -10133.231, 1.79e+200]
        _check_array_equal(array_lsb_double.data, lsb_double, 'float64')

    def test_data_loaded(self):

        structures = pds4_read(self.data('test_masked_data.xml'), lazy_load=True, quiet=True)

        # Test ``as_masked`` does not load data automatically in tables
        table = structures[0].as_masked()
        assert not table.data_loaded
        table.data
        assert table.data_loaded

        # Test ``as_masked`` and ``section``does not load data automatically in arrays
        array = structures[1].as_masked()
        assert not array.data_loaded
        array.section[:]
        assert not array.data_loaded
        array.data
        assert array.data_loaded

    def test_fill_value(self):

        # Test in tables
        table = self.structures[0].as_masked()
        assert np.isclose(table['IEEE754MSBDouble'].fill_value, -5.7303e100)

        # Test in arrays
        array = self.structures[1].as_masked()
        assert np.isclose(array.data.fill_value, 3994967214)

    def test_no_mask(self):

        structures = pds4_read(self.data('äf.xml'), lazy_load=True, quiet=True)

        # Test ArrayStructure.as_masked on arrays without Special_Constants
        structure1 = structures['data_Primary']
        _check_array_equal(structure1.data, structure1.as_masked().data, structure1.data.dtype)
        assert(isinstance(structure1.as_masked().data, PDS_marray))

        # Test TableStructure.as_masked on tables without Special_Constants
        structure2 = structures['data_Engineering']
        _check_array_equal(structure2.data, structure2.as_masked().data, structure2.data.dtype)
        assert(isinstance(structure2.as_masked().data, PDS_marray))


class TestDownloadFile(PDS4ToolsTestCase):

    def test_download_file(self):

        # Test downloads with ASCII URL
        structures_web = pds4_read(self.data('colors.xml', from_web=True), lazy_load=True)  # afö.xml
        structures_local = pds4_read(self.data('colors.xml'))

        # Test that lazy-load works with URLs
        assert(structures_web[0].data_loaded is False)

        # Test that data is equal whether downloaded or accessed locally
        assert(np.array_equal(structures_web[0].data, structures_local[0].data))

        # Test downloads with both encoded and decoded UTF-8 in URL
        structures_web1 = pds4_read(self.data('äf.xml', from_web=True), lazy_load=True)
        structures_web2 = pds4_read(self.data('%C3%A4f.xml', from_web=True), lazy_load=True)
        structures_local = pds4_read(self.data('äf.xml'))

        assert xml_equal(structures_web1.label, structures_local.label)
        assert xml_equal(structures_web2.label, structures_local.label)


class TestDeprecation(PDS4ToolsTestCase):

    def test_deprecated(self):

        @deprecated('0.0')
        class DeprecatedClass(object):

            def __init__(self, arg):
                self._arg = arg

            @deprecated('0.0')
            @property
            def deprecated_property(self):
                return self._arg

        @deprecated('0.0')
        def deprecated_func():
            return None

        # Test deprecated class
        with pytest.warns(PDS4ToolsDeprecationWarning, match=r'0.0'):
            obj = DeprecatedClass('value')

        # Test deprecated property
        with pytest.warns(PDS4ToolsDeprecationWarning, match=r'0.0'):
            val = obj.deprecated_property

        # Test deprecated function
        with pytest.warns(PDS4ToolsDeprecationWarning, match=r'0.0'):
            val = deprecated_func()

    def test_rename_parameter(self):

        class TestClass(object):

            @rename_parameter('0.0', 'arg2_old', 'arg2')
            def __init__(self, arg1, arg2=None, arg3=True):
                self.arg1 = arg1
                self.arg2 = arg2

        @rename_parameter('0.0', 'arg2', 'arg3')
        def test_function(arg1, arg3):
            return arg1 + arg3

        # Test renaming keyword argument with-in a method
        with pytest.warns(PDS4ToolsDeprecationWarning, match=r'renamed.*0.0'):
            obj = TestClass(0, arg2_old=1)
            assert obj.arg2 == 1

        # Test renaming positional argument with-in a function
        with pytest.warns(PDS4ToolsDeprecationWarning, match=r'renamed.*0.0'):
            val = test_function(1, arg2=2)
            assert val == 3

        # Test for lack of spurious warnings
        with warnings.catch_warnings():
            warnings.simplefilter('error')

            obj = TestClass(0, arg2=2, arg3=False)
            obj = TestClass(0, arg3=False)
            test_function(1, 2)

    def test_delete_parameter(self):

        class TestClass(object):

            @delete_parameter('0.0', 'arg2', alternative='arg3')
            def __init__(self, arg1, arg2=None, arg3=True):
                self.arg1 = arg1
                self.arg3 = arg3

        @delete_parameter('0.0', 'arg2')
        def test_function(arg1, arg2):
            return arg1 + arg2

        # Test deleting keyword argument with-in a method
        with pytest.warns(PDS4ToolsDeprecationWarning, match=r'0.0.*arg3'):
            obj = TestClass(0, arg2='hello')

        # Test deleting positional argument with-in a function
        with pytest.warns(PDS4ToolsDeprecationWarning, match=r'0.0'):
            val = test_function(1, arg2=2)
            assert val == 3

        PY26 = sys.version_info[0:2] == (2, 6)
        if not PY26:
            with pytest.warns(PDS4ToolsDeprecationWarning, match=r'0.0'):
                val = test_function(1, 2)
                assert val == 3

        # Test for lack of spurious warnings
        with warnings.catch_warnings():
            warnings.simplefilter('error')

            obj = TestClass(0)
            obj = TestClass(0, arg3=True)

    def test_deprecated_docstring(self):
        
        @deprecated('0.0')
        class DeprecatedClass(object):
            """ Class description.

            Notes
            -----
            Test note.
            """
            def __init__(self, arg):
                self._arg = arg

            @deprecated('0.0')
            @property
            def deprecated_property(self):
                return self._arg

        @deprecated('0.0')
        def deprecated_func():
            """ Function description.

            Returns
            -------
            None
            """
            pass

        # Test docstring adjustment in deprecated class
        obj = DeprecatedClass
        if sys.version_info[0] > 2:
            assert '[Deprecated]' in obj.__doc__
            assert '.. deprecated::' in obj.__doc__

        # Test docstring adjustment in deprecated property
        prop = obj.deprecated_property
        assert '[Deprecated]' in prop.__doc__
        assert '.. deprecated::' in prop.__doc__

        # Test docstring adjustment in deprecated function
        func = deprecated_func
        assert '[Deprecated]' in func.__doc__
        assert '.. deprecated::' in func.__doc__


def _check_array_equal(unknown_array, known_array, known_typecode):

    is_int_array = np.issubdtype(np.asarray(unknown_array).dtype, np.integer)
    is_float_array = np.issubdtype(np.asarray(unknown_array).dtype, np.floating)
    is_complex_array = np.issubdtype(np.asarray(unknown_array).dtype, np.complexfloating)

    # Check that int values are equal
    if is_int_array:
        assert np.array_equal(unknown_array, np.asanyarray(known_array, dtype='object'))

    # Check that float values are equal
    elif is_float_array:

        # Tolerances for floating point comparison
        # (set such that differences large enough to raise eyebrows and thus should be investigated will fail)
        float_rtol = 1e-7
        float_atol = 1e-40

        assert np.allclose(unknown_array, known_array, rtol=float_rtol, atol=float_atol)

    # Check that complex values are equal
    elif is_complex_array:

        # We use float comparison here because NumPy's tolerance accounting seems strange when comparing
        # complex numbers, and allows large differences to pass (especially for very small numbers)

        unknown_real_array = np.asarray([x.real for x in unknown_array], dtype='float64')
        known_real_array = np.asarray([x.real for x in known_array], dtype='float64')

        _check_array_equal(unknown_real_array, known_real_array, 'float64')

        unknown_imag_array = np.asarray([x.imag for x in unknown_array], dtype='float64')
        known_imag_array = np.asarray([x.imag for x in known_array], dtype='float64')

        _check_array_equal(unknown_imag_array, known_imag_array, 'float64')

    # Check that all other (non-int, non-float and non-complex) values are equal
    else:
        assert np.array_equal(unknown_array, known_array)

    # Check that typecode is correct
    assert (unknown_array.dtype == known_typecode) or (unknown_array.dtype.name == known_typecode)


# Compares equality of two ElementTree Elements. Based on:
# https://bitbucket.org/formencode/official-formencode/src/3be5078c6030/formencode/doctest_xml_compare.py
def xml_equal(x1, x2):

    if x1.tag != x2.tag:
        return False

    for name, value in x1.attrib.items():
        if x2.attrib.get(name) != value:
            return False

    for name in x2.attrib:
        if name not in x1.attrib:
            return False

    if x1.text != x2.text:
        return False

    if x1.tail != x2.tail:
        return False

    cl1 = list(x1)
    cl2 = list(x2)

    if len(cl1) != len(cl2):
        return False

    i = 0
    for c1, c2 in zip(cl1, cl2):
        i += 1
        if not xml_equal(c1, c2):
            return False

    return True
