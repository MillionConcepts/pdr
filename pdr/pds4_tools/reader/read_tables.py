from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import itertools
from functools import reduce
from math import log10

import numpy as np

from .read_arrays import apply_scaling_and_value_offset
from .table_objects import (TableStructure, TableManifest, Meta_Field)
from .data import PDS_array
from .data_types import (data_type_convert_table_ascii, data_type_convert_table_binary,
                         decode_bytes_to_unicode, pds_to_numpy_type, pds_to_numpy_name,
                         mask_special_constants, get_min_integer_numpy_type)

from ..utils.constants import PDS4_TABLE_TYPES
from ..utils.logging import logger_init

from ..extern import six
from ..extern.six.moves import range

# Initialize the logger
logger = logger_init()

#################################


def _read_table_byte_data(table_structure):
    """ Reads the byte data from the data file for a PDS4 Table.

    Determines, from the structure's meta data, the relevant start and stop bytes in the data file prior to
    reading. For fixed-width tables (Table_Character and Table_Binary), the returned data is exact. For
    Table_Delimited, the byte data is likely to go beyond end of its last record.

    Parameters
    ----------
    table_structure : TableStructure
        The PDS4 Table data structure for which the byte data needs to be read. Should have been
        initialized via `TableStructure.from_file` method, or contain the required meta data.

    Returns
    -------
    str or bytes
        The byte data for the table.
    """

    from .core import read_byte_data

    meta_data = table_structure.meta_data
    num_records = meta_data['records']
    start_byte = meta_data['offset']

    if meta_data.is_fixed_width():

        record_length = meta_data.record['record_length']
        stop_byte = start_byte + num_records * record_length

    elif meta_data.is_delimited():

        object_length = meta_data.get('object_length')
        record_length = meta_data.record.get('maximum_record_length')

        if object_length is not None:
            stop_byte = start_byte + object_length

        elif record_length is not None:
            stop_byte = start_byte + num_records * record_length

        else:
            stop_byte = -1

    else:
        raise TypeError('Unknown table type: {0}'.format(table_structure.type))

    return read_byte_data(table_structure.parent_filename, start_byte, stop_byte)


def _make_uniformly_sampled_field(table_structure, uni_sampled_field):
    """ Create/obtain data for a Uniformly_Sampled field.

    Notes
    -----
    Under the vast majority of cases, the data type of the returned data from this method will
    be a 64-bit float. It is not quickly and easily possible to determine for a very large uniformly
    sampled field whether all the returned data will be integers. While we could use Python's
    built-in numerics and lists, which would then not require knowing ahead of time whether
    all the data is integer or float, this would be very memory inefficient due to overhead
    for each built-in Python numeric type. Therefore we instead almost assume that the data will
    be floats and require 64-bit precision, and leave it to a user to cast the data if desired.

    Parameters
    ----------
    table_structure : TableStructure
        The PDS4 Table data structure which contains the *uni_sampled_field*.
    uni_sampled_field : Label
        Portion of label that defines a single Uniformly Sampled field.

    Returns
    -------
    np.ndarray
        The data created for the Uniformly Sampled field based on the specified label description.
    """

    # Extract scale (older PDS4 standards allowed leaving it empty)
    if 'scale' not in uni_sampled_field:
        scale = 'linear'

    else:
        scale = uni_sampled_field['scale'].lower()

    # Extract necessary values to speed up calculation
    num_records = table_structure.meta_data['records']
    first_value = uni_sampled_field['first_value']
    last_value = uni_sampled_field['last_value']
    interval = uni_sampled_field['interval']

    # If the first and last value (one of which should contain the largest possible value) are integers,
    # there is a chance that the uniformly sampled field contains integers larger than even double supports
    # (without Inf). Therefore we check this, and use 'object' dtype in such a case.
    if isinstance(first_value, six.integer_types) and isinstance(last_value, six.integer_types):
        dtype = get_min_integer_numpy_type([first_value, last_value])

        if dtype == 'object':
            logger.warning('Detected numeric data exceeding 8 bytes in Uniformly Sampled field. For integer '
                           'data this precision exceeds memory efficient case. For decimal data, the data'
                           'will be downcast to 8-byte floats.')
    else:
        dtype = None

    # Create an array_like to contain the data for this field
    dtype = 'object' if dtype == 'object' else 'float64'
    data = np.empty(num_records, dtype=dtype)

    # Calculate field's data for Linear sampling
    if scale == 'linear':

        current_value = first_value

        for j in range(0, num_records):

            data[j] = current_value
            current_value += interval

    # Calculate field's data for Logarithmic sampling
    elif scale == 'logarithmic':

        # Implements xj = x1 * (xn/x1)^[(j-1)/(n-1)] for j = 1 ... n, where xn/x1^(1/(n-1)) is the
        # interval and x1 ... xj are the field's data.

        x1 = first_value

        for j in range(0, num_records):

            current_value = x1 * (interval ** j)
            data[j] = current_value

    # Calculate field's data for Exponential sampling
    elif scale == 'exponential':

        # Implements b^xj = b^x1 + (j-1)*(b^xn - b^x1)/(n-1) for j = 1 ... n, where (b^xn - b^x1)/(n-1)
        # is the interval and x1 ... xj are the field's data.

        base = uni_sampled_field['base']

        log_x1 = base ** first_value
        log_base = log10(base)

        for j in range(0, num_records):

            current_value = log10(log_x1 + j * interval) / log_base
            data[j] = current_value

    # Function to compare closeness of two floating point numbers, based on PEP-0485 with larger tolerance
    def is_close_num(a, b, rel_tol=1e-3, abs_tol=0.0):
        return abs(a-b) <= max(rel_tol * max(abs(a), abs(b)), abs_tol)

    # Warn if last calculated value for Uniformly Sampled does not match indicated last value in label
    if not is_close_num(last_value, data[-1]):
        logger.warning("Last value in Uniformly Sampled field, '{0}', does not match expected '{1}'."
                       .format(data[-1], last_value))

    return data


