from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys

from .general_objects import Structure, Meta_Structure
from .label_objects import Meta_DisplaySettings, Meta_SpectralCharacteristics
from .data_types import apply_scaling_and_value_offset, PDSdtype

from ..utils.exceptions import PDS4StandardsException

from ..extern import six
from ..extern.cached_property import threaded_cached_property


class ArrayStructure(Structure):
    """ Stores a single PDS4 array data structure.

    Contains the array's data, meta data and label portion. All forms of Array
    (e.g. Array, Array_2D, Array_3D_Image, etc) are stored by this class.

    See `Structure`'s and `pds4_read`'s docstrings for attributes, properties and usage instructions
    of this object.

    Inherits all Attributes, Parameters and Properties from `Structure`. Overrides `info`, `data`
    and `from_file` methods to implement them.
    """

    @classmethod
    def from_file(cls, data_filename, structure_label, full_label,
                  lazy_load=False, no_scale=False, decode_strings=None):
        """ Create an array structure from relevant labels and file for the data.

        Parameters
        ----------
        data_filename : str or unicode
            Filename of the data file that contained the data for this array structure.
        structure_label : Label
            The segment of the label describing only this array structure.
        full_label : Label
            The entire label describing the PDS4 product this structure originated from.
        lazy_load : bool, optional
            If True, does not read-in the data of this structure until the first attempt to access it.
            Defaults to False.
        no_scale : bool, optional
            If True, read-in data will not be adjusted according to the offset and scaling factor.
            Defaults to False.
        decode_strings : None, optional
            Has no effect because Arrays may not contain string data. Defaults to None.

        Returns
        -------
        ArrayStructure
            An object representing the PDS4 array structure; contains its label, data and meta data.
        """

        # Create the meta data structure for this array
        meta_array_structure = Meta_ArrayStructure.from_label(structure_label, full_label)

        # Create the data structure for this array
        array_structure = cls(structure_data=None, structure_meta_data=meta_array_structure,
                              structure_label=structure_label, full_label=full_label,
                              parent_filename=data_filename)
        array_structure._no_scale = no_scale

        # Attempt to access the data property such that the data gets read-in (if not on lazy-load)
        if not lazy_load:
            array_structure.data

        return array_structure

    @classmethod
    def from_array(cls, input, no_scale=False, no_bitmask=False, masked=None, **structure_kwargs):
        """ Create an array structure from PDS-compliant data or meta data.

        Parameters
        ----------
        input : PDS_ndarray, PDS_marray or Meta_ArrayStructure
            Either an array containing the data, which must also have a valid PDS4 meta_data attribute
            describing itself, or an instance of valid Meta_ArrayStructure.
        no_scale : bool, optional
            If False, and input is an array of data, then the data will scaled according to the scaling_factor
            and value_offset meta data. If the *input* is meta data only, then the output data type will be
            large enough to store the scaled values. If True, no scaling or data type conversions will be
            done. Defaults to False.
        no_bitmask : bool, optional
            If False, and input is an array of data, then the bitmask indicated in the meta data will be
            applied. If True, the bitmask will not be used. Defaults to False.
        masked : bool or None, optional
            If True, and input is an array of data, then the data will retain any masked values and in
            additional have numeric Special_Constants values masked. If False, any masked values in the input
            array will be unmasked and data assignments will not preserve masked values. If None, masked
            values in the input will be retained only if any are present. Defaults to None.
        structure_kwargs :  dict, optional
            Keywords that are passed directly to the `ArrayStructure` constructor.

        Returns
        -------
        ArrayStructure
            An object representing the PDS4 array structure. The data attribute will contain an array that
            can store *input* values (or does store it, if input is an array of data). Other attributes may
            be specified via *structure_kwargs*.
        """

        from .read_arrays import new_array

        return new_array(input, no_scale=no_scale, no_bitmask=no_bitmask, masked=masked, **structure_kwargs)

    def info(self, abbreviated=False, output=None):
        """ Prints a summary of this data structure.

        Contains the type and dimensions of the Array, and if *abbreviated* is False then
        also outputs the name and number of elements of each axis in the array.

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
        axes_info = '{0} axes, {1}'.format(len(dimensions), ' x '.join(
            six.text_type(dim) for dim in dimensions))

        summary_args = [self.type, id, axes_info]
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
            output.write('Axes for {0}: \n\n'.format(abbreviated_info))

            for axis in self.meta_data.get_axis_arrays():
                output.write('{0} ({1} elements)\n'.format(axis['axis_name'], axis['elements']))

            output.flush()

    @threaded_cached_property
    def data(self):
        """ All data in the PDS4 array data structure.

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
            An array (either effectively np.ndarray or np.ma.MaskedArray) representing all the data in
            this array structure.
        """

        super(ArrayStructure, self).data()

        from .read_arrays import read_array_data
        read_array_data(self, no_scale=self._no_scale, masked=self._masked, memmap=False)

        return self.data

    @threaded_cached_property
    def section(self):
        """ A section of the data in the PDS4 array data structure.

        This property is implemented as a thread-safe cacheable attribute. See docstring of ``.data``
        for more info.

        Returns
        -------
        ArraySection
            An object that allows access to sections of the array without reading the entire array
            into memory.
        """

        from .read_arrays import read_array_data

        # Read-in data unscaled with memory mapping (scaled data is not guaranteed to be memory mapped)
        structure = self.__class__(structure_meta_data=self.meta_data, structure_label=self.label,
                                   full_label=self.full_label, parent_filename=self.parent_filename)

        read_array_data(structure, no_scale=True, masked=self._masked, memmap=True)

        # Return an ArraySection, which will scale the requested portion of the data as needed on access
        return ArraySection(structure, self._no_scale)

    def as_masked(self):
        """ Obtain a view of this ArrayStructure, with numeric Special_Constants masked.

        Notes
        -----
        The returned Structure may not be easily converted back to unmasked. However, the original
        Structure can continue to be used to access the unmasked data.

        Returns
        -------
        ArrayStructure
            A view of this structure, where the data is masked for numeric Special_Constants. The data,
            labels and meta data are all effectively views, no copies are made.
        """

        kwargs = {'structure_meta_data': self.meta_data,
                  'structure_label': self.label, 'full_label': self.full_label,
                  'parent_filename': self.parent_filename, 'structure_id': self.id}

        # If data is already loaded, create a view of the ArrayStructure where the data is masked
        if self.data_loaded:

            array_structure = self.from_array(self.data, no_scale=True, no_bitmask=True, masked=True,
                                              copy=False, structure_data=self.data, **kwargs)

        # If the data has not been loaded, create a view of ArrayStructure that indicates to mask data
        # when the attempt to access it is made later
        else:
            array_structure = self.__class__(**kwargs)
            array_structure._no_scale = self._no_scale
            array_structure._masked = True

        return array_structure


class ArraySection(object):
    """ Stores and allows retrieval of a section of an array.

    Used to extract and scale (if necessary) a portion of a PDS4 array. Usually this would be used for
    an array that is too large to hold entirely in memory.

    Notes
    -----
    We use this instead of memory mapping to access extremely large arrays because the latter does not work
    for scaled arrays in which the scaled data type is different from the data type on disk.

    Parameters
    ----------
    array_structure : ArrayStructure
        A PDS4 array structure. The data attribute in this structure should be memory-mapped.
    no_scale : bool, optional
        If True, returned data will not be adjusted according to the offset and scaling factor.
        Defaults to False.
    """

    def __init__(self, array_structure, no_scale=False):

        self._structure = array_structure
        self._no_scale = no_scale

    def __getitem__(self, idx):
        """ Obtain a portion of the array.

        Parameters
        ----------
        idx : str, slice, array_like
            Standard ``np.ndarray`` indexes, including field name, list of field names, record number or
            slice, or an array-like of record numbers.

        Returns
        -------
        PDS_ndarray, PDS_marray, np.void, np.mvoid, np.record, any np.dtype
            The selected portion of the array.
        """

        # Obtain data for the key (``.data`` should be memory mapped for this structure), and
        # then copy it so that it can be scaled below
        data = self._structure.data[idx].copy()

        # Adjust data values to account for 'scaling_factor' and 'value_offset' as necessary
        if not self._no_scale:
            element_array = self._structure.meta_data['Element_Array']
            special_constants = self._structure.meta_data.get('Special_Constants')
            data = apply_scaling_and_value_offset(data,
                                                  element_array.get('scaling_factor'),
                                                  element_array.get('value_offset'),
                                                  special_constants=special_constants)

        return data


class Meta_ArrayStructure(Meta_Structure):
    """ Meta data about a PDS4 array data structure.

    Meta data stored in this class is accessed in ``dict``-like fashion.  Stores meta data about all forms
    of Array (e.g. Array, Array_2D, Array_3D_Image, etc). Normally this meta data originates from the
    label (e.g., if this is an Array_2D then everything from the opening tag of Array_2D to its closing
    tag will be stored in this object), via the `from_label` method.

    Attributes
    ----------
    display_settings : Meta_DisplaySettings
        Meta data about the Display Settings for this array data structure.
    spectral_characteristics : Meta_SpectralCharacteristics
        Meta data about the Spectral Characteristics for this array data structure.

    Inherits all Attributes, Parameters and Properties from `Meta_Structure`.

    Examples
    --------

    Supposing the following Array definition from a label::

        <Array_3D_Spectrum>
          <local_identifier>data_Primary</local_identifier>
          ...
          <Axis_Array>
            <axis_name>Time</axis_name>
            <elements>21</elements>
            <sequence_number>1</sequence_number>
          </Axis_Array>
          ...
        </Array_3D_Spectrum>

    >>> meta_array = Meta_ArrayStructure.from_label(structure_xml, full_label)

    >>> print(meta_array['local_identifier'])
    data_Primary

    >>> print(meta_array['Axis_Array']['elements']
    21

    """

    def __init__(self, *args, **kwds):
        super(Meta_ArrayStructure, self).__init__(*args, **kwds)

        # Contains the Meta_DisplaySettings and Meta_SpectralCharacteristics for this Array structure,
        # if they exist in the label
        self.display_settings = None
        self.spectral_characteristics = None

    @classmethod
    def from_label(cls, xml_array, full_label=None):
        """ Create a Meta_ArrayStructure from XML originating from a label.

        Parameters
        ----------
        xml_array : Label or ElementTree Element
            Portion of label that defines the Array data structure.
        full_label : Label or ElementTree Element, optional
            The entire label from which *xml_array* originated.

        Returns
        -------
        Meta_ArrayStructure
            Instance containing meta data about the array structure, as taken from the XML label.

        Raises
        ------
        PDS4StandardsException
            Raised if required meta data is absent.
        """

        obj = cls()
        obj._load_keys_from_xml(xml_array)

        # Ensure required keys for Array_* exist
        keys_must_exist = ['offset', 'axes', 'Axis_Array', 'Element_Array']
        obj._check_keys_exist(keys_must_exist)

        # Ensure required keys for Axis_Array(s) exist
        axis_keys_must_exist = ['axis_name', 'elements', 'sequence_number']
        multiple_axes = True if obj.num_axes() > 1 else False
        obj._check_keys_exist(axis_keys_must_exist, sub_element='Axis_Array', is_sequence=multiple_axes)

        # Ensure required keys for Element_Array exist
        obj._check_keys_exist(['data_type'], sub_element='Element_Array')

        # Add the Meta_DisplaySettings and Meta_SpectralCharacteristics if they exist in the label
        if ('local_identifier' in obj) and (full_label is not None):

            local_identifier = six.text_type(obj['local_identifier'])

            try:
                obj.display_settings = Meta_DisplaySettings.from_full_label(full_label, local_identifier)
            except (KeyError, PDS4StandardsException):
                pass

            try:
                obj.spectral_characteristics = Meta_SpectralCharacteristics.from_full_label(full_label, local_identifier)
            except (KeyError, PDS4StandardsException):
                pass

        return obj

    def data_type(self):
        """ Data type of the array elements.

        Returns
        -------
        PDSdtype
            A PDS4 data type.
        """

        return PDSdtype(self['Element_Array']['data_type'])

    def dimensions(self):
        """
        Returns
        -------
        list
            Dimensions of the array.
        """

        dimensions = [axis_array['elements'] for axis_array in self.get_axis_arrays(sort=True)]

        return dimensions

    def num_axes(self):
        """
        Returns
        -------
        int
            Number of axes/dimensions in the array.
        """

        return len(self.get_axis_arrays())

    def get_axis_arrays(self, sort=True):
        """ Convenience method to always obtain Axis_Arrays as a ``list``.

        Parameters
        ----------
        sort : bool, optional
            Sorts returned Axis Arrays by sequence_number if True. Defaults to True.

        Returns
        -------
        list
            List of ``OrderedDict``'s containing meta data about each Axis_Array.
        """

        axis_arrays = self['Axis_Array']

        if isinstance(axis_arrays, (list, tuple)):
            axis_arrays = list(axis_arrays)

        else:
            axis_arrays = [axis_arrays]

        if sort:
            axis_arrays = sorted(axis_arrays, key=lambda x: x['sequence_number'])

        return axis_arrays

    def get_axis_array(self, axis_name=None, sequence_number=None):
        """ Searches for a specific Axis_Array.

        Either *axis_name*, *sequence_number* or both must be specified.
        When both are given, then the result must match both values.

        Parameters
        ----------
        axis_name : str or unicode, optional
            Searches for an Axis_Array with this name.
        sequence_number : int, optional
            Searches for an Axis_Array with this sequence number.

        Returns
        -------
        OrderedDict or None
            The matched Axis_Array, or None if no match was found.
        """

        axis_arrays = self.get_axis_arrays()

        retrieved_axis = None

        for axis in axis_arrays:

            # Find by both axis_name and sequence_number
            if (axis_name is not None) and (sequence_number is not None):

                if (six.text_type(axis['axis_name']) == axis_name) and (axis['sequence_number'] == sequence_number):
                    retrieved_axis = axis

            # Find by axis_name
            elif (axis_name is not None) and (
                    six.text_type(axis['axis_name']) == axis_name):
                retrieved_axis = axis

            # Find by sequence_number
            elif (sequence_number is not None) and (axis['sequence_number'] == sequence_number):
                retrieved_axis = axis

        return retrieved_axis
