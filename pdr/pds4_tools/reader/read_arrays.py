from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import numpy as np

from .array_objects import ArrayStructure, Meta_ArrayStructure
from .data import PDS_array
from .data_types import (data_type_convert_array, pds_to_numpy_type, apply_scaling_and_value_offset,
                         mask_special_constants)

from ..utils.logging import logger_init
from ..extern import six

# Initialize the logger
logger = logger_init()

#################################


def _read_array_byte_data(array_structure, as_string=True, memmap=False):
    """ Reads the byte data from the data file for a PDS4 Array.

    Determines, from the structure's meta data, the relevant start and stop bytes in the data file prior to
    reading.

    Parameters
    ----------
    array_structure : ArrayStructure
        The PDS4 Array data structure for which the byte data needs to be read. Should have been
        initialized via `TableStructure.from_file` method, or contain the required meta data.
    as_string : bool, optional
        If True, the byte data is returned as a byte string (either ``str`` in Python 2, or ``bytes`` in
        Python 3). If False, the byte data is an ndarray of dtype int8. Defaults to True.
    memmap: bool, optional
        If True, the byte data is memory mapped when *as_string* is False. Defaults to False.

    Returns
    -------
    str, bytes, np.ndarray or np.memmap
        The byte data for the table. Either ndarray or memmap of each byte with a dtype of int8,
        or a byte string, depending on the input parameters.
    """

    data_filename = array_structure.parent_filename
    meta_data = array_structure.meta_data

    num_elements = np.prod([axis_array['elements'] for axis_array in meta_data.get_axis_arrays()])
    data_type = meta_data.data_type()
    element_size = pds_to_numpy_type(data_type).itemsize

    start_byte = meta_data['offset']
    stop_byte = start_byte + num_elements * element_size

    num_int8_elements = stop_byte - start_byte

    # Read byte data from file
    try:

        if memmap:

            data = np.memmap(data_filename, offset=start_byte, mode='c', dtype='int8',
                             shape=num_int8_elements)

        else:

            with open(data_filename, 'rb') as file_handler:
                file_handler.seek(start_byte)

                data = np.fromfile(file_handler, dtype='int8', count=num_int8_elements)

    except IOError as e:
        raise six.raise_from(IOError("Unable to read data from file '" + data_filename +
                                     "' found in label - {0}".format(e)), None)

    # Convert to a byte string if requested
    if as_string:
        data = data.tostring()

    return data


def _apply_bitmask(data, bit_mask_string, special_constants=None):
    """ Apply bitmask to *data*, modifying it in-place.

    Parameters
    ----------
    data : array_like
        Flat array-like integer data, byteswapped to be correct for endianness of current system if necessary
    bit_mask_string : str or unicode
        String of 1's and 0's, same length as number of bits in each *data* datum

    Returns
    -------
    None
    """

    # Skip needlessly applying bit_mask if it's all 1's
    if '0' not in bit_mask_string:
        return

    # Convert bit mask to binary (python assumes the input is a string describing the integer in MSB format,
    # which is what the PDS4 standard specifies.)
    bit_mask = int(bit_mask_string, 2)

    # Mask Special_Constants values so that bit mask application does not affect them
    non_masked = np.arange(0, len(data))
    if special_constants is not None:

        masked_data = mask_special_constants(data, special_constants=special_constants)
        non_masked = np.where(masked_data.mask == False)

        del masked_data

    # Apply bit mask to each datum
    for i in np.nditer(non_masked, flags=['zerosize_ok']):
        data[i] &= bit_mask