def _extract_fixed_width_field_data(extracted_data, table_byte_data,
                                    field_length, field_location, record_length,
                                    array_shape, group_locations=(), repetition_lengths=()):
    """
    Extracts data for a single field in a fixed-width (Character or Binary) table.

    Parameters
    ----------
    extracted_data : list[str or bytes]
        The extracted byte data for each element the table. Should be an empty list on initial call.
        Modified in-place.
    table_byte_data : str or bytes
        Byte data for the entire table.
    field_length : int
        Length of each element in the field, in bytes.
    field_location : int
        Location of the first element in the field, in bytes, from the beginning of the table.
    record_length : int
        Length of each record in the table, in bytes.
    array_shape : array_like[int]
        Sequence of dimensions for the field. First element is the number of records, all other
        elements are the number of repetitions for each GROUP the field is inside of, if any.
    group_locations : array_like[int], optional
        If this field is inside at least one group field, the array must contain the location of the
        first element of the first repetition (i.e, group_location), in bytes, of each group.
    repetition_lengths : array_like[int], optional
        If this field is inside at least one group field, the array must contain the group length divided
        by the number of repetitions (i.e, group_length/repetitions), in bytes, for each group.

    Returns
    -------
    None
    """

    # Simplified, sped up, case for fields that are not inside group fields
    if len(array_shape) == 1:

        # Loop over each record, extracting the datum for this field
        for record_num in range(0, array_shape[0]):

            start_byte = (record_num * record_length) + field_location
            stop_byte = start_byte + field_length

            extracted_data.append(table_byte_data[start_byte:stop_byte])

        return

    # Determine if the data for a field inside group fields is contiguous. If it is, we can significantly
    # speed operations up. To determine if contiguous, we check that all group locations (except possibly
    # the first) start from the first byte, and that the group_length/group_repetitions of each group is
    # equal to the group_length of its child group. Finally, we check that the group_length/group_repetitions
    # for the last group is equal to the field length.
    has_contiguous_locations = group_locations[1:] == [0] * (len(group_locations) - 1)
    has_contiguous_end_bytes = field_length == repetition_lengths[-1]

    for i, length in enumerate(repetition_lengths[1:]):

        if length * array_shape[i+2] != repetition_lengths[i]:
            has_contiguous_end_bytes = False

    # Simplified, sped up, case for fields inside group fields that are contiguous. Principle of
    # operation is that we can effectively read one element after the other, as we would in an array,
    # where the only thing we need to know is the element length. A slight complication is that we
    # need to take into account the byte jump between end of the field for one record and start of it
    # for the next record.
    if has_contiguous_locations and has_contiguous_end_bytes:

        group_start_byte = group_locations[0]
        num_elements = reduce(lambda x, y: x*y, array_shape[1:])

        # Loop over each record
        for record_num in range(0, array_shape[0]):

            record_start_byte = (record_num * record_length) + group_start_byte + field_location

            # Loop over each element (multiple due to group field) in the record for this field,
            # extracting them
            for element_num in range(0, num_elements):
                start_byte = record_start_byte + field_length * element_num
                stop_byte = start_byte + field_length

                extracted_data.append(table_byte_data[start_byte:stop_byte])

        return

    # If we've reached this point then our field is inside group fields, and those group fields are not
    # contiguous. Therefore we will need to calculate each and every position.

    # Create a list of positions, where each position is one of every possible valid combination of the
    # dimension values in *array_shape*. E.g., if the shape of the field (due to a GROUP) is [100, 50], then
    # the positions created by itertools.product will have values [0, 0], [0, 1], ... [0, 49], [1, 0], ...
    # [1, 49], [2, 0] ... [99, 49]. Each position therefore contains the record number and the group
    # repetition numbers for each GROUP the field is in. In case of field that is not inside any groups, this
    # simplifies to a single for-loop which loops over each record in the field.
    product_list = [range(0, repetitions) for repetitions in array_shape]
    positions = itertools.product(*product_list)

    # Extract each element's byte data if we have its full position in array_shape, via the formula:
    # start_byte = record_length * i_current_record_number
    # + first_group_location + (first_group_length/first_group_repetitions) * j_current_first_group_repetition
    # + (repeat) n_group_location + (n_group_length/n_group_repetitions) * k_current_n_group_repetition
    # + field_location
    # stop_byte = start_byte + field_length
    for current_position in positions:

        start_byte = record_length * current_position[0] + field_location

        for i in range(0, len(group_locations)):
            start_byte += group_locations[i] + repetition_lengths[i] * current_position[i + 1]

        stop_byte = start_byte + field_length
        extracted_data.append(table_byte_data[start_byte:stop_byte])


