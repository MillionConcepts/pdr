from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re
import abc
import sys
import numpy as np

from .general_objects import Structure, Meta_Class, Meta_Structure
from .label_objects import Meta_SpectralCharacteristics
from .data_types import pds_to_numpy_name, PDSdtype

from ..utils.compat import OrderedDict
from ..utils.helpers import is_array_like, dict_extract
from ..utils.exceptions import PDS4StandardsException
from ..utils.logging import logger_init

from ..extern import six
from ..extern.six.moves import collections_abc
from ..extern.cached_property import threaded_cached_property

# Initialize the logger
logger = logger_init()

#################################


class TableStructure(Structure):
    """ Stores a single PDS4 table data structure.

    Contains the table's data, meta data and label portion. All forms of PDS4 tables
    (e.g. Table_Character, Table_Binary and Table_Delimited) are stored by this class.

    See `Structure`'s and `pds4_read`'s docstrings for attributes, properties and usage instructions
    of this object.

    Inherits all Attributes and Parameters from `Structure`. Overrides `info`, `data` and `from_file`
    methods to implement them.
    """

    @classmethod
    def from_file(cls, data_filename, structure_label, full_label,
                  lazy_load=False, no_scale=False, decode_strings=False):
        """ Create a table structure from relevant labels and file for the data.

        Parameters
        ----------
        data_filename : str or unicode
            Filename of the data file that contained the data for this table structure.
        structure_label : Label
            The segment of the label describing only this table structure.
        full_label : Label
            The entire label describing the PDS4 product this structure originated from.
        no_scale : bool, optional
            Read-in data will not be adjusted according to the offset and scaling factor. Defaults to False.
        decode_strings : bool, optional
            If True, strings data types contained in the returned data will be decoded to
            the ``unicode`` type in Python 2, and to the ``str`` type in Python 3. If
            false, leaves string types as byte strings. Defaults to False.
        lazy_load : bool, optional
            If True, does not read-in the data of this structure until the first attempt to access it.
            Defaults to False.

        Returns
        -------
        TableStructure
            An object representing the PDS4 table structure; contains its label, data and meta data.
        """

        # Create the meta data structure for this table
        meta_table_structure = Meta_TableStructure.from_label(structure_label, full_label)

        # Create the data structure for this table
        table_structure = cls(structure_data=None, structure_meta_data=meta_table_structure,
                              structure_label=structure_label, full_label=full_label,
                              parent_filename=data_filename)
        table_structure._no_scale = no_scale
        table_structure._decode_strings = decode_strings

        # Attempt to access the data property such that the data gets read-in (if not on lazy-load)
        if not lazy_load:
            table_structure.data

        return table_structure

    @classmethod
    def from_fields(cls, fields, no_scale=False, decode_strings=False, masked=None, **structure_kwargs):
        """ Create a table structure from PDS-compliant data or meta data.

        Parameters
        ----------
        fields : list[PDS_ndarray, PDS_marray or Meta_Field]
            A list of either fields with data, where each must contain a valid PDS4 meta_data attribute
            defining the field, or a list of valid Meta_Field's.
        no_scale : bool, optional
            If True, and input is a list of fields with data, then the data will scaled according to the
            scaling_factor and value_offset meta data. If the *fields* is meta data only, then the output
            data type will be large enough to store the scaled values. If False, no scaling or data type
            conversions will be done. Defaults to False.
        decode_strings : bool, optional
            If True, then fields containing character byte data will be converted to a dtype of unicode.
            If False, then for character data the obtained dtype will remain byte strings. Defaults to
            False.
        masked : bool or None, optional
            If True, and input is a list of fields with data, then the data will retain any masked values and
            in additional have numeric Special_Constants values masked. If False, any masked values in the
            input fields will be unmasked and data assignments will not preserve masked values. If None,
            masked values in the input will be retained only if any are present. Defaults to None.
        structure_kwargs : dict, optional
            Keywords that are passed directly to the `TableStructure` constructor.

        Returns
        -------
        TableStructure
            An object representing the PDS4 table structure. The data will contain a structured array that
            can store values for *fields* (or does store it, if input is a list of fields with data). Other
            attributes may be specified via *structure_kwargs*.
        """

        from .read_tables import new_table

        return new_table(fields, no_scale=no_scale, decode_strings=decode_strings, masked=masked,
                         **structure_kwargs)

    def info(self, abbreviated=False, output=None):
        """ Prints a summary of this data structure.

        Contains the type, number of fields and number of records in the Table.
        If *abbreviated* is True then also outputs the name and number of elements
        for each field in the table.

        Parameters
        ----------
        abbreviated : bool, optional
            If False, output additional detail. Defaults to False.
        output : file, bool or None, optional
            A file-like object to write the output to.  If set to False then instead of outputting
            to a file a list representing the summary parameters for the Structure is returned.
            Writes to ``sys.stdout`` by default.

        Returns
        -------
        None or list
            If output is False, then returns a list representing the summary parameters for the Structure.
            Otherwise returns None.
        """

        # Set default output to write to command line
        if output is None:
            output = sys.stdout

        # Obtain abbreviated version of summary
        dimensions = self.meta_data.dimensions()
        id = "'{0}'".format(self.id)
        field_info = '{0} fields x {1} records'.format(dimensions[0], dimensions[1])

        summary_args = [self.type, id, field_info]
        abbreviated_info = "{0} {1} ({2})".format(*summary_args)

        # If output is false, return list representing the various parameters of the summary
        if not output:
            return summary_args

        # Otherwise write out summary to output
        if abbreviated:
            output.write(abbreviated_info)
            output.write('\n')
            output.flush()

        else:
            output.write('Fields for {0}: \n\n'.format(abbreviated_info))

            for field in self.fields:

                name = field.meta_data['name']
                full_name = field.meta_data.full_name(separator=', ')

                full_name_print = ''
                if name != full_name:
                    full_name_print = ' (full name: {0})'.format(full_name)

                output.write(name + full_name_print + '\n')

            output.flush()

    def __getitem__(self, key):
        """ Get data for specific field in `TableStructure`.

        In the case of GROUP fields, the key can include the full location for disambiguation,
        (e.g. field_name = 'GROUP_1, GROUP_0, field_name'). See `info` method for full locations of all
        fields.

        Parameters
        ----------
        key : str, unicode, int, slice or tuple
            Selection for desired field. May be a string containing the name of a field to search for,
            similar to ``dict`` indexing functionality. May be an integer or slice specifying which field(s)'
            data to select,  similar to ``list`` or ``tuple`` indexing functionality. May be a two-valued
            tuple, with the first value providing the field name and the second value a zero-based repetition
            selector count if there are multiple fields with the same name.

        Returns
        -------
        PDS_ndarray, PDS_marray or None
            The data for the matched field, or None if no match found.

        Raises
        ------
        IndexError
            Raised if *key* is a larger int than there are fields in the table.
        ValueError
            Raised if *key* contains a name that does not match any field in the table.

        Examples
        --------
        >>> table_struct['First_Field_Name']
        >>> table_struct.field(0)

        To access two fields at the same time by name,

        >>> table_struct[['First_Field', 'Second_Field']]

        In-case of GROUP fields, we can use the full name (as given by the `info` method) for disambiguation,

        >>> table_struct['GROUP_1, GROUP_0, field_name']

        If both of the first two data structures have the name 'Field_Name', then to select the second
        we can do,

        >>> table_structure['Field_Name [1]']
        >>> table_struct.field('Field_Name', 1)

        We can also record record-wise. To obtain all fields for the first five records,

        >>> table_struct[0:5]
        """

        # Search by full or partial field name for single-valued search
        if isinstance(key, six.string_types):
            return self.field(key)

        # Search by full or partial field name for multi-valued search
        elif is_array_like(key):

            if np.issubdtype(np.asarray(key).dtype, np.character):

                fields = [self.field(_key) for _key in key]
                field_names = [pds_to_numpy_name(field.meta_data.full_name())
                               for field in fields]

                return self.data[field_names]

        # Allow all other searches (slice, specific indexes, etc)
        return self.data[key]

    def __len__(self):
        """
        Returns
        -------
        int
            Number of fields contained in the table.
        """

        if self.data_loaded:
            num_fields = len(self.fields)

        else:
            dimensions = self.meta_data.dimensions()
            num_fields = dimensions[0]

        return num_fields

    def field(self, key, repetition=0, all=False):
        """ Get data for specific field in table.

        In the case of GROUP fields, the key can include the full location for disambiguation,
        (e.g. *key* = 'GROUP_1, GROUP_0, field_name'). See `info` method for full locations of all
        fields.

        Parameters
        ----------
        key : str, unicode, int or slice
            Selection for desired field. May be an integer or slice specifying which field(s)' data
            to select,  similar to ``list`` or ``tuple`` indexing functionality. May be a string
            containing the name of a field to search for.
        repetition : int, optional
            If there are multiple fields with the same name, specifies a zero-based repetition count
            to return. Defaults to 0.
        all : bool, optional
            If there are multiple fields with the same name, setting to True indicates that
            all fields should be returned in a ``list``. If set, and no match is found
            then an empty list will be returned. Defaults to False.

        Returns
        -------
        PDS_ndarray or PDS_marray
            The data for the field(s).

        Raises
        ------
        IndexError
            Raised if *key* is a larger integer than there are fields in the table.
        ValueError
            Raised if *key* is a name that does not match any field.

        Examples
        --------
            See :func:`TableStructure.__getitem__` method examples.
        """

        return_fields = []

        # Search by index or slice
        if isinstance(key, six.integer_types) or isinstance(key, slice):
            return self.fields[key]

        # Search by name (full or partial)
        for field in self.fields:

            if field.meta_data.full_name() == key:
                return_fields.append(field)

            elif field.meta_data['name'] == key:
                return_fields.append(field)

        # Return result
        if len(return_fields) > repetition and not all:
            return return_fields[repetition]

        elif all:
            return return_fields

        if repetition > 0:
            raise ValueError("Field '{0}' (repetition {1}) not found.".format(key, repetition))
        else:
            raise ValueError("Field '{0}' not found.".format(key))

    @threaded_cached_property
    def data(self):
        """ All data in the PDS4 table data structure.

        This property is implemented as a thread-safe cacheable attribute. Once it is run
        for the first time, it replaces itself with an attribute having the exact
        data that was originally returned.

        Unlike normal properties, this property/attribute is settable without a __set__ method.
        To never run the read-in routine inside this property, you need to manually create the
        the ``.data`` attribute prior to ever invoking this method (or pass in the data to the
        constructor on object instantiation, which does this for you).

        Returns
        -------
        PDS_ndarray or PDS_marray
            A structured array (either effectively np.ndarray or np.ma.MaskedArray) representing all the
            fields in this table.
        """

        super(TableStructure, self).data()

        from .read_tables import read_table_data
        read_table_data(self, no_scale=self._no_scale, decode_strings=self._decode_strings, masked=self._masked)

        return self.data

    @property
    def fields(self):
        """
        Returns
        -------
        list[PDS_ndarray or PDS_marray]
            All the fields in this table.
        """

        return [self.data[name] for name in self.data.dtype.names]

    def set_field(self, data, meta_data):
        """ Set a field in the table.

        Notes
        -----
        Prior to calling this method, ``self.data`` must be set to a structured ``ndarray`` that will be
        used to store each field. See `TableStructure.from_fields`.

        Parameters
        ----------
        data : array_like
            Data for the field to be added.
        meta_data : Meta_Field
            Meta data of the field to be added.

        Returns
        -------
        None
        """

        if not self.data_loaded:
            raise RuntimeError('Unable to add field: backing data structure has not been initialized.')

        self.data.set_field(data, meta_data)

    def as_masked(self):
        """ Obtain a new TableStructure, where numeric fields with Special_Constants are masked.

        Notes
        -----
        The returned Structure may not be easily converted back to unmasked. However, the original
        Structure can continue to be used to access the unmasked data.

        Returns
        -------
        TableStructure
            A new structure, where numeric fields with Special_Constants are masked. The data, labels and
            meta data are all effectively views, no copies are made.
        """

        kwargs = {'structure_meta_data': self.meta_data,
                  'structure_label': self.label, 'full_label': self.full_label,
                  'parent_filename': self.parent_filename, 'structure_id': self.id}

        # If data is already loaded, create a view of the TableStructure where the data is masked
        if self.data_loaded:

            table_structure = self.from_fields(fields=self.fields, no_scale=True, decode_strings=False,
                                               masked=True, copy=False, structure_data=self.data, **kwargs)

        # If the data has not been loaded, create a view of TableStructure that indicates to mask data
        # when the attempt to access it is made later
        else:
            table_structure = self.__class__(**kwargs)
            table_structure._no_scale = self._no_scale
            table_structure._decode_strings = self._decode_strings
            table_structure._masked = True

        return table_structure