def new_array(input, no_scale=False, no_bitmask=False, masked=None, copy=True, **structure_kwargs):
    """ Create an `ArrayStructure` from PDS-compliant data or meta data.

    Notes
    -----
    The data attribute will not be a view of the original *input* (if it is a data array), but rather a new
    array. However, the *input* passed into this method may still be modified in-place to save memory, see
    *copy*. A method to get a view of the original data, if conditions are satisfied, is to also pass *input*
    as a kwarg of the name ``structure_data``.

    Parameters
    ----------
    input : PDS_ndarray, PDS_marray or Meta_ArrayStructure
        Either an array containing the data, which must also have a valid PDS4 meta_data attribute
        describing itself, or an instance of valid Meta_ArrayStructure. If input is data, the base data type
        will be taken from its actual dtype, rather than from the meta data it must still contain.
    no_scale : bool, optional
        If False, and input is an array of data, then the data will scaled according to the scaling_factor
        and value_offset meta data. If the *input* is meta data only, then the output data type will be
        large enough to store the scaled values. If False, no scaling or data type conversions will be
        done.
    no_bitmask : bool, optional
        If False, and input is an array of data, then the bitmask indicated in the meta data will be
        applied. If True, the bitmask will not be used. Defaults to False.
    masked : bool or None, optional
        If True, and input is an array of data, then the data will retain any masked values and in
        additional have numeric Special_Constants values masked. If False, any masked values in the input
        array will be unmasked and data assignments will not preserve masked values. If None, masked
        values in the input will be retained only if any are present.
    copy: bool, optional
        If True, a copy of *input* is made, ensuring that it does not get modified during processing.
        If False, then the input may change if it is an array of data. In either case, the output data
        will not be a view. Defaults to True.
    structure_kwargs :  dict, optional
        Keywords that are passed directly to the `ArrayStructure` constructor.

    Returns
    -------
    ArrayStructure
        An object representing the PDS4 array structure. The data attribute will contain an array that
        can store *input* values (or does store it, if input is an array of data). Other attributes may
        be specified via *structure_kwargs*.
    """

    # Determine and validate that input is a Meta_ArrayStructure, PDS_ndarray or PDS_marray
    input_is_array = PDS_array.isinstance(input)
    input_is_meta_array = isinstance(input, Meta_ArrayStructure)

    if (not input_is_array) and (not input_is_meta_array):
        raise RuntimeError('Inputs must all be one of Meta_ArrayStructure, PDS_ndarray or PDS_marray.')

    # Obtain basic meta data
    if input_is_array:
        array = input
        meta_data = input.meta_data

    else:
        array = None
        meta_data = input

    special_constants = meta_data.get('Special_Constants')
    element_array = meta_data['Element_Array']
    scale_kwargs = {} if no_scale else {'scaling_factor': element_array.get('scaling_factor'),
                                        'value_offset': element_array.get('value_offset')}

    # Obtain dtype (ensuring to scale it for future application of scaling and offset if necessary)
    dtype = pds_to_numpy_type(meta_data.data_type(), data=array, include_unscaled=False, **scale_kwargs)

    # Obtain shape
    array_shape = meta_data.dimensions()

    # Decide what type of data array we will be using (i.e., masked or otherwise)
    if masked is None:
        masked = np.ma.is_masked(input)

    array_type = PDS_array.get_array(masked=masked)

    # Create the ArrayStructure
    array_structure = ArrayStructure(**structure_kwargs)
    if array_structure.data_loaded:

        # Ensure data array is of requested type if it was already supplied
        array_structure.data = array_structure.data.view(array_type)

    else:

        # Create the structured data array, and assign a view of it as a PDS_array type
        array_structure.data = np.empty(array_shape, dtype=dtype).view(array_type)

    # For cases where input is PDS_array, we transfer their data into the new array
    if input_is_array:

        array = input.copy() if copy else input

        # Apply the bit mask to extracted_data if necessary
        bit_mask = (meta_data.get('Object_Statistics') or {}).get('bit_mask')
        if (not no_bitmask) and (bit_mask is not None):
            bit_mask_string = six.text_type(bit_mask).zfill(array.dtype.itemsize * 8)
            _apply_bitmask(array, bit_mask_string, special_constants=special_constants)

        # Adjust data values to account for 'scaling_factor' and 'value_offset' (in-place if possible)
        # (Note that this may change the data type to prevent overflow and thus increase memory usage.)
        if not no_scale:
            array = apply_scaling_and_value_offset(array, special_constants=special_constants, **scale_kwargs)

        # Mask Special_Constants in output if requested
        if masked:
            array = mask_special_constants(array, special_constants=special_constants)

        # Reshape array as necessary
        if len(array_shape) > 1:
            array = array.reshape(array_shape)

        # Assign data, and ensure data array is of requested type if it was already supplied
        array_structure.data = array.view(array_type)

        # Set correct fill value if our data is masked (necessary only on NumPy < v1.13)
        if masked and isinstance(array, np.ma.MaskedArray):
            array_structure.data.set_fill_value(array.fill_value)

    return array_structure


def read_array_data(array_structure, no_scale, masked, memmap=False):
    """
    Reads and properly formats the data for a single PDS4 array structure, modifies *array_structure* to
    contain all extracted fields for said table.

    Parameters
    ----------
    array_structure : ArrayStructure
        The PDS4 Array data structure to which the data should be added.
    no_scale : bool
        Returned data will not be adjusted according to the offset and scaling factor.
    masked : bool
        Returned data will have numeric Special_Constants masked.
    memmap : bool, optional
        If True, extracted data is memory mapped. Only guaranteed for unscaled data or for *no_scale*;
        otherwise returned data maybe a copy. Defaults to False.

    Returns
    -------
    None
    """

    # Obtain basic meta data
    meta_data = array_structure.meta_data
    data_type = meta_data.data_type()

    # Read the data in, and transform it to the necessary data type
    extracted_data = _read_array_byte_data(array_structure, as_string=False, memmap=memmap)
    extracted_data = data_type_convert_array(data_type, extracted_data)

    # Merge data and meta_data into a PDS_ndarray
    extracted_data = PDS_array(extracted_data, meta_data)

    # Finish processing (scale and applying bit mask), then set obtained data
    array_structure.data = new_array(extracted_data, no_scale=no_scale, no_bitmask=False,
                                     masked=masked, copy=False).data


def read_array(full_label, array_label, data_filename, lazy_load=False, no_scale=False):
    """ Create the `ArrayStructure`, containing label, data and meta data for a PDS4 Array from a file.

    Used for all forms of PDS4 Arrays (e.g., Array, Array_2D_Image, Array_3D_Spectrum, etc).

    Parameters
    ----------
    full_label : Label
        The entire label for a PDS4 product, from which *array_label* originated.
    array_label : Label
        Portion of label that defines the PDS4 array data structure.
    data_filename : str or unicode
        Filename, including the full path, of the data file that contains the data for this array.
    lazy_load : bool, optional
        If True, does not read-in the data of this array until the first attempt to access it.
        Defaults to False.
    no_scale : bool, optional
        If True, returned data will not be adjusted according to the offset and scaling factor.
        Defaults to False.

    Returns
    -------
    ArrayStructure
        An object representing the array; contains its label, data and meta data

    Raises
    ------
    TypeError
        Raised if called on a non-array according to *array_label*.
    """

    # Skip over data structure if its not actually an Array
    if 'Array' not in array_label.tag:
        raise TypeError('Attempted to read_array() on a non-array: ' + array_label.tag)

    # Create the data structure for this array
    array_structure = ArrayStructure.from_file(data_filename, array_label, full_label,
                                               lazy_load=lazy_load, no_scale=no_scale)

    return array_structure