def _extract_delimited_field_data(extracted_data, table_byte_data, start_bytes, current_column, array_shape,
                                  skip_factors=()):
    """
    Extracts data for a single field in a delimited table.

    Parameters
    ----------
    extracted_data : list[str or bytes]
        The extracted byte data for each element the table. Should be an empty list on initial call.
        Modified in-place.
    table_byte_data : array_like[str or bytes]
        Byte data for the entire table, split into records.
    start_bytes : array_like
        The start byte for each element in the table. Two-dimensional, where the first dimension specifies
        which column (if the record were split by delimiter) and the second dimension specifies which record.
    current_column : int
        Specifies which column (if the record were split by delimiter) to extract the data for. For fields
        that are inside GROUPs, this represents only the first column (i.e. for the first repetition). For
        tables without GROUP fields, this is equivalent to the field number.
    array_shape : array_like[int]
        Sequence of dimensions for the field. First element is the number of records, all other
        elements are the number of repetitions for each GROUP the field is inside of, if any.
    skip_factors : array_like[int], optional
        If this field is inside at least one group field, the array must contain the number of columns to
        skip between each repetition, for each group.

    Returns
    -------
    None
    """

    num_records = array_shape[0]
    group_shape = np.asarray(array_shape[1:])
    num_group_columns = 0 if (len(array_shape) == 1) else group_shape.prod()

    # Extract data from non-GROUP fields. Simplified, sped up, case.
    if num_group_columns == 0:

        # Pre-extract necessary variables to speed up computation time
        field_start_bytes = start_bytes[current_column]
        next_field_start_bytes = start_bytes[current_column + 1]

        # Extract the byte data for this field from byte_data
        for record_num in range(0, num_records):
            column = field_start_bytes[record_num]
            end_idx = next_field_start_bytes[record_num] - 1

            extracted_data.append(table_byte_data[record_num][column:end_idx])

        # Remove start_bytes for no-longer needed columns to save memory
        start_bytes[current_column] = None

    # Extract data from GROUP fields. This process could basically be used for non-GROUP fields also,
    # however it would be slower than the optimized code for that specific case above.
    else:

        # Create a list of positions, where each position is one of every possible valid combination of the
        # dimension values in `group_shape`. E.g., if the shape of the field (due to a GROUP) is [100, 50],
        # then the positions created by itertools.product will have values [0, 0], [0, 1], ... [0, 49],
        # [1, 0], ... [1, 49], [2, 0] ... [99, 49]. Each position therefore is the group repetition numbers
        # for each GROUP the field is in. In case of field that is not inside any groups, this is an empty
        # list.
        product_list = [range(0, repetitions) for repetitions in array_shape[1:]]
        positions = itertools.product(*product_list)

        # Create an array that will store the indexes of *start_bytes* necessary to extract all the
        # repetitions of this field for a single record (see below for details). To save memory, we use
        # the smallest data  type that can contain all the needed indexes.
        start_column = current_column
        max_column = start_column + (num_group_columns-1) + ((group_shape-1) * skip_factors).sum()
        array_dtype = get_min_integer_numpy_type([max_column])
        columns = np.empty(num_group_columns, dtype=array_dtype)

        # Extract the indexes of *start_bytes* that correspond to the correct columns for this field. This
        # is necessary for group fields, for which the column number in *start_bytes* (which are obtained
        # by splitting records by the delimiter) will not correspond to the field number, as there is only
        # one field number but many repetitions (i.e. columns). Additionally, when multiple fields are
        # inside a single group the columns comprising the repetitions of each of those fields are not
        # sequential. We use *skip_factors* to determine how many columns to skip inside *start_bytes* for
        # each group-level for each field. These indexes are identical for each record (although the actual
        # *start_bytes* values will be different), and therefore saved to speed up operations.
        for i, current_position in enumerate(positions):

            column = start_column

            # Starting from the column number for the first repetition of this field, apply the correct skip
            # factors for each repetition of the group the field is inside of to obtain the column number for
            # the column that contains the repetition indicated by *current_position*.
            for j, repetition_num in enumerate(current_position):
                column += skip_factors[j] * repetition_num

            columns[i] = column
            start_column += 1

        # Extract the byte data for this field from byte_data
        for record_num in range(0, num_records):

            # Loop over each repetition of the field
            for column in columns:

                field_start_bytes = start_bytes[column][record_num]
                next_field_start_bytes = start_bytes[column + 1][record_num] - 1

                extracted_data.append(table_byte_data[record_num][field_start_bytes:next_field_start_bytes])

        # Remove start_bytes for no-longer needed columns to save memory
        for column in columns:

            prev_column = column-1

            # We can only erase *start_bytes* that will not be used as end-bytes
            # (i.e. start_bytes[column + 1]) above for another field.
            if (prev_column in columns) or (prev_column < 0) or (start_bytes[prev_column] is None):
                start_bytes[column] = None