class Meta_TableStructure(Meta_Structure):
    """ Meta data about a PDS4 table data structure.

    Meta data stored in this class is accessed in ``dict``-like fashion.  Stores meta data about all forms
    of Table (e.g. Table_Character, Table_Binary, and Table_Delimited). Normally this meta data originates
    from the label (e.g., if this is an Table_Character then everything from the opening tag of
    Table_Character to its closing tag will be stored in this object), via the `from_label` method.

    Inherits all Attributes, Parameters and Properties from `Meta_Structure`.

    Attributes
    ----------
    record : OrderedDict
        Convenience attribute for the Record_* portion of this table's meta data.
    type : str or unicode
        Type of table. One of 'Character', 'Binary', or 'Delimited'.

    Examples
    --------

    Supposing the following Table definition from a label::

        <Table_Binary>
          <local_identifier>data_Integration</local_identifier>
          ....
          <Record_Binary>
            <fields>9</fields>
            <groups>0</groups>
            <record_length unit="byte">65</record_length>
            <Field_Binary>
              <name>TIMESTAMP</name>
              ...
           ...
        ...
        </Table_Binary>

    >>> meta_table = Meta_TableStructure.from_label(structure_xml, full_label)

    >>> print(meta_table['local_identifier'])
    data_Integration

    >>> print(meta_table['Record_Binary']['record_length']
    65
    """

    def __init__(self, *args, **kwds):

        super(Meta_TableStructure, self).__init__(*args, **kwds)

        # Type of table (Character, Binary, Delimited)
        self.type = None

        # Record_* (Character, Binary, Delimited) of the table
        self.record = None

        # Contains the Meta_SpectralCharacteristics for this Table structure, if it exists in the label
        self.spectral_characteristics = None

    @classmethod
    def from_label(cls, xml_table, full_label=None):
        """ Create a Meta_TableStructure from the XML portion describing the Table structure.

        Parameters
        ----------
        xml_table : Label or ElementTree Element
            Portion of label that defines the Table data structure.
        full_label : Label or ElementTree Element, optional
            The entire label from which *xml_table* originated.

        Returns
        -------
        Meta_TableStructure
            Instance containing meta data about the table structure, as taken from the XML label.

        Raises
        ------
        PDS4StandardsException
            Raised if required meta data is absent.
        """

        obj = cls()
        obj._load_keys_from_xml(xml_table)

        # Store record meta data with a variable name that is independent of the table-type
        record_str = [elem.tag for elem in xml_table if 'Record_' in elem.tag][0]
        obj.type = record_str.split('_')[-1]
        obj.record = obj[record_str]

        # Ensure required keys for delimited tables exist
        if 'delimited' in obj.type.lower():

            # Ensure required keys for table exist
            keys_must_exist = ['offset', 'records', 'record_delimiter', 'field_delimiter', record_str]
            obj._check_keys_exist(keys_must_exist)

            # Ensure required keys for table's record exist
            keys_must_exist = ['fields', 'groups']
            obj._check_keys_exist(keys_must_exist, sub_element=record_str)

        # Ensure required keys for fixed-width tables exist
        else:

            # Ensure required keys for table exist
            keys_must_exist = ['offset', 'records', record_str]
            obj._check_keys_exist(keys_must_exist)

            # Ensure required keys for table's record exist
            keys_must_exist = ['fields', 'groups', 'record_length']
            obj._check_keys_exist(keys_must_exist, sub_element=record_str)

        # Add Meta_SpectralCharacteristics if they exist in the label
        if ('local_identifier' in obj) and (full_label is not None):

            local_identifier = six.text_type(obj['local_identifier'])

            try:
                obj.spectral_characteristics = Meta_SpectralCharacteristics.from_full_label(full_label, local_identifier)
            except (KeyError, PDS4StandardsException):
                pass

        return obj

    def dimensions(self):
        """ Obtains the number of fields and records for the table.

        Count does not include Group_Fields, but includes any non-group fields with-in them.

        Returns
        -------
        list
            Dimensions of the table, i.e., the number of fields and records, respectively.
        """

        normal_fields = sum(dict_extract(self.record, 'fields'))
        uni_sampled = 1 if ('Uniformly_Sampled' in self) else 0

        fields = normal_fields + uni_sampled
        records = self['records']

        return [fields, records]

    def is_fixed_width(self):
        """
        Returns
        -------
        bool
            True if the table is fixed-width (Table_Character and Table_Binary), false otherwise.
        """

        type = self.type.lower()

        if ('character' in type) or ('binary' in type):
            return True

        return False

    def is_delimited(self):
        """
        Returns
        -------
        bool
            True if the table is delimited (Table_Delimited), false otherwise.
        """

        if 'delimited' in self.type.lower():
            return True

        return False