def _get_delimited_records_and_start_bytes(records, table_structure, table_manifest):
    """
    For a delimited table, we obtain the start byte of each column (and each repetition of column)
    for each record, and adjust the records themselves such that any column value starts at its start byte
    and ends at the start byte of the next column value.

    In principle there are a number of ways to read a delimited table. The built-in Python delimited table
    reader does not support specifying line-endings as solely those allowed by PDS4. NumPy's ``genfromtxt``
     was found to be much slower than the technique below, though this should be retested periodically.
    For manual reading (i.e., without using above tools), one could read a delimited table in row by row:
    however when converting each value to a data type, there is CPU overhead in determining what that data
    type should be and the conversion itself. If we read a row, and then convert each value for that row one
    at a time then we have that overhead each time and that becomes extremely costly for large numbers of
    records. If we could read an entire column at a time and convert it then we avoid said overhead. One
    easy approach to the latter is to store a 2D array_like[record, column], thus splitting the data first
    into records and then each record by delimiter (adjusting to account for double quote where needed).
    However in general this approach is often very memory intensive because the strings, especially with
    overhead, require more memory to store than once the data is converted to its desired type. Instead, we
    take a similar approach where we use a 2D array_like[column, record] to record the start bytes of the data
    for each column but do not actually split each record into fields. We use NumPy ndarrays with integer
    dtypes of minimal size required to store each start byte; this will nearly always result in
    significantly less memory than would be required to actually split each field into a string since the
    start bytes will nearly always be 1 or 2 bytes each because records are rarely longer than 65535
    characters.

    Notes
    -----
    The terminology of column and field are not identical as used in this function. Columns are obtained
    by splitting each record by the delimiter (accounting for double quotes); for PDS4 fields inside groups
    the result is that there are many columns for a single field due to repetitions. The start bytes returned
    by this method are for each column (as opposed to field), and the repetitions for a single field are
    not necessarily sequential in that result (i.e. if there is more than one field in any group.)

    Parameters
    ----------
    records : list[str or bytes]
        The data for the delimited table, split into records.
    table_structure : TableStructure
        The PDS4 Table data structure for the delimited table.
    table_manifest : TableManifest
        A manifest describing the structure of the PDS4 delimited table.

    Returns
    -------
    list[str or bytes], list[array_like]
        A two-valued tuple of: the records for the table, modified to remove quotes; and a 2D list, where
        the first dimension is the column and the second dimension is the record, with the value being
        the start byte of the data contained in the first tuple value for those parameters. See Notes
        above for difference between column as referred to here and PDS4 fields.
    """

    # Extract the proper record delimiter (as bytes, for compatibility with Python 3)
    delimiter_name = table_structure.meta_data['field_delimiter'].lower()
    field_delimiter = {'comma': b',',
                       'horizontal tab': b'\t',
                       'semicolon': b';',
                       'vertical bar': b'|'
                      }.get(delimiter_name, None)

    # Determine total number of columns (if we split the record by record delimiter) in each record.
    # A column is either a field or if there's a GROUP then it's one of the repetitions of a field.
    # This number, as are other references to this number in the code, are corrected for cases where
    # we ignore the record delimiter as its effectively escaped by being between bounding double quotes.
    num_columns = 0

    for field in table_manifest.fields():

        repetitions = []
        parent_idx = table_manifest.index(field)

        for j in range(0, field.group_level):
            parent_idx = table_manifest.get_parent_by_idx(parent_idx, return_idx=True)
            repetitions.append(table_manifest[parent_idx]['repetitions'])

        num_columns += 1 if (not repetitions) else reduce(lambda x, y: x*y, repetitions)

    # Pre-allocate ``list``, which will store NumPy ndarray's, containing the start byte of each field
    # for each record. Thus `start_bytes` is a two-dimensional array_like, where the first dimension is
    # the field and the second dimension is the record, with the value being the start byte of the data
    # for those parameters.
    start_bytes = [None] * (num_columns + 1)

    longest_record = len(max(records, key=len))
    array_dtype = get_min_integer_numpy_type([longest_record + 1])

    for i in range(0, num_columns + 1):
        start_bytes[i] = np.empty(len(records), dtype=array_dtype)

    # In Python 3, when checking for the first and last character below, we need to convert the value
    # to a ``str``, since obtaining first character of a ``bytes`` returns a byte value. In Python 2, no
    # action needs to be taken since the value is ``str`` by default.
    if six.PY2:
        str_args = ()
    else:
        str_args = ('utf-8', )

    # Obtain start bytes for each column in each record, and adjust the record itself such that only the
    # start byte is required to obtain the entire value (to save RAM). The latter is needed due to the
    # requirement to ignore delimiters found inside enclosing quotes and that such enclosing quotes themselves
    # are not part of the value: i.e., a record consisting of '"value1", value2' would want to use the start
    # byte of 'value2' as the end byte of '"value1"', but this would include the extra quote at the end,
    # therefore we remove such quotes after recording the proper start byte.
    for record_idx, record in enumerate(records):

        # Split the record by delimiter
        split_record = record.split(field_delimiter)
        next_start_byte = 0

        # Look for column values bounded by a double quotes. Inside such values any delimiter found should be
        # ignored, but ``split`` above will not ignore it. Therefore we have to join the value back.
        if b'"' in record:

            split_record_len = len(split_record)
            column_idx = 0

            # Loop over each column value (may turn out to only be part of a column)
            while column_idx < split_record_len:
                value = split_record[column_idx]
                value_length = len(value)
                first_character = str(value, *str_args)[0] if value_length > 0 else None

                # If field value starts with a quote then we need to check if there is a matching closing
                # quote somewhere further.
                if first_character == '"':

                    next_quote_idx = -1

                    # Find the index of the column value containing the next quote in the record
                    if b'"' in value[1:]:
                        next_quote_idx = column_idx

                    else:

                        for k, next_value in enumerate(split_record[column_idx + 1:]):
                            if b'"' in next_value:
                                next_quote_idx = column_idx + 1 + k
                                break

                    # If a latter or same field value contained a quote, check whether it was the last
                    # character in the value (and thus the two quotes enclosed a single value)
                    if next_quote_idx >= 0:
                        next_value = split_record[next_quote_idx]
                        last_character = str(next_value, *str_args)[-1] if len(next_value) > 0 else None

                        if last_character == '"':

                            # Reconstruct the original value prior to ``split``
                            original_value = field_delimiter.join(split_record[column_idx:next_quote_idx+1])

                            # Remove the quote at the start and end of the original value
                            original_value = original_value[1:-1]

                            # Insert the joined value back into split_record (and remove its split components)
                            split_record = split_record[0:column_idx] + [original_value] + \
                                           split_record[next_quote_idx+1:]

                            # We've joined several values into one, therefore split_record_len has shrunk
                            split_record_len -= next_quote_idx - column_idx

                            # Record the start byte of this column, and adjust the next start byte to account
                            # for the entire length of the joined field
                            start_bytes[column_idx][record_idx] = next_start_byte
                            next_start_byte += len(original_value) + 1

                            column_idx += 1
                            continue

                # If the record had a quote somewhere but not in this column or it was not an enclosing quote
                # for the column then we simply record its start byte and set the next start byte as usual
                start_bytes[column_idx][record_idx] = next_start_byte
                next_start_byte += value_length + 1

                column_idx += 1

            # Join (the potentially) adjusted record back into a single string to save ``str`` overhead memory
            records[record_idx] = field_delimiter.join(split_record)

        # If there were no quotes in the record then we can simply record the start bytes of each value
        # (surprisingly splitting the record and doing this via length of each value appears to be the
        # fastest way to accomplish this since ``str.split`` is written in C.)
        else:

            for column_idx, value in enumerate(split_record):
                start_bytes[column_idx][record_idx] = next_start_byte
                next_start_byte += len(value) + 1

        # Add an extra start byte, which actually acts only as the end byte for the last field
        start_bytes[-1][record_idx] = next_start_byte

    return records, start_bytes