class TableManifest(collections_abc.Sequence):
    """ Stores a single table's Meta_Fields and Meta_Groups

    The manifest is a representation the table, with fields and groups in the same order as they physically
    appear in the label, created by adding the appropriate Meta_Field and Meta_Group structures.

    The manifest is normally initialized from the label portion describing the Table, via `from_label`.

    Parameters
    ----------
    items : list[Meta_Field or Meta_Group], optional
        A list of Meta_Fields or Meta_Groups describing the Fields and Groups in this TableManifest.
    table_type : str or unicode, optional
        The type of table. One of
    table_label : Label or ElementTree Element, optional
        Portion of label that defines the PDS4 table data structure.
    """

    def __init__(self, items=None, table_type=None, table_label=None):

        self._struct = [] if (items is None) else items
        self._table_type = table_type
        self._table_label = table_label

        super(TableManifest, self).__init__()

    def __getitem__(self, key):
        """
        Parameters
        ----------
        key : int or slice
            Index of requested field or group.

        Returns
        -------
        Meta_Field or Meta_Group
            Matched field or group meta data.
        """
        return self._struct[key]

    def __len__(self):
        """
        Returns
        -------
        int
            Total number of fields and groups in the table.
        """
        return len(self._struct)

    @classmethod
    def from_label(cls, table_label):
        """ Create a TableManifest from the XML portion describing the Table structure.

        Parameters
        ----------
        table_label : Label or ElementTree Element
            Portion of label that defines the PDS4 table data structure.

        Returns
        -------
        TableManifest
            Instance containing all appropriate Meta_Field's and Meta_Group's.
        """

        # Find the <Record_*> and set the table type (e.g. Character, Binary or Delimited)
        record_str = [elem.tag for elem in table_label if 'Record_' in elem.tag][0]
        record_xml = table_label.find(record_str)
        table_type = record_str.split('_')[-1]

        obj = cls(table_type=table_type, table_label=table_label)

        # Add Uniformly_Sampled fields to the manifest
        obj._add_uniformly_sampled(table_label)

        # Add all fields and groups in <Record_*> to the manifest
        obj._add_fields_and_groups(record_xml)

        # Set group names for all groups
        obj._create_group_names()

        # Set location list for all fields and groups
        obj._create_full_locations()

        # Perform basic sanity and basic validation checking on the table
        obj._validate_table(record_xml)

        return obj

    @property
    def num_items(self):
        """
        Returns
        -------
        int
            Total number of fields and groups in the table manifest.
        """
        return len(self)

    @property
    def num_records(self):

        if self._table_label is not None:
            return int(self._table_label.findtext('records'))

        return None

    def fields(self, skip_uniformly_sampled=False):
        """ Obtain all fields in the table manifest.

        Parameters
        ----------
        skip_uniformly_sampled : bool, optional
            If True, uniformly sampled fields not added to the returned list. Defaults to False.

        Returns
        -------
        list[Meta_Field]
            All fields in the table manifest.
        """
        return [item for item in self
                if item.is_field() and
                (not skip_uniformly_sampled or (item not in self.uniformly_sampled_fields()))]

    def uniformly_sampled_fields(self):
        """
        Returns
        -------
        list[Meta_FieldUniformlySampled]
            All Uniformly Sampled fields in the table manifest.
        """
        return [item for item in self if isinstance(item, Meta_FieldUniformlySampled)]

    def groups(self):
        """
        Returns
        -------
        list[Meta_Group]
            All groups in the table manifest.
        """
        return [item for item in self if item.is_group()]

    def get_field_by_full_name(self, field_full_name):
        """ Returns field(s) matched by full name.

        In the case of GROUP fields, the full name will include the full location for disambiguation,
        (e.g. field_full_name = 'GROUP_1, GROUP_0, field_name'). The full location includes the names of
        the groups necessary to reach this field.

        Parameters
        ----------
        field_full_name : str or unicode
            The full name of the field(s) to search for.

        Returns
        -------
        list[Meta_Field]
            List of matched fields.
        """
        matching_fields = [item for item in self._struct if item.full_name() == field_full_name]

        return matching_fields

    def get_children_by_idx(self, parent_idx, direct_only=False, return_idx=False):
        """ Obtains the child items (Meta_Fields and Meta_Groups) of the *parent_idx* item.

        Child items of a Group field are other Fields and Groups inside said Group field,
        and the children of those groups, etc.

        Parameters
        ----------
        parent_idx : int
            The index (in this TableManifest) of the Meta_Group whose children to find.
            A value of -1 indicates to find all items in the entire manifest.
        direct_only : bool, optional
            If True, only the immediate children of the *parent_idx* element are returned. Defaults to False.
        return_idx : bool, optional
            If True, changes the return type to a ``list`` containing the indicies (in this TableManifest)
            of the matched children. Defaults to False.

        Returns
        -------
        TableManifest
            A new table manifest containing only the matched children.
        """

        if return_idx:
            children = []
        else:
            children = TableManifest()

        if parent_idx == -1:
            parent_item_group_lvl = 0

        else:
            parent_item_group_lvl = self._struct[parent_idx].group_level + 1

        for i in range(parent_idx + 1, self.num_items):
            cur_item = self._struct[i]

            if cur_item.group_level >= parent_item_group_lvl:

                if cur_item.group_level == parent_item_group_lvl or not direct_only:
                    if return_idx:
                        children.append(i)
                    else:
                        children._append(cur_item)

            else:
                break

        return children

    def get_parent_by_idx(self, child_idx, return_idx=False):
        """ Obtains the parent Meta_Group of the child item given by *child_idx*.

        Parameters
        ----------
        child_idx : int
            The index (in this TableManifest) of the Meta_Field or Meta_Group whose parent to find.
        return_idx : bool, optional
            If True, changes the return type to an ``int``, which is the index (in this TableManifest) of the
            parent Meta_Group instead of the group itself. Returns -1 if a parent was not found. Defaults to
            False.

        Returns
        -------
        Meta_Group or None
            The parent of the specified child, or None if a parent was not found.
        """
        child_item = self._struct[child_idx]
        child_group_level = child_item.group_level

        for i in range(child_idx - 1, -1, -1):
            cur_item = self._struct[i]

            if (cur_item.group_level + 1) == child_group_level and cur_item.is_group():

                if return_idx:
                    return i
                else:
                    return cur_item

        if return_idx:
            return -1

        return None

    def get_parents_by_idx(self, child_idx, return_idx=False):
        """ Obtains all Meta_Group parents of the child item given by *child_idx*.

        Parameters
        ----------
        child_idx : int
            The index (in this TableManifest) of the Meta_Field or Meta_Group whose parent to find.
        return_idx : bool, optional
            If True, changes the return type to a list of ``int``'s, each of which is an index (in this
            TableManifest) of the parent Meta_Group instead of the group itself. A value of -1 will be present
            in the list if no parent is found. Defaults to False.

        Returns
        -------
        list[Meta_Group]
            The parents of the specified child, or empty list if no parents were not found.
        """

        child_item = self._struct[child_idx]
        parent_idx = child_idx

        parent_groups = []

        # Obtain values for all parents of child
        for j in range(0, child_item.group_level):

            parent_idx = self.get_parent_by_idx(parent_idx, return_idx=True)

            parent_or_idx = parent_idx if return_idx else self[parent_idx]
            parent_groups.append(parent_or_idx)

        return parent_groups

    def get_field_offset(self, field_idx, parent_idx=None):
        """ Obtains the number of data values between *parent_idx* and *field_idx* in a single record.

        Each value in a record is a single field value, or a single repetition of a field value. If all
        the data values for all fields in a single record were combined into an array, then data_array[offset]
        (with the default *parent_idx*) would select that field's value (or the value of its first
        repetition, for fields inside groups).

        Parameters
        ----------
        field_idx : int
            The index (in this TableManifest) of the Meta_Field whose offset to find.
        parent_idx : int, optional
            The parent index (index of one of the group fields that *field_idx* is inside of), from which
            to calculate the offset to *field_idx*. If None, calculates the offset from the beginning of the
            record. Defaults to None.

        Returns
        -------
        int
            The number of values, where each repetition of any field also counts as a separate value, that
            are between *parent_idx* and *field_idx* (inclusive).
        """

        offset_num = 0
        field = self._struct[field_idx]

        # Calculate the offset from beginning of record unless otherwise requested
        if parent_idx is None:
            parent_idx = -1

        # Iterate over every child of `parent_idx` until we reach the `field`
        for child_item in self.get_children_by_idx(parent_idx, direct_only=True):

            if child_item is field:
                break

            elif child_item.is_field():
                offset_num += 1

            elif child_item.is_group():

                full_index = self.index(child_item)
                offset_add = self.get_field_offset(field_idx, parent_idx=full_index)

                if field in self.get_children_by_idx(full_index):
                    offset_num += offset_add
                    break

                else:
                    offset_num += offset_add * child_item['repetitions']

        return offset_num

    def get_field_skip_factors(self, field_idx, parent_idxs=None):
        """ Obtains the number of data values between each repetition of *field_idx* for every parent group.

        Each value in a record is a single field value, or a single repetition of a field value. If each
        skip factor were multiplied by the max number of repetitions for that group, and the results were
        added together then that skip value would represent the number of data values between the first
        value in the field and the last value in the field.

        Parameters
        ----------
        field_idx : int
            The index (in this TableManifest) of the Meta_Field whose offset to find.
        parent_idxs : list[int], optional
            The parent indexes (indexes of group fields that *field_idx* is inside of) for which to
            calculate the skip factors. If None, selects the parent indexes for all groups that *field_idx*
            is inside of. Defaults to None.

        Returns
        -------
        list[int]
            Each item in the list is the number of values, where each repetition of any field also counts
            as a separate value, between each repetition of the field for that group. The values are
            in reverse order from *parent_idxs*.
        """

        skip_factors = []
        field = self._struct[field_idx]

        # Calculate skip factors for all groups that `field` is unless requested otherwise
        if parent_idxs is None:
            item_idx = self.index(field)
            parent_idxs = self.get_parents_by_idx(item_idx, return_idx=True)

        # Iterate over every group
        for parent_idx in reversed(parent_idxs):

            skip_factor = 0

            # For each group that `field` is inside of, find the amount of other fields and groups; this
            # is how many other values will need to be skipped until we reach `field` on the next repetition.
            for child_item in self.get_children_by_idx(parent_idx, direct_only=True):

                if (child_item is not field) and child_item.is_field():
                    skip_factor += 1

                elif child_item.is_group():

                    child_idx = [self.index(child_item)]
                    skip_factor += self.get_field_skip_factors(field_idx, parent_idxs=child_idx)[0] \
                                   * child_item['repetitions']

            skip_factors.append(skip_factor)

        return skip_factors

    def _insert(self, key, field_or_group):
        """ Inserts an item (Meta_Field or Meta_Group) into the manifest.

        Parameters
        ----------
        key : int
            The key (index) the item will have in this TableManifest.
        field_or_group : Meta_Field or Meta_Group
            The field or group to insert.

        Returns
        -------
        None
        """

        self._struct.insert(key, field_or_group)

    def _append(self, field_or_group):
        """ Appends an item (Meta_Field or Meta_Group) at the end of the manifest.

        Parameters
        ----------
        field_or_group : Meta_Field or Meta_Group
            The field or group to append.

        Returns
        -------
        None
        """

        self._struct.append(field_or_group)

    def _add_fields_and_groups(self, xml_parent, group_level=0):
        """
        Adds all <Field_*>s and <Group_Field_*>s which are direct children of xml_parent to the
        TableManifest, and then recursively all children of the <Group_Field_*>s.

        The end result, when this is called on the <Record_*> of a table, is to add all Fields
        and all Groups defined inside <Record_*> into the manifest.

        Parameters
        ----------
        xml_parent : Label or ElementTree Element
            An XML element containing <Field_*> or <Group_Field_*> tags as children.
        group_level : int, optional
            The depth the current elements being added are nested from the <Record_*>. Defaults to 0,
            which means direct children. (Only non-zero for children of Group fields.)

        Returns
        -------
        None
        """
        field_tag = 'Field_' + self._table_type
        group_tag = 'Group_Field_' + self._table_type

        # Work around ElementTree not having ability to findall based on multiple conditions
        # while preserving order
        elements_xml = [element for element in xml_parent
                        if element.tag == field_tag or
                        element.tag == group_tag]

        # Iterate over all fields and groups
        for element in elements_xml:

            # Append Fields to Data
            if element.tag == field_tag:

                if self._table_type == 'Character':
                    field_type = Meta_FieldCharacter
                elif self._table_type == 'Binary':
                    field_type = Meta_FieldBinary
                elif self._table_type == 'Delimited':
                    field_type = Meta_FieldDelimited
                else:
                    raise ValueError('Unknown table type: ' + self._table_type)

                field = field_type.from_label(element)
                self._append(field)
                field_idx = self.index(field)

                field.group_level = group_level
                field.shape = tuple(self._get_item_shape(field_idx))

            # Append Groups (and recursively sub-Fields and sub-Groups) to Data
            else:

                group = Meta_Group.from_label(element)
                self._append(group)

                group.group_level = group_level
                self._add_fields_and_groups(element, group_level + 1)

    def _add_uniformly_sampled(self, table_xml):
        """ Add <Uniformly_Sampled> fields into the manifest.

        Parameters
        ----------
        table_xml : Label or ElementTree Element
            Portion of label that defines the PDS4 table data structure.

        Returns
        -------
        None
        """

        for element in table_xml.findall('Uniformly_Sampled'):

            field = Meta_FieldUniformlySampled.from_label(element)

            self._append(field)
            field_idx = self.index(field)

            field.group_level = 0
            field.shape = tuple(self._get_item_shape(field_idx))

    def _create_group_names(self, group_level=0):
        """ Creates a name for each Meta_Group in the manifest that was not given one in the label.

        PDS4 Standards make group field names optional. This method creates names where necessary, with the
        format 'GROUP_n', where n is an integer from 0 to infinity (depending on the number of groups).
        In groups that are nested inside other groups, n will start from 0 regardless of the name of the
        parent group.

        Parameters
        ----------
        group_level : int, optional
            The depth the current group being named is nested from the <Record_*>. Defaults to 0,
            which means direct child.

        Returns
        -------
        None
        """
        group_indicies = [i for i, item in enumerate(self._struct)
                          if item.is_group()
                          if item.group_level == group_level]

        if not group_indicies:
            return

        prev_parent = -2
        counter = 0

        for group_idx in group_indicies:

            group = self._struct[group_idx]
            parent_idx = self.get_parent_by_idx(group_idx, return_idx=True)

            if parent_idx == prev_parent:
                counter += 1
            else:
                counter = 0

            if 'name' not in group:
                group['name'] = 'GROUP_' + six.text_type(counter)

            prev_parent = parent_idx

        self._create_group_names(group_level + 1)

    def _create_full_locations(self):
        """ Sets the correct full locations for all Meta_Fields and Meta_Groups in the manifest.

        A full location is a ``list`` of ``dict``s, where each ``dict`` has a single key and a single
        value. All together these keys and values indicate the full path to the table element from the
        beginning of the <Record_*>. Available keys are: 'field', 'group', and 'overlap'. A field key
        has a value corresponding to the name of a (non-group) field. A group key has a value corresponding
        to the name of a group field. An overlap has a value corresponding to the overlap number of the
        preceding field or group (zero-based index).

        Returns
        -------
        None

        Examples
        --------

        Suppose the following Example Label Outline::

            Table_Binary: Observations
                Field: order
                Field: wavelength           (1)
                Group: unnamed
                        Field: pos_vector   (2)
                Group: unnamed
                    Group: unnamed
                        Field: pos_vector
                        Field: pos_vector   (3)

        The full locations of the fields labeled above in parenthesis are as follows:

        (1) [{'field': 'wavelength'}]

        (2) [{'group': 'GROUP_0'},
             {'field': 'pos_vector'}]

        (3) [{'group': 'GROUP_1'},
             {'group': 'GROUP_0'},
             {'field': 'pos_vector'},
             {'overlap': '1'}]
        """

        for i, item in enumerate(self._struct):

            full_location = []

            # Begin by adding item name to full location
            idx = i

            type = 'group' if item.is_group() else 'field'
            full_location.insert(0, {type: item['name']})

            # Find _struct indicies of items having the same name and group location as current item
            identical_idxs = self._get_overlapping_item_idxs(i)

            # Add overlap count for groups and fields that have the same name and same group location
            # (otherwise these groups and fields would have exactly the same full name)
            if len(identical_idxs) >= 2:
                full_location.append({'overlap': identical_idxs.index(i)})

            parent_idx = self.get_parent_by_idx(idx, return_idx=True)

            # Add field parent group's full location
            # (this should already contain locations of all prior groups)
            if parent_idx != -1:
                group = self._struct[parent_idx]

                # Add parent group's location
                group_full_location = [location.copy() for location in group.full_location]
                group_full_location.extend(full_location)
                full_location = group_full_location

            item.full_location = full_location

    def _get_overlapping_item_idxs(self, item_idx):
        """
        Overlapping items are those Meta_Field's and Meta_Group's that have the same type (i.e., either
        field or group), name, and group location as `table_manifest[item_idx]`. The simplest case is two
        fields with the same name in a table without groups. To disambiguate these fields there is special
        handling, but first we need to find them, which is the purpose of this method.

        Parameters
        ----------
        item_idx : int
            The index (in this TableManifest) of the Meta_Field or Meta_Group whose overlapping items
            to find.

        Returns
        -------
        list[int]
            Indexes (in this TableManifest) of the Meta_Field's or Meta_Group's that overlap with `item_idx`.
        """
        item = self._struct[item_idx]
        item_parent_idx = self.get_parent_by_idx(item_idx, return_idx=True)

        overlapping_item_idxs = []

        # Determine if we're looking for overlapping fields or overlapping groups
        find_fields = True
        if item.is_group():
            find_fields = False

        child_idxs = self.get_children_by_idx(item_parent_idx, direct_only=True, return_idx=True)

        for idx in child_idxs:

            if self._struct[idx]['name'] == item['name']:

                if (find_fields and not self._struct[idx].is_group()) or (
                   not find_fields and self._struct[idx].is_group()):

                    overlapping_item_idxs.append(idx)

        return overlapping_item_idxs

    def _get_item_shape(self, item_idx):
        """ Obtain dimensions of item given by *item_idx*.

        Normally this would be used only on Meta_Field items, to obtain the dimensions of the array needed
        for that field's data.

        Parameters
        ----------
        item_idx : int
            The index (in this TableManifest) of the Meta_Field or Meta_Group whose shape to obtain.

        Returns
        -------
        list[int]
            Dimensions of the item. For fields not inside groups, this will be equivalent to the number of
            records.
        """

        item_shape = [self.num_records]

        for parent_group in self.get_parents_by_idx(item_idx):
            item_shape.insert(1, parent_group['repetitions'])

        return item_shape

    def _validate_table(self, record_xml):
        """
        Performs basic sanity checks on the table and basic verification of some PDS4 standards
        not currently tested by the schema and schematron.

        Checks performed:
            1) Ensure <fields> matches number of Field_* (including for nested fields)
            2) Ensure <groups> matches number of Group_Field_* (including for nested groups)
            3) Ensure the <format> of each field, if given, is valid according to the PDS4 standards
            4) Ensure that <group_repetitions> mod <group_length> equals zero for all group fields

        If any of the optional checks (1-3) fail, a warning is output. It is normally safe to continue.
        If an unsafe check fails, an exception is raised.

        Parameters
        ----------
        record_xml : Label or ElementTree Element
            The Record_* portion of the label for this table.

        Returns
        -------
        None

        Raises
        ------
        PDS4StandardsException
           Raised if group_repetitions do not evenly divide into group_length for all group fields.
        """

        # Check that number of fields and groups claimed matches number of <Field_*> and <Group_Field_*>
        num_rec_fields = int(record_xml.findtext('fields'))
        num_rec_groups = int(record_xml.findtext('groups'))

        groups = [group for group in self.groups() if group.group_level == 0]
        fields = [field for field in self.fields(skip_uniformly_sampled=True) if field.group_level == 0]

        fields_mismatch_warn = '<fields> value does not match number of <Field_{0}> in'.format(self._table_type)
        groups_mismatch_warn = '<groups> value does not match number of <Group_Field_{0}> in'.format(self._table_type)

        if len(fields) != num_rec_fields:
            logger.warning('{0} Record_{1}.'.format(fields_mismatch_warn, self._table_type))

        if len(groups) != num_rec_groups:
            logger.warning('{0} Record_{1}.'.format(groups_mismatch_warn, self._table_type))

        for i, item in enumerate(self._struct):

            full_location_warn = "'{0}' (full location: '{1}')".format(item['name'], item.full_name(' -> '))

            if item.is_group():

                # Check number of fields and groups matching in nested groups
                children = self.get_children_by_idx(i, direct_only=True)

                groups = [child for child in children if child.is_group()]
                fields = [child for child in children if not child.is_group()]

                # For fixed-width tables, check that group_length is evenly divisible by group_repetitions
                if self._table_type != 'Delimited':

                    if len(fields) != item['fields']:
                        logger.warning(fields_mismatch_warn + ' group ' + full_location_warn)

                    if len(groups) != item['groups']:
                        logger.warning(groups_mismatch_warn + ' group ' + full_location_warn)

                    if item['length'] % item['repetitions'] != 0:
                        raise PDS4StandardsException("Group length '{0}' must be evenly divisible by the "
                                                     "number of repetitions '{1}' for group {2}"
                                                     .format(item['length'], item['repetitions'],
                                                             full_location_warn))

            elif 'format' in item:

                # Ensure field_format requirements
                valid_field_format = re.compile(r'^%([\+,-])?([0-9]+)(\.([0-9]+))?([doxfeEs])$')

                if not valid_field_format.match(item['format']):
                    logger.warning("field_format '{0}' does not conform to PDS4 standards for field {1} "
                                   .format(item['format'], full_location_warn))

                else:

                    is_numeric = {'ASCII_Real': True,
                                  'ASCII_Integer': True,
                                  'ASCII_NonNegative_Integer': True,
                                  'ASCII_Numeric_Base2': True,
                                  'ASCII_Numeric_Base8': True,
                                  'ASCII_Numeric_Base16': True}.get(item['data_type'], False)

                    sub_exp = valid_field_format.search(item['format']).groups()

                    plus_minus = sub_exp[0]
                    width = sub_exp[1]
                    precision = sub_exp[3]
                    specifier = sub_exp[4]

                    if plus_minus is not None:

                        if plus_minus == '+' and not is_numeric:
                            logger.warning("field_format '{0}' may not have '+' for a numeric data_type '{1}' for "
                                           "field {2}".format(item['format'], item['data_type'], full_location_warn))

                        elif plus_minus == '-' and is_numeric:
                            logger.warning("field_format '{0}' may not have '-' for a non-numeric data_type '{1}' for "
                                           "field {2}".format(item['format'], item['data_type'], full_location_warn))

                    if self._table_type == 'Character' and int(width) != item['length']:
                        logger.warning("in Table_Character field_format '{0}' width must be equal to field_length "
                                       "'{1}' for field {2}".format(item['format'], item['length'], full_location_warn))

                    if precision is not None and specifier == 's' and int(width) != int(precision):
                        logger.warning("field_format '{0}' precision must be equal to width '{1}' for a string format "
                                       "for field {2}".format(item['format'], width, full_location_warn))


@six.add_metaclass(abc.ABCMeta)
class Meta_TableElement(Meta_Class):
    """ Stores meta data about any table element.

    Table elements are Fields and Group fields. Subclassed by Meta_Field, Meta_Group and their derivatives.

    Meta data stored in this class is accessed in ``dict``-like fashion.  See docstring for `Meta_Class`
    for additional documentation.

    Parameters
    ----------
    (same as for `Meta_Class` and ``OrderedDict``)

    *args
        Variable length argument list.
    **kwargs
        Arbitrary keyword arguments.

    Attributes
    ----------
    full_location : list[dict]
        See docstring for ``TableManifest._create_full_locations``.
    group_level : int
        The depth the element is nested from the <Record_*>. 0 means direct child.
    """

    def __init__(self, *args, **kwds):
        super(Meta_TableElement, self).__init__(*args, **kwds)

        self.full_location = None
        self.group_level = 0

    @abc.abstractmethod
    def from_label(cls, element_xml):
        """ Initializes the meta data from an XML description of the element.

        Parameters
        ----------
        element_xml : Label or ElementTree Element
            Portion of the label describing this element.

        Returns
        -------
        Meta_TableElement
            Instance containing meta data from *element_xml*.
        """

    def full_name(self, separator=', ', skip_parents=False):
        """ The full name of the element.

        The full name always includes an overlap disambiguator, to resolve two elements in the same
        location with the same name. Normally it also includes the name of any parent groups necessary
        to reach this element from the beginning of the record description.

        Parameters
        ----------
        separator : str or unicode, optional
            Used as the string separating each parent group and the name of the element. Defaults to ', '.
        skip_parents : bool, optional
            If True, parent groups of the element are excluded from the full name. Defaults to False.

        Returns
        -------
        str or unicode
            The name, including overlap disambiguator and parent groups if enabled, of the element.

        Examples
        --------

        Suppose the following Example Label Outline::

            Table_Binary: Observations
                Field: order
                Field: wavelength           (1)
                Group: unnamed
                        Field: pos_vector   (2)
                Group: unnamed
                    Group: example_group
                        Field: pos_vector
                        Field: pos_vector   (3)

        The full name of each element, with the default separator, is:

        (1) wavelength
        (2) GROUP_0, pos_vector
        (3) GROUP_1, example_group, pos_vector [1]

        Enabling skip_parents for element (3) would result in 'pos_vector [1]', which includes the
        overlap disambiguator, but excludes all parent groups.
        """

        # Attempt to begin extraction of name from full location
        full_name = None if (self.full_location is None) else ''

        # If full location is not set (should only be the case if this a fake field, for all fields
        # read from a real table full location should always be set), try to extract a name from
        # the name attribute
        if (full_name is None) and ('name' in self):
            full_name = self['name']

        # Build name by looping over the full location
        else:

            # If we are skipping outputting parent groups and fields, then find
            # the last index of a field or group in `self.full_location`
            if skip_parents:

                start_idx = None

                for i in range(len(self.full_location) - 1, -1, -1):

                    key = list(self.full_location[i].keys())[0]

                    if key in ['group', 'field']:
                        start_idx = i
                        break

            else:
                start_idx = 0

            # Location from which to start building the full name
            location = self.full_location[start_idx:]

            for i in range(0, len(location)):

                key = list(location[i].keys())[0]
                value = six.text_type(list(location[i].values())[0])

                # Add key/value to name
                if key == 'overlap':
                    full_name += ' [{0}]'.format(value)

                else:
                    full_name += value

                # Insert the separator where necessary (following group and field)
                if i < len(location) - 1:

                    next_key = list(location[i+1].keys())[0]

                    if next_key in ['group', 'field']:
                        full_name += separator

        return full_name

    def is_field(self):
        """
        Returns
        -------
        bool
            True if this element is a Field (i.e. Field_*), false otherwise.
        """

        return isinstance(self, Meta_Field)

    def is_group(self):
        """
        Returns
        -------
        bool
            True if this element is a Group field (i.e. Group_Field_*), false otherwise.
        """

        return isinstance(self, Meta_Group)