def new_table(fields, no_scale=False, decode_strings=False, masked=None, copy=True, **structure_kwargs):
    """ Create a `TableStructure` from PDS-compliant data or meta data.

    Notes
    -----
    The data attribute will not be a view of the original *fields* (if they are data arrays), but rather
    a new array. However, the *fields* passed into this method may still be modified in-place to save
    memory, see *copy*. If *fields* originated from a single structured ndarray, then a method to get
    a view of the original data, if conditions are satisfied, is to also pass that single structured
    ndarray as a kwarg of the name``structure_data``.

    Parameters
    ----------
    fields : list[PDS_ndarray, PDS_marray or Meta_Field]
        A list of either fields with data, which each must contain a valid PDS4 meta_data attribute
        defining the field, or a list of valid Meta_Field's. If input is data, the base data type will
        be taken from its actual dtype, rather than from the meta data it must still contain.
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
    copy: bool, optional
        If True, a copy of *fields* is made, ensuring that they do not get modified during processing.
        If False, then the fields may change if each is an array of data. In either case, the output data
        will not be a view. Defaults to True.
    structure_kwargs : dict, optional
        Keywords that are passed directly to the `TableStructure` constructor.

    Returns
    -------
    TableStructure
        An object representing the PDS4 table structure. The data will contain a structured array that
        can store values for *fields* (or does store it, if input is a list of fields with data). Other
        attributes may be specified via *structure_kwargs*.
    """

    # For each field in the record array, create the dtype needed to initialize it. For each said field,
    # this will be either a two valued tuple (unique_field_name, numpy_dtype) or a three valued tuple, with
    # the third value being the shape when the data for that field is non-flat (e.g. for group fields).
    dtypes = []
    array_shapes = []

    # Determine and validate that input is a sequence of all Meta_Field, PDS_ndarray or PDS_marray
    input_is_fields = all([PDS_array.isinstance(field) for field in fields])
    input_is_meta_fields = all([isinstance(field, Meta_Field) for field in fields])

    if (not input_is_fields) and (not input_is_meta_fields):
        raise RuntimeError('Inputs must all be one of Meta_Field, PDS_ndarray or PDS_marray.')

    # Obtain the name, shape and dtype for each field in the record array that will contain the data.
    for i, field in enumerate(fields):

        # Obtain the meta data for Meta_Fields
        if input_is_meta_fields:

            meta_field = field
            data_kwargs = {}

        # Obtain the meta data for PDS_ndarray or PDS_marray
        else:

            meta_field = field.meta_data
            data_kwargs = {'data': field}

        scale_kwargs = {} if no_scale else {'scaling_factor': meta_field.get('scaling_factor'),
                                            'value_offset': meta_field.get('value_offset'),
                                            'include_unscaled': False}

        # Obtain dtype (ensuring to scale it for future application of scaling and offset if necessary)
        dtype = pds_to_numpy_type(meta_field.data_type(),
                                  field_length=meta_field.get('length'),
                                  decode_strings=decode_strings,
                                  **dict(data_kwargs, **scale_kwargs))

        # Obtain the array shape
        array_shape = meta_field.shape
        array_shapes.append(array_shape)

        # Obtain the field name. Use full name, to address the case of two fields with the same name,
        # which NumPy does not support.
        name = pds_to_numpy_name(meta_field.full_name())

        # Create the dtype initializer for this field, as NumPy requires it
        if array_shape[1:]:
            dtypes.append((name, dtype, tuple(array_shape[1:])))
        else:
            dtypes.append((name, dtype))

    # Obtain the number of records
    num_all_records = [shape[0] for shape in array_shapes]
    if min(num_all_records) != max(num_all_records):
        raise RuntimeError('Input fields do not all have the same number of records.')
    else:
        num_records = min(num_all_records)

    # Decide what type of data array for the table we will be using (i.e., masked or otherwise)
    if masked is None:
        masked = any([np.ma.is_masked(field) for field in fields])

    array_type = PDS_array.get_array(masked=masked)

    # Create the TableStructure
    table_structure = TableStructure(**structure_kwargs)
    if table_structure.data_loaded:

        # Ensure data array is of requested type if it was already supplied
        table_structure.data = table_structure.data.view(array_type)

    else:

        # Create the structured data array, and assign a view of it as a PDS_array type
        table_structure.data = np.recarray(num_records, dtype=dtypes).view(array_type)

    # For cases where input is PDS_array, we transfer their data into the new table
    if input_is_fields:

        # Create final versions of the fields and set them inside the table
        # (e.g. apply scaling, convert strings to unicode if requested, etc)
        for i, field in enumerate(fields):

            array_shape = array_shapes[i]
            extracted_data = field.copy() if copy else field
            meta_field = field.meta_data
            special_constants = meta_field.get('Special_Constants')
            is_bitstring_data = meta_field.data_type().issubtype('BitString')

            # Adjust data to decode strings if requested
            if np.issubdtype(extracted_data.dtype, np.character) and (not is_bitstring_data) and decode_strings:
                extracted_data = decode_bytes_to_unicode(extracted_data)

            # Adjust data values to account for 'scaling_factor' and 'value_offset' (in-place if possible)
            # (Note that this may change the data type to prevent overflow and thus increase memory usage)
            if not no_scale:
                extracted_data = apply_scaling_and_value_offset(extracted_data,
                                                                meta_field.get('scaling_factor'),
                                                                meta_field.get('value_offset'),
                                                                special_constants=special_constants)

            # Mask Special_Constants in output if requested
            if masked:
                extracted_data = mask_special_constants(extracted_data, special_constants=special_constants)

            # For fields inside groups, we reshape them into the proper shape
            if len(array_shape) > 1:
                extracted_data = extracted_data.reshape(array_shape)

            # Set read-in field in the TableStructure
            table_structure.set_field(extracted_data, meta_field)

    return table_structure