class Meta_Field(Meta_TableElement):
    r""" Stores meta data about a single <Field_*>.

    Subclassed by `Meta_FieldCharacter`, `Meta_FieldBinary`, `Meta_FieldDelimited` and
    `Meta_FieldUniformlySampled`.

    Inherits ``full_location`` and ``group_level`` attributes from `Meta_TableElement`.

    Attributes
    ----------
    shape : tuple[int]
        The dimensions of the field's data. For fields not inside groups, this will be equivalent to
        the number of records.

    Notes
    -----
    Keys starting with the 'field\_' prefix have this prefix removed.
    All other keys preserve their XML names.

    Examples
    --------

    Supposing the following Field definition from a label::

        <Field_Binary>
          <name>UTC</name>
          <field_location unit="byte">17</field_location>
          <data_type>ASCII_String</data_type>
          <field_length unit="byte">33</field_length>
          <unit>UTC date string</unit>
          <description>Time that the integration began</description>
        </Field_Binary>

    >>> field = Meta_Field.from_label(field_xml)

    >>> print(field['name'])
    UTC

    >>> print(field['length'])
    33

    >>> print(field.keys())
    ['name', 'location', 'data_type', 'length', 'unit', 'description']
    """

    def __init__(self, *args, **kwds):
        super(Meta_Field, self).__init__(*args, **kwds)

        self.shape = None

    @classmethod
    def from_label(cls, field_xml):
        """ Initializes the meta data from an XML description of the Field.

        Parameters
        ----------
        field_xml : Label or ElementTree Element
            Portion of the label describing this Field.

        Returns
        -------
        Meta_Field
            Contains meta data for the field.
        """

        obj = cls()

        obj._load_keys_from_xml(field_xml, tag_modify=('field_', ''))
        obj._check_keys_exist(['name'])

        return obj

    def data_type(self):
        """ Data type of the field.

        Notes
        -----
        All fields, except Uniformly Sampled fields, must specify the data type. Uniformly Sampled fields
        default to ASCII_Real with-in this code.

        Returns
        -------
        PDSdtype
            A PDS4 data type.
        """

        data_type = self.get('data_type', 'ASCII_Real')
        return PDSdtype(data_type)


class Meta_FieldCharacter(Meta_Field):
    """ Stores meta data about a single <Field_Character>.

    Inherits ``shape`` attribute from `Meta_Field`. Inherits ``full_location`` and ``group_level``
    attributes from `Meta_TableElement`.

    See docstring of `Meta_Field` for usage information.
    """

    @classmethod
    def from_label(cls, field_xml):
        """ Initializes the meta data from an XML description of the element.

        Parameters
        ----------
        field_xml : Label or ElementTree Element
            Portion of the label describing this Field.

        Returns
        -------
        Meta_FieldCharacter
            Contains meta data for a Field_Character.
        """

        obj = super(Meta_FieldCharacter, cls).from_label(field_xml)

        keys_must_exist = ['location', 'length', 'data_type']
        obj._check_keys_exist(keys_must_exist)

        return obj


class Meta_FieldBinary(Meta_Field):
    """ Stores meta data about a single <Field_Binary>.

    Inherits ``shape`` attribute from `Meta_Field`. Inherits ``full_location`` and ``group_level``
    attributes from `Meta_TableElement`.

    See docstring of `Meta_Field` for usage information.
    """

    @classmethod
    def from_label(cls, field_xml):
        """ Initializes the meta data from an XML description of the Field.

        Parameters
        ----------
        field_xml : Label or ElementTree Element
            Portion of the label describing this Field.

        Returns
        -------
        Meta_FieldBinary
            Contains meta data for a Field_Binary.
        """

        obj = super(Meta_FieldBinary, cls).from_label(field_xml)

        keys_must_exist = ['location', 'length', 'data_type']
        obj._check_keys_exist(keys_must_exist)

        # Add the bit fields
        # Note: bit fields not currently supported
        # packed_data = field_xml.find('Packed_Data_Fields')
        # if packed_data is not None:
        #
        #     bit_fields = packed_data.findall('Field_Bit')
        #
        #     for bit_field in bit_fields:
        #
        #         bit_field = Meta_FieldBit.from_label(bit_field)
        #         obj.bit_fields.append(bit_field)

        return obj