def table_data_size_check(table_structure, quiet=False):
    """ Checks, and warns, if table is estimated to have a large amount of data.

    This estimate is done from the meta-data only and excludes nested fields (fields inside groups fields)
    and repetitions. A more accurate meta-data only estimate could be obtained via `TableManifest`.

    Parameters
    ----------
    table_structure : Structure
        The table structure whose data to check for size.
    quiet : bool, optional
        If True, does not output warning if table contains a large amount of data. Defaults to False.

    Returns
    -------
    bool
        True if the table structure exceeds pre-defined parameters for size of its data, False otherwise.
    """

    meta_data = table_structure.meta_data
    dimensions = meta_data.dimensions()

    # Estimate of the number of elements in the table
    num_elements = dimensions[0] * dimensions[1]

    # Limit at which the data is considered large
    if meta_data.is_delimited():

        # Loading delimited tables is slower than fixed-width tables due to additional required processing
        num_elements_warn = 2 * 10**7

    else:
        num_elements_warn = 4 * 10**7

    if num_elements > num_elements_warn:

        if not quiet:
            logger.info("{0} contains a large amount of data. Loading data may take a while..."
                        .format(table_structure.id))

        return True

    return False


def read_table_data(table_structure, no_scale, decode_strings, masked):
    """
    Reads and properly formats the data for a single PDS4 table structure, modifies *table_structure* to
    contain all extracted fields for said table.

    Parameters
    ----------
    table_structure : TableStructure
        The PDS4 Table data structure to which the table's data fields should be added.  Should have been
        initialized via `TableStructure.from_file` method.
    no_scale : bool
        Returned data will not be adjusted according to the offset and scaling factor.
    masked : bool
        Returned data will have numeric Special_Constants masked.
    decode_strings : bool
        If True, character data types contained in the returned data will be decoded to the ``unicode`` type
        in Python 2, and to the ``str`` type in Python 3. If False, leaves character types as byte strings.

    Returns
    -------
    None
    """

    # Provide a warning to the user if the data is large and may take a while to read
    table_data_size_check(table_structure)

    # Obtain the byte data of the table
    table_byte_data = _read_table_byte_data(table_structure)

    # Obtain a manifest for the table, which describes the table structure (the fields and groups)
    table_manifest = TableManifest.from_label(table_structure.label)

    # Extract the number of records
    num_records = table_structure.meta_data['records']

    # Stores the initial non-post-processed version of fields
    extracted_fields = []

    # Special processing for delimited tables
    if table_structure.meta_data.is_delimited():

        delimiter_name = table_structure.meta_data['record_delimiter'].lower()
        record_delimiter = {'line-feed': b'\n',
                            'carriage-return line-feed': b'\r\n'
                           }.get(delimiter_name, None)

        # Split the byte data into records
        table_byte_data = table_byte_data.split(record_delimiter)[0:num_records]

        # Obtain adjusted records (to remove quotes) and start bytes (2D array_like, with first dimension
        # the field number and the second dimension the record number, and the value set to the start byte
        # of the data for those parameters).
        table_byte_data, start_bytes = _get_delimited_records_and_start_bytes(table_byte_data,
                                                                              table_structure, table_manifest)

    # Create data for the Uniformly Sampled fields
    for field in table_manifest.uniformly_sampled_fields():

        created_data = _make_uniformly_sampled_field(table_structure, field)
        extracted_fields.append(PDS_array(created_data, field))

    # For each regular field, do initial read-in from byte data and conversion to its actual data type. No
    # post-processing is done in this loop (for example, no scaling and no conversion to unicode).
    for field in table_manifest.fields(skip_uniformly_sampled=True):

        # Field index in the manifest
        field_idx = table_manifest.index(field)

        # Stores the shape that that the data for this field will take-on
        array_shape = field.shape

        # Create flat list that will contain the (flat) data for this Field
        extracted_data = []

        # Extract the byte data for the field (delimited tables)
        if table_structure.meta_data.is_delimited():

            # The current column represents which column of `start_bytes` has the data for the field being
            # looped over. For fields inside groups, this is the column with the first repetition only.
            current_column = table_manifest.get_field_offset(field_idx)

            # Obtain the skip factors for this field, necessary to determine the columns containing
            # field repetitions (only relevant for fields inside groups)
            skip_factors = table_manifest.get_field_skip_factors(field_idx)

            # Extract data for the current field
            _extract_delimited_field_data(extracted_data, table_byte_data,
                                          start_bytes, current_column, array_shape, skip_factors)

        # Extract the byte data for the field (fixed-width tables)
        else:

            # Store the group_location and the group_length divided by the number of repetitions for each
            # group the field is inside of (added in for loop below)
            group_locations = []
            repetition_lengths = []

            parent_idx = field_idx
            for parent_group in table_manifest.get_parents_by_idx(parent_idx):
                group_locations.insert(0, parent_group['location'] - 1)
                repetition_lengths.insert(0, parent_group['length'] // parent_group['repetitions'])

            record_length = table_structure.meta_data.record['record_length']

            # Extract data for the current field
            _extract_fixed_width_field_data(extracted_data, table_byte_data, field['length'],
                                            field['location'] - 1, record_length,
                                            array_shape, group_locations, repetition_lengths)

        # Cast the byte data for this field into the appropriate data type
        try:

            args = [field.data_type(), extracted_data]
            kwargs = {'decode_strings': False}

            if table_structure.type == 'Table_Character':
                extracted_data = data_type_convert_table_ascii(*args, **kwargs)

            elif table_structure.type == 'Table_Binary':
                extracted_data = data_type_convert_table_binary(*args, **kwargs)

            elif table_structure.meta_data.is_delimited():
                extracted_data = data_type_convert_table_ascii(*args, mask_nulls=True, **kwargs)

            else:
                raise TypeError('Unknown table type: {0}'.format(table_structure.type))

        except ValueError as e:
            six.raise_from(ValueError("Unable to convert field '{0}' to data_type '{1}': {2}"
                                      .format(field['name'], field.data_type(), repr(e.args[0]))), None)

        # Save a preliminary version of each field
        # (cast to its initial data type but without any scaling or other adjustments)
        extracted_fields.append(PDS_array(extracted_data, field))

    # Delete table byte data to save RAM now that it is no longer needed (all fields have been extracted)
    del table_byte_data

    # Finish processing (scale and decoding), create the table's structured data array and set fields
    table_structure.data = new_table(extracted_fields, no_scale=no_scale, decode_strings=decode_strings,
                                     masked=masked, copy=False).data


def read_table(full_label, table_label, data_filename,
               lazy_load=False, no_scale=False, decode_strings=False):
    """ Create the `TableStructure`, containing label, data and meta data for a PDS4 Table from a file.

    Used for all forms of PDS4 Tables (i.e., Table_Character, Table_Binary and Table_Delimited).

    Parameters
    ----------
    full_label : Label
        The entire label for a PDS4 product, from which *table_label* originated.
    table_label : Label
        Portion of label that defines the PDS4 table data structure.
    data_filename : str or unicode
        Filename, including the full path, of the data file that contains the data for this table.
    lazy_load : bool, optional
        If True, does not read-in the data of this table until the first attempt to access it.
        Defaults to False.
    no_scale : bool, optional
        If True, returned data will not be adjusted according to the offset and scaling factor.
        Defaults to False.
    decode_strings : bool, optional
        If True, strings data types contained in the returned data will be decoded to
        the ``unicode`` type in Python 2, and to the ``str`` type in Python 3. If False,
        leaves string types as byte strings. Defaults to False.

    Returns
    -------
    TableStructure
        An object representing the table; contains its label, data and meta data.

    Raises
    ------
    TypeError
        Raised if called on a non-table according to *table_label*.
    """

    # Skip over data structure if its not actually a supported Table
    if table_label.tag not in PDS4_TABLE_TYPES:
        raise TypeError('Attempted to read_table() on a non-table: ' + table_label.tag)

    # Create the data structure for this table
    table_structure = TableStructure.from_file(data_filename, table_label, full_label,
                                               lazy_load=lazy_load, no_scale=no_scale,
                                               decode_strings=decode_strings)

    return table_structure