class Meta_FieldDelimited(Meta_Field):
    """ Stores meta data about a single <Field_Delimited>.

    Inherits ``shape`` attribute from `Meta_Field`. Inherits ``full_location`` and ``group_level``
    attributes from `Meta_TableElement`.

    See docstring of `Meta_Field` for usage information.
    """

    @classmethod
    def from_label(cls, field_xml):
        """ Initializes the meta data from an XML description of the Field.

        Parameters
        ----------
        field_xml : Label or ElementTree Element
            Portion of the label describing this Field.

        Returns
        -------
        Meta_FieldDelimited
            Contains meta data for a Field_Delimited.
        """

        obj = super(Meta_FieldDelimited, cls).from_label(field_xml)

        keys_must_exist = ['data_type']
        obj._check_keys_exist(keys_must_exist)

        return obj


class Meta_FieldUniformlySampled(Meta_Field):
    """ Stores meta data about a single <Uniformly_Sampled>.

    See docstring of `Meta_Field` for usage information.
    """

    @classmethod
    def from_label(cls, uniformly_sampled_xml):
        """ Initializes the meta data from an XML description of the Uniformly_Sampled.

        Parameters
        ----------
        uniformly_sampled_xml : Label or ElementTree Element
            Portion of the label describing this Uniformly Sampled field.

        Returns
        -------
        Meta_FieldUniformlySampled
            Contains meta data for a Uniformly_Sampled field.
        """

        obj = cls()

        obj._load_keys_from_xml(uniformly_sampled_xml, tag_modify=('sampling_parameter_', ''))
        obj.full_location = [{'field': obj['name']}]

        keys_must_exist = ['name', 'interval', 'first_value', 'last_value']
        obj._check_keys_exist(keys_must_exist)

        return obj


class Meta_FieldBit(Meta_Field):
    """ Stores meta data about a single <Field_Bit>. """

    @classmethod
    def from_label(cls, field_bit_xml):
        raise NotImplementedError


class Meta_Group(Meta_TableElement):
    r""" Stores meta data about a single <Group_Field_*>.

    Notes
    -----
    Keys starting with the 'group\_' prefix have this prefix removed.
    All other keys preserve their XML names.

    Examples
    --------

    Supposing the following Group field definition from a label::

        <Group_Field_Binary>
          <repetitions>12</repetitions>
          <fields>1</fields>
          <groups>0</groups>
          <group_location unit="byte">1</group_location>
          <group_length unit="byte">24</group_length>
          <Field_Binary>
            ...
          </Field_Binary>
        </Group_Field_Binary>

    >>> group = Meta_Group.from_label(group_field_xml)

    >>> print(group['repetitions'])
    12

    >>> print(group['location'])
    1

    >>> print(group.keys())
    ['repetitions', 'fields', 'groups', 'location', 'length', 'Field_Binary']
    """

    @classmethod
    def from_label(cls, group_field_xml):
        """ Initializes the meta data from an XML description of the Group_Field.

        Parameters
        ----------
        group_field_xml : Label or ElementTree Element
            Portion of the label describing this group field.

        Returns
        -------
        Meta_Group
            Contains meta data for Group_Field_* fields.
        """

        obj = cls()

        obj._load_keys_from_xml(group_field_xml, tag_modify=('group_', ''))

        keys_must_exist = ['repetitions', 'fields', 'groups']
        if 'Delimited' not in group_field_xml.tag:
            keys_must_exist.extend(['location', 'length'])

        obj._check_keys_exist(keys_must_exist)

        return obj
