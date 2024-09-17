from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import datetime as dt

import numpy as np

from ..utils.compat import np_unicode
from ..utils.deprecation import rename_parameter
from ..utils.logging import logger_init

from ..extern import six
from ..extern.six.moves import builtins

# Initialize the logger
logger = logger_init()

#################################

PDS_NUMERIC_TYPES = {
    'IEEE754MSBSingle': ('big', 'float32',    'float'),
    'IEEE754MSBDouble': ('big', 'float64',    'float'),
    'SignedMSB2':       ('big', 'int16',      'int'),
    'SignedMSB4':       ('big', 'int32',      'int'),
    'SignedMSB8':       ('big', 'int64',      'int'),
    'UnsignedMSB2':     ('big', 'uint16',     'int'),
    'UnsignedMSB4':     ('big', 'uint32',     'int'),
    'UnsignedMSB8':     ('big', 'uint64',     'int'),
    'ComplexMSB8':      ('big', 'complex64',  'complex'),
    'ComplexMSB16':     ('big', 'complex128', 'complex'),

    'IEEE754LSBSingle': ('little', 'float32',    'float'),
    'IEEE754LSBDouble': ('little', 'float64',    'float'),
    'SignedLSB2':       ('little', 'int16',      'int'),
    'SignedLSB4':       ('little', 'int32',      'int'),
    'SignedLSB8':       ('little', 'int64',      'int'),
    'UnsignedLSB2':     ('little', 'uint16',     'int'),
    'UnsignedLSB4':     ('little', 'uint32',     'int'),
    'UnsignedLSB8':     ('little', 'uint64',     'int'),
    'ComplexLSB8':      ('little', 'complex64',  'complex'),
    'ComplexLSB16':     ('little', 'complex128', 'complex'),

    'SignedByte':       ('little', 'int8',  'int'),
    'UnsignedByte':     ('little', 'uint8', 'int'),

    'ASCII_Real':                ('native', 'float64', 'float'),
    'ASCII_Integer':             ('native', 'int64',   'int'),
    'ASCII_NonNegative_Integer': ('native', 'uint64',  'int'),
    'ASCII_Numeric_Base2':       ('native', 'object',  'int'),
    'ASCII_Numeric_Base8':       ('native', 'object',  'int'),
    'ASCII_Numeric_Base16':      ('native', 'object',  'int'),
    'ASCII_Boolean':             ('native', 'bool_',   'bool'),
}

PDS4_DATE_TYPES = {
    'ASCII_Date_DOY':          ('native', 'datetime64[D]',  'date',     '%Y-%j'),
    'ASCII_Date_YMD':          ('native', 'datetime64[D]',  'date',     '%Y-%m-%d'),
    'ASCII_Date_Time_DOY':     ('native', 'datetime64[us]', 'datetime', '%Y-%jT%H:%M:%S.%f'),
    'ASCII_Date_Time_YMD':     ('native', 'datetime64[us]', 'datetime', '%Y-%m-%dT%H:%M:%S.%f'),
    'ASCII_Date_Time_DOY_UTC': ('native', 'datetime64[us]', 'datetime', '%Y-%jT%H:%M:%S.%f'),
    'ASCII_Date_Time_YMD_UTC': ('native', 'datetime64[us]', 'datetime', '%Y-%m-%dT%H:%M:%S.%f'),
    'ASCII_Time':              ('native', 'datetime64[us]', 'time',     '%H:%M:%S.%f')
}


def pds_to_numpy_type(data_type=None, data=None, field_length=None, decode_strings=False, decode_dates=False,
                      scaling_factor=None, value_offset=None, include_endian=True, include_unscaled=False):
    """ Obtain a NumPy dtype for PDS4 data.

    Either *data* or *data_type* must be provided.

    Notes
    -----
    For certain data (such as ASCII_Integer), there are a number of NumPy dtypes (e.g. int8, int32, int64)
    that could be used. If only the PDS4 data type is given, the returned dtype will be large enough to store
    any possible valid value according to the PDS4 Standard. However, if the *data* parameter is specified,
    then the obtained dtype will not be any larger than needed to store exactly that data (plus any
    scaling/offset specified).

    Parameters
    ----------
    data_type : str, unicode or PDSdtype, optional
        A PDS4 data type. If *data* is omitted, the obtained NumPy data type is based on this value
        (see notes).
    data : array_like, optional
        A data array. If *data_type* is omitted, the obtained NumPy data type is based on this value
        (see notes).
    field_length : int, optional
        If given, and the returned dtype is a form of character, then it will include the number of
        characters. Takes priority over length of *data* when given.
    decode_strings : bool, optional
        If True, and the returned dtype is a form of character, then the obtained dtype will be a form of
        unicode. If False, then for character data the obtained dtype will remain byte strings. If *data* is
        given and is unicode, then this setting will be ignored and unicode dtype will be returned. If
        *data_type* is given and refers to bit-strings, then this setting will be ignored and a byte string
        dtype will be returned. Defaults to False.
    decode_dates: bool, optional
        If True, then the returned dtype will be a datetime64 when *data_type* is both given and is a form of
        date and/or time. If False, then the returned dtype will be a form of character according to *decode_strings*.
        If *data* is given, then this setting will be ignored. Defaults to False.
    scaling_factor : int, float or None, optional
        PDS4 scaling factor. If given, the returned dtype will be large enough to contain data scaled by
        this number. Defaults to None, indicating a value of 1.
    value_offset : int, float or None, optional
        PDS4 value offset. If given, the returned dtype will be large enough to contain data offset by this
        number. Defaults to None, indicating a value of 0.
    include_endian : bool, optional
        If True, the returned dtype will contain an explicit endianness as specified by the PDS4 data type.
        If False, the dtype will not specifically indicate the endianness, typically implying same endianness
        as the current machine. Defaults to True.
    include_unscaled : bool, optional
        If True, and when combined with *data*, *scaling_factor* and/or *value_offset*, the returned dtype
        will not only be large enough to store the scaled data but also large enough to store the unscaled
        *data*. Defaults to False.

    Returns
    -------
    np.dtype
        A NumPy dtype that can store the data described by the input parameters.
    """

    if (data is None) and (data_type is None):
        raise ValueError('Either data or a data_type must be provided.')

    # Ensure *data_type* is a PDSdtype when given
    if data_type is not None:
        data_type = PDSdtype(data_type)

    # Detect if dealing with bit strings
    is_bitstring_data = (data_type is not None) and data_type.issubtype('BitString')

    # Get either a character or the initial unscaled numeric data type from data
    if data is not None:
        data = np.asanyarray(data)
        is_character_data = np.issubdtype(data.dtype, np.character)
        is_datetime_data = np.issubdtype(data.dtype, np.datetime64)

        # Get dtype for character data (from data)
        if is_character_data:
            unicode_requested = decode_strings and not is_bitstring_data
            dtype = 'U' if (np.issubdtype(data.dtype, np_unicode) or unicode_requested) else 'S'

            if field_length is not None:
                dtype += str(field_length)
            else:
                field_length = data.dtype.itemsize
                dtype += str(field_length)

        # Get dtype for numeric data (from data)
        else:
            dtype = data.dtype
            if not include_endian:
                dtype = dtype.newbyteorder('native')

    # Get either a character or the initial unscaled numeric data type from meta data
    else:
        numeric_types = PDS_NUMERIC_TYPES.get(data_type.name, None)
        datetime_types = PDS4_DATE_TYPES.get(data_type.name, None)
        is_datetime_data = (datetime_types is not None) and decode_dates
        is_character_data = (numeric_types is None) and (not is_datetime_data)

        # Get dtype for character data (from meta data)
        if is_character_data:
            dtype = 'U' if (decode_strings and not is_bitstring_data) else 'S'

            if field_length is not None:
                dtype += str(field_length)

        # Get dtype for numeric and datetime data (from meta data)
        else:

            types = datetime_types if is_datetime_data else numeric_types
            dtype = np.dtype(types[1])
            if include_endian:
                dtype = dtype.newbyteorder(types[0])

    # Get scaled data type for numeric data (if necessary)
    if (not is_character_data) and (not is_datetime_data):

        kwargs = {
            'scaling_factor': scaling_factor,
            'value_offset': value_offset,
            'include_unscaled': include_unscaled
        }
        has_scaling = (scaling_factor is not None) or (value_offset is not None)

        if data is not None:

            # Find the minimum possible dtype for ASCII integers
            if (data_type is not None) and data_type.issubtype('ASCII') and is_pds_integer_data(data=data):
                dtype = get_min_integer_numpy_type(data)

            # Scale dtype if requested
            if has_scaling:
                dtype = get_scaled_numpy_type(data=data, **kwargs)

        # Scale dtype if requested
        elif has_scaling:
            dtype = get_scaled_numpy_type(data_type=data_type, **kwargs)

    return np.dtype(dtype)


def pds_to_builtin_type(data_type=None, data=None, decode_strings=False, decode_dates=False,
                        scaling_factor=None, value_offset=None):
    """ Obtain a Python __builtin__ data type for PDS4 data.

    Either *data* or *data_type* must be provided.

    Parameters
    ----------
    data_type : str, unicode or PDSdtype, optional
        A PDS4 data type. If *data* is omitted, the obtained builtin data type is based on this value.
    data : array_like, optional
        A data array. If *data_type* is omitted, the obtained builtin data type is based on this value.
    decode_strings : bool, optional
        If True, and the returned data type is a form of character, then the obtained data type will be
        either ``str`` (Python 3) or ``unicode`` (Python 2). If False, then for character data
        the obtained data type will remain byte strings. If *data* is given and is unicode, then this
        setting will be ignored and unicode data type will be returned. If *data_type* is given and
        refers to bit-strings, then this setting will be ignored and a byte string data type will be returned.
        Defaults to False.
    decode_dates: bool, optional
        If True, then the returned data type will be a form of date/time when *data_type* is both given and
        is a form of date and/or time. If False, then the returned data type will be a form of character
        according to *decode_strings*. If *data* is given, then this setting will be ignored. Defaults to False.
    scaling_factor : int, float or None, optional
        PDS4 scaling factor. If given, the returned data type will be large enough to contain data scaled by
        this number. Defaults to None, indicating a value of 1.
    value_offset : int, float or None, optional
        PDS4 value offset. If given, the returned data type will be large enough to contain data offset
        by this number. Defaults to None, indicating a value of 0.

    Returns
    -------
    str, unicode, bytes, int, float, bool, complex
        A builtin data type that can store the data described by the input parameters.
    """

    if (data is None) and (data_type is None):
        raise ValueError('Either data or a data_type must be provided.')

    # Ensure *data_type* is a PDSdtype when given
    if data_type is not None:
        data_type = PDSdtype(data_type)

    # Detect if dealing with bit strings
    is_bitstring_data = (data_type is not None) and data_type.issubtype('BitString')

    # Get unscaled type from data
    if data is not None:
        data = np.asanyarray(data)
        is_character_data = np.issubdtype(data.dtype, np.character)
        is_datetime_data = np.issubdtype(data.dtype, np.datetime64)

        if is_character_data:
            unicode_requested = decode_strings and not is_bitstring_data
            _type = six.text_type if (np.issubdtype(data.dtype, np_unicode) or unicode_requested
                                      ) else six.binary_type
        else:
            _type = type(np.asscalar(data[0]))

    # Get unscaled type from meta data
    else:
        numeric_types = PDS_NUMERIC_TYPES.get(data_type.name, None)
        datetime_types = PDS4_DATE_TYPES.get(data_type.name, None)
        is_datetime_data = (datetime_types is not None) and decode_dates
        is_character_data = (numeric_types is None) and (not is_datetime_data)

        if is_character_data:
            _type = six.text_type if (decode_strings and not is_bitstring_data) else six.binary_type

        elif is_datetime_data:
            _type = getattr(dt, datetime_types[2])

        else:
            _type = getattr(builtins, numeric_types[2])

    # Get scaled data type for numeric data (if necessary)
    if (not is_character_data) and (not is_datetime_data):

        has_scaling = (scaling_factor is not None) or (value_offset is not None)
        kwargs = {'scaling_factor': scaling_factor, 'value_offset': value_offset}

        if has_scaling:

            if data is not None:
                dtype = get_scaled_numpy_type(data=data, **kwargs)
            else:
                dtype = get_scaled_numpy_type(data_type=data_type, **kwargs)

            _type = type(np.asscalar(np.zeros(1, dtype)))

    return _type


def numpy_to_pds_type(dtype, ascii_numerics=False):
    """ Obtain a PDS4 data type from a NumPy dtype.

    This method only provides a plausible match. For any data type which is string-like, it will always
    return that the PDS4 data type is a string when in fact this have been any type interpreted by this
    application as strings (e.g. LIDs, dates, times, etc). Even for numeric data, the match is not exact
    because the same NumPy dtype is used for multiple PDS4 data types (for example ASCII_Numeric_Base
    and ASCII_Integer both have integer NumPy dtypes).

    Parameters
    ----------
    dtype : np.dtype
        A NumPy data type.
    ascii_numerics
        If True, the returned PDS4 data type will be an ASCII numeric type if the input dtype is numeric
        or boolean. If False, the returned PDS4 data type will be a binary type. Defaults to False.

    Returns
    -------
    PDSdtype
        A PDS4 data type that could plausibly (see description above) correspond to the input dtype.
    """

    # For string dtypes
    if np.issubdtype(dtype, np_unicode):
        data_type = 'UTF8_String'

    elif np.issubdtype(dtype, np.string_):
        data_type = 'ASCII_String'

    # For datetime dtypes
    elif np.issubdtype(dtype, np.datetime64):
        data_type = 'ASCII_Date_Time_YMD'

    # For numeric dtypes
    else:

        # Get numeric ASCII types. We obtain these from builtin portion because if we attempt to match
        # e.g. 'int16' to 'int64' it would fail but for ASCII types this should succeed.
        ascii_types = dict((value[2], key)
                           for key, value in six.iteritems(PDS_NUMERIC_TYPES)
                           if ('ASCII' in key) and ('Numeric_Base' not in key))

        # Get numeric non-ASCII types, including the correct endianness.
        non_ascii_types = dict((np.dtype(value[1]).newbyteorder(value[0]), key)
                               for key, value in six.iteritems(PDS_NUMERIC_TYPES)
                               if ('ASCII' not in key) and ('Numeric_Base' not in key))

        if ascii_numerics:

            builtin_type = type(np.asscalar(np.array(0, dtype=dtype))).__name__
            data_type = ascii_types.get(builtin_type, None)

        else:
            data_type = non_ascii_types.get(dtype, None)

    # Raise error if we were unable to find a match
    if data_type is None:

        raise ValueError("Unable to convert NumPy data type, '{0}', to a PDS4 {1} data type.".
                         format(dtype, 'ASCII' if ascii_numerics else 'binary'))

    return PDSdtype(data_type)


def pds_to_numpy_name(name):
    """ Create a NumPy field name from a PDS4 field name.

    Parameters
    ----------
    name : str or unicode
        A PDS4 field name.

    Returns
    -------
    str
        A NumPy-compliant field name.
    """

    # We encode to UTF-8 because under Python 2 NumPy does not accept unicode. We replace
    # the colon by an underscore because under Python 3 this seems to cause an error when using
    # ``recarray.__new__`` with the ``buf`` keyword.

    name = name.replace(':', '_')
    if six.PY2:
        name = name.encode('utf-8')

    return name


def data_type_convert_array(data_type, byte_string):
    """
    Cast binary data in the form of a byte_string to a flat array having proper dtype for *data_type*.

    Parameters
    ----------
    data_type : str, unicode or PDSdtype
        The PDS4 data type that the data should be cast to.
    byte_string : str, bytes or buffer
        PDS4 byte string data for an array data structure or a table binary field.

    Returns
    -------
    np.ndarray
        Array-like view of the data cast from a byte string into values having the indicated data type.
        Will be read-only if underlying *byte_string* is immutable.
    """

    # Determine data type needed for this binary field
    dtype = pds_to_numpy_type(data_type)

    # Convert from the byte string into the actual data type
    byte_string = np.frombuffer(byte_string, dtype=dtype)

    return byte_string


@rename_parameter('1.3', 'mask_numeric_nulls', 'mask_nulls')
def data_type_convert_table_ascii(data_type, data, mask_nulls=False, decode_strings=False):
    """
    Cast data originating from a PDS4 Table_Character or Table_Delimited data structure in the form
    of an array_like[byte_string] to an array with the proper dtype for *data_type*. Most likely this
    data is a single Field, or a single repetition of a Field, since different Fields have different
    data types.

    Parameters
    ----------
    data_type : str, unicode or PDSdtype
        The PDS4 data type that the data should be cast to.
    data : array_like[str or bytes]
        Flat array of PDS4 byte strings from a Table_Character data structure.
    mask_nulls : bool
        If True, then *data* may contain empty values for a numeric and boolean *data_type*'s. If such
        nulls are found, they will be masked out and a masked array will be returned. Defaults to False,
        in which case an exception will be raised should an empty value be found in such a field.
    decode_strings : bool, optional
        If True, and the returned dtype is a form of character, then the obtained dtype will be a form of
        unicode. If False, then for character data the obtained dtype will remain byte strings. Defaults
        to False.

    Returns
    -------
    np.ndarray
        Data cast from a byte string array into a values array having the right data type.
    """

    # Ensure *data_type* is a PDSdtype
    data_type = PDSdtype(data_type)

    # Obtain dtype that these data will take
    dtype = pds_to_numpy_type(data_type, decode_strings=decode_strings)

    # Stores mask and fill value used when *mask_nulls* is enabled
    # (a fill value of None uses NumPy's default for the data type)
    mask_array = np.zeros(0)
    fill_value = 0

    # Fill any empty numeric or bool values with a 0, if requested
    if not np.issubdtype(dtype, np.character) and mask_nulls:

        mask_array = np.zeros(len(data), dtype='bool')
        data = np.array(data, dtype='object', copy=True)

        # Assign mask to True where necessary (so that we remember which values need to be masked),
        # then set value in data array to 0 (this value will be masked). The syntax here is used
        # to speed up operations.
        for i, datum in enumerate(data):
            if datum.strip() == b'':
                mask_array[i] = True

        data[mask_array] = six.ensure_binary(str(fill_value))

    # Special handling for boolean due to e.g. bool('false') = True
    # and that in NumPy 2.0+ string arrays typecast to bool set
    # all non-empty strings as True.
    if data_type == 'ASCII_Boolean':

        # Replace 'true' and 'false' with 1 and 0
        data = b'@'.join(data)
        data = data.replace(b'true', b'1')
        data = data.replace(b'false', b'0')
        data = data.split(b'@')

        try:
            data = np.asarray(data).astype(np.uint8, copy=False) \
                                   .astype(dtype, copy=False)
        except TypeError:
            data = np.asarray(data).astype(np.uint8).astype(dtype)

    # Convert ASCII numerics into their proper data type
    elif not np.issubdtype(dtype, np.character):

        # We convert binary, octal and hex integers to base 10 integers on the assumption that
        # it is more likely a user will want to do math with them so we cannot store them as strings
        # and to base 10 in order to be consistent on the numerical meaning of all values
        numeric_base = {'ASCII_Numeric_Base2': 2,
                        'ASCII_Numeric_Base8': 8,
                        'ASCII_Numeric_Base16': 16,
                        }.get(data_type.name, 10)

        # We can use NumPy to convert floats to a numeric type, but not integers. The latter is
        # because in case an integer does not fit into a NumPy C-type (since some ascii integer types
        # are unbounded in PDS4), there appears to be no method to tell NumPy to convert each string
        # to be a numeric Python object. Therefore we use pure Python to convert to numeric Python
        # objects (i.e, int), and then later convert the list into a NumPy array of numeric Python
        # objects.
        if np.issubdtype(dtype, np.floating):

            # Convert ASCII_Reals to numeric type
            data = np.asarray(data, dtype=dtype)

        else:

            # Make a copy such that original data is unmodified (if we did not already make a copy above)
            if not mask_nulls:
                data = np.array(data, dtype='object', copy=True)

            # Convert ASCII_Integers to numeric type. The syntax here is used to speed up operations,
            # especially for delimited tables with many empty values, by explicitly looping over and
            # casting only non-zero values.
            for i in np.nditer(np.where(data != '0'), flags=['zerosize_ok']):
                data[i] = int(data[i], numeric_base)

            data[data == '0'] = 0

            # Cast down numeric base integers if possible
            if numeric_base != 10:
                dtype = get_min_integer_numpy_type(data)

    # Decode PDS4 ASCII and UTF-8 strings into unicode/str
    elif decode_strings:
        data = decode_bytes_to_unicode(data)

    # Convert to numpy array (anything that was not already converted above)
    data = np.asanyarray(data, dtype=dtype)

    # Assign mask and full_value to numeric/bool data with nulls as needed
    if mask_nulls and mask_array.any():
        data = data.view(np.ma.masked_array)
        data.mask = mask_array
        data.set_fill_value(fill_value)

    # Emit memory efficiency warning if necessary
    if dtype == 'object':
        logger.warning('Detected integer Field with precision exceeding memory efficient case.')

    return data


def data_type_convert_table_binary(data_type, data, decode_strings=False):
    """
    Cast data originating from a PDS4 Table_Binary data structure in the form of an array_like[byte_string]
    to an array with the proper dtype for *data_type*. Most likely this data is a single Field, or a
    single repetition of a Field, since different Fields have different data types.

    Parameters
    ----------
    data_type : str, unicode or PDSdtype
        The PDS4 data type that the data should be cast to.
    data : array_like[str or bytes]
        Flat array of PDS4 byte strings from a Table_Binary data structure.
    decode_strings : bool, optional
        If True, and the returned dtype is a form of character, then the obtained dtype will be a form of
        unicode. If False, then for character data the obtained dtype will remain byte strings. Defaults
        to False.

    Returns
    -------
    np.ndarray
        Data cast from a byte string array into a values array having the right data type.
    """

    # Ensure *data_type* is a PDSdtype
    data_type = PDSdtype(data_type)

    # Convert binary data types
    if data_type.issubtype('binary'):

        # Join data array-like back into a byte_string, then cast to bytearray to ensure mutability
        byte_string = bytearray(b''.join(data))

        data = data_type_convert_array(data_type, byte_string)

    # Convert character table data types
    else:
        data = data_type_convert_table_ascii(data_type, data, decode_strings=decode_strings)

    return data


def data_type_convert_dates(data, data_type=None, mask_nulls=False):
    """
    Cast an array of datetime strings originating from a PDS4 Table data structure to an array having
    NumPy datetime64 dtype.

    Parameters
    ----------
    data : array_like[str or bytes]
        Flat array of datetime strings in a PDS4-compatible form.
    data_type : str, unicode or PDSdtype, optional
        The PDS4 data type for the *data*. If omitted, will be obtained from the meta_data of *data*.
    mask_nulls : bool, optional
        If True, then *data* may contain empty values. If such nulls are found, they will be masked out and
        a masked array will be returned. Defaults to False, in which case an exception will be raised should
        an empty value be found.

    Returns
    -------
    np.ndarray, np.ma.MaskedArray or subclass
        Data cast from a string-like array to a datetime array. If null values are found, an
        ``np.ma.MaskedArray`` or subclass view will be returned. When the input is an instance of PDS_array,
        the output will be as well.
    """

    from .data import PDS_array

    # Ensure data is a NumPy array
    data = np.asanyarray(data)

    # Determine the PDS4 data type of our data
    meta_data = getattr(data, 'meta_data', {})

    if (data_type is None) and (not meta_data):
        raise ValueError('Input must either contain meta_data, or *data_type* must be given.')

    data_type = PDSdtype(meta_data.data_type() if (data_type is None) else data_type)
    if not data_type.issubtype('datetime'):
        raise TypeError('Unknown PDS4 Date type: {0}'.format(data_type))

    # Determine all possible date formats allowed by the PDS4 data type
    # (The PDS4 standard allows truncating the format string of each date format until only a year remains.)
    dtype = pds_to_numpy_type(data_type, decode_dates=True)
    format = PDS4_DATE_TYPES[data_type.name][3]
    formats = [format]
    chars = ['.', ':', 'T', '-']
    idx = 0

    while idx < len(chars):

        char = chars[idx]
        prev_format = formats[-1]
        new_format = (prev_format.rsplit(char, 1))[0]

        if new_format not in formats:
            formats.append(new_format)

        if new_format.count(char) == 0:
            idx += 1

    # Build a dict where each key corresponds to the length of a datetime for that format, and each value
    # corresponds to the format. I.e., allow translation between datetime length and its format.
    symbol_lengths = {'%Y': 4, '%j': 3, '%m': 2, '%d': 2, '%H': 2, '%M': 2, '%S': 2, '.%f': 0}
    format_lengths = {}

    for _format in formats:

        _edited_format = _format
        for k, v in six.iteritems(symbol_lengths):

            if k in _edited_format:
                _edited_format = _edited_format.replace(k,  ' ' * v)

        format_lengths[len(_edited_format)] = _format

    # Adjust above format length dict to account for the variable number of fraction seconds (up to 6 allowed)
    if '%f' in format:

        fraction_length = max(format_lengths.keys()) + 2
        for i in range(0, 6):
            format_lengths[fraction_length+i] = format

    # Decode input from bytes into strings, when necessary
    if (not six.PY2) and (data.dtype.char == 'S'):
        data = decode_bytes_to_unicode(data)

    # Determine the format of the first data point
    # (We strip any leading/trailing spaces and UTC indicator. The latter would double our search space.)
    first_datum = data[0].strip(' Z')
    format_guess = format_lengths.get(len(first_datum), '')

    # Try assuming that all dates have the same format and no special constants
    # (speeding up the conversion, if true)
    try:

        dates = np.empty(len(data), dtype=dtype)

        for i, datum in enumerate(data):
            datum = datum.strip(' Z')
            dates[i] = dt.datetime.strptime(datum, format_guess)

    # If dates do not all have same format or have Special_Constants
    except ValueError:

        # Search for and mask any Special_Constants
        special_constants = meta_data.get('Special_Constants', {})

        if mask_nulls:
            special_constants['null_constant'] = ''

        data = mask_special_constants(data, special_constants=special_constants, mask_strings=True, copy=False)

        try:

            dates = np.empty(len(data), dtype=dtype)

            # If there are Special_Constants. Dates may also different formats, length is used for each
            # datetime string to determine possible format.
            if isinstance(data, np.ma.MaskedArray) and data.mask.any():

                dates = dates.view(np.ma.MaskedArray)
                dates.mask = data.mask

                for i, datum in enumerate(data):

                    if not isinstance(datum, np.ma.core.MaskedConstant):
                        datum_strip = datum.strip(' Z')
                        date = dt.datetime.strptime(datum_strip, format_lengths[len(datum_strip)])

                        dates[i] = np.datetime64(date)

            # If there are no Special_Constants, but dates have different formats then use length of each
            # datetime string to determine possible format. (This is mostly an optimized-case, which runs
            # more than 2x speed.)
            else:

                for i, datum in enumerate(data):
                    datum_strip = datum.strip(' Z')
                    date = dt.datetime.strptime(datum_strip, format_lengths[len(datum_strip)])

                    dates[i] = np.datetime64(date)

        except (ValueError, KeyError):
            raise ValueError("Unable to format date value, '{0}', according to PDS4 {1} data type.".
                             format(datum.strip(), data_type))

    # Convert output back to PDS_array as necessary
    if meta_data:
        dates = PDS_array(dates, meta_data)

    return dates


def apply_scaling_and_value_offset(data, scaling_factor=None, value_offset=None, special_constants=None):
    """ Applies scaling factor and value offset to *data*.

    Data is modified in-place, if possible. Data type may change to prevent numerical overflow
    if applying scaling factor and value offset would cause one.

    Parameters
    ----------
    data : array_like
        Any numeric PDS4 data.
    scaling_factor : int, float or None, optional
        PDS4 scaling factor to apply to the array. Defaults to None, indicating a value of 1.
    value_offset : int, float or None, optional
        PDS4 value offset to apply to the array. Defaults to None, indicating a value of 0.
    special_constants : dict, optional
        If provided, the keys correspond to names and values correspond to numeric values for
        special constants. Those particular values will not be scaled or offset.

    Returns
    -------
    np.ndarray or subclass
        *data* with *scaling_factor* and *value_offset* applied, potentially with a new dtype if necessary
        to fit new values.
    """

    no_scaling = (scaling_factor is None) or (scaling_factor == 1)
    no_offset = (value_offset is None) or (value_offset == 0)

    # Ensure data is a NumPy array
    data = np.asanyarray(data)

    # Skip taking computationally intensive action if no adjustment is necessary
    if no_scaling and no_offset:
        return data

    # Mask Special_Constants values so that scaling/offset does not affect them
    if special_constants is not None:
        mask = np.ma.getmask(data) if np.ma.is_masked(data) else None
        data = mask_special_constants(data, special_constants=special_constants)

    # Adjust data type to prevent overflow on application of scaling factor and value offset, if necessary
    data = adjust_array_data_type(data, scaling_factor, value_offset)

    # Apply scaling factor and value offset
    # (workaround inability of NumPy 2.0+ to add / multiply in cases where
    #  value on right of operand is out-of-bounds of dtype, see PR #99)
    if not no_scaling:

        scale_dtype = None
        if isinstance(scaling_factor, six.integer_types):
            scale_dtype = get_min_integer_numpy_type([scaling_factor])

        data *= np.array(scaling_factor, dtype=scale_dtype)

    if not no_offset:

        offset_dtype = None
        if isinstance(value_offset, six.integer_types):
            offset_dtype = get_min_integer_numpy_type([value_offset])

        data += np.array(value_offset, dtype=offset_dtype)

    # Cast down integers if possible
    # (see note in `adjust_array_data_type` for why this can be necessary)
    if is_pds_integer_data(data=data):

        final_dtype = get_min_integer_numpy_type(data)

        try:
            data = data.astype(final_dtype, copy=False)
        except TypeError:
            data = data.astype(final_dtype)

    # Restore the original mask if necessary, removing any additional mask applied above for Special_Constants
    if (special_constants is not None) and (mask is not None):
        data.mask = mask

    return data


def adjust_array_data_type(array, scaling_factor=None, value_offset=None):
    """
    Converts the input *array* into a new large enough data type if adjusting said array as-is by
    *scaling_factor* or *value_offset* would result in an overflow. This can be necessary both
    if the array is data from a PDS4 Array or a PDS4 Table, so long as it has a scaling factor or value
    offset associated with it.

    Notes
    -----
    The resultant dtype is not necessarily the smallest the data will fit into while preserving
    precision after applying scaling / offset. For example, for integers, the value of *array*
    prior to scaling / offset must also still fit the data type, and this can be larger than
    the scaled / offset data type if that operation makes the final value smaller.

    Parameters
    ----------
    array : array_like
        Any PDS4 numeric data.
    scaling_factor : int, float or None, optional
        PDS4 scaling factor to apply to the array. Defaults to None, indicating a value of 1.
    value_offset : int, float or None, optional
        PDS4 value offset to apply to the array. Defaults to None, indicating a value of 0.

    Returns
    -------
    np.ndarray or subclass
        Original *array* modified to have a new data type if necessary or unchanged if otherwise.
    """

    new_dtype = get_scaled_numpy_type(data=array,
                                      scaling_factor=scaling_factor,
                                      value_offset=value_offset,
                                      include_unscaled=True)

    if new_dtype == 'object':
        logger.warning('Detected integer Field with precision exceeding memory efficient case.')

    # Only adjust if the data types are not the same, and if the adjustment would not result in loss of
    # precision. The latter also prevents us from adjusting data that becomes smaller on application of
    # scaling, because adjusting it now (while it is larger) would result in an overflow.
    if (array.dtype.name != new_dtype.name) and (array.dtype != 'object') and (
            array.dtype.kind != new_dtype.kind or array.dtype.itemsize < new_dtype.itemsize):

        try:
            array = array.astype(new_dtype, copy=False)
        except TypeError:
            array = array.astype(new_dtype)

    return array


def get_scaled_numpy_type(data_type=None, data=None, scaling_factor=None, value_offset=None,
                          include_unscaled=False):
    """ Obtain the NumPy dtype that would be necessary to store PDS4 data once that data has been scaled.

    When scaling data, the final data type is likely going to be different from the original data type
    it has. (E.g. if you multiply integers by a float, then the final data type will be float.) This method
    determines what that final data type will have to be when given the initial data type and the scaling
    and offset values.

    Notes
    -----
    For masked data, the output type will be large enough to store the masked data values as if they had
    been scaled/offset. This is because NumPy documentation notes that masked data are not guaranteed
    to be unaffected by arithmetic operations, only that every attempt will be made to do so.

    Parameters
    ----------
    data_type : str, unicode or PDSdtype, optional
        If given, specifies the initial PDS4 data type that the unscaled data has or would have.
    data : array_like or None, optional
        If given, an array of data. When given, the initial data type for the unscaled data will be taken
        from this array and *data_type* ignored. For some ASCII data types in PDS4, the exact necessary data
        type (scaled or unscaled) can only be obtained when the data is already known. If data is not given,
        a data type sufficient (but possibly larger than necessary) to store the data will be returned.
        Defaults to None.
    scaling_factor : int, float, or None
        PDS4 scaling factor that will later be applied to the data. Defaults to None, indicating a value of 1.
    value_offset : int, float, or None
        PDS4 value offset that will later be applied to the data. Defaults to None, indicating a value of 0.
    include_unscaled : bool, optional
        If True, and when combined with *data*, *scaling_factor* and/or *value_offset*, the returned dtype
        will not only be large enough to store the scaled data but also large enough to store the unscaled
        *data*. Defaults to False.

    Returns
    -------
    np.dtype
        A NumPy dtype large enough to store the data if it has had *scaling_factor* and *value_offset* applied.
        If *include_unscaled*, the dtype is also large enough to store *data* prior to scaling and offset.
    """

    if (data is None) and (data_type is None):
        raise ValueError('Either data or a data_type must be provided.')

    if data is None:
        data_dtype = pds_to_numpy_type(data_type)

    else:
        data = np.asanyarray(data)
        data_dtype = data.dtype

    data_is_float = np.issubdtype(data_dtype, np.floating)
    scaling_is_float = isinstance(scaling_factor, float)
    offset_is_float = isinstance(value_offset, float)

    no_scaling = (scaling_factor is None) or (scaling_factor == 1)
    no_offset = (value_offset is None) or (value_offset == 0)

    # For values that have no value_offset or scaling_factor we can return the original data type
    if no_scaling and no_offset:
        new_dtype = data_dtype

    # Data should be double precision
    elif data_is_float or scaling_is_float or offset_is_float:
        new_dtype = 'float64'

    # Data should be integer
    elif is_pds_integer_data(data=data, pds_data_type=data_type):

        # Integers should be fixed-precision, because we do not necessarily know they can be 8-bytes
        # (see e.g. ASCII_Numeric_Base*)
        if data is None:
            new_dtype = 'object'

        # Determine number of bytes needed for integers from *data*
        else:

            # For ints, we find minimum size necessary for data not to overflow
            if scaling_factor is None:
                scaling_factor = 1

            if value_offset is None:
                value_offset = 0

            # Find min and max data (so we do not have to multiply all data, which is slower)
            # Note: cast to int must stay, otherwise NumPy integers may overflow
            min_data = int(data.view(np.ndarray).min())
            max_data = int(data.view(np.ndarray).max())
            min_scaled_data = min_data * scaling_factor + value_offset
            max_scaled_data = max_data * scaling_factor + value_offset

            # Obtain type necessary to store all integers
            if include_unscaled:
                check_values = [min_data, max_data, min_scaled_data, max_scaled_data]
            else:
                check_values = [min_scaled_data, max_scaled_data]

            new_dtype = get_min_integer_numpy_type(check_values)

    else:
        raise ValueError('Attempted to scale data which does not appear scalable.')

    return np.dtype(new_dtype)


def decode_bytes_to_unicode(array):
    """ Decodes each byte string in the array into unicode.

    Parameters
    ----------
    array : array_like
        An array containing only byte strings (``str`` in Python 2, ``bytes`` in Python 3).

    Returns
    -------
    np.ndarray or subclass
        An array in which each element of input *array* has been decoded to unicode.
    """

    return np.char.decode(array, 'utf-8')


def mask_special_constants(data, special_constants, mask_strings=False, copy=False):
    """ Mask out special constants in an array.

    Notes
    -----
    The match between special constant value and data value (to mask it out) in this method is simplistic.
    For numeric values, it is based on the NumPy implementation of equality. For string values, the match is
    done by trimming leading/trailing whitespaces in both data value and special constant, then comparing for
    exact equality. Currently the PDS4 Standard does not provide enough clarity on how Special_Constant
    matching should truly be done.

    Parameters
    ----------
    data : array_like
        An array of data in which to mask out special constants.
    special_constants : dict
        A dictionary, where keys are the names of the special constants, and the values will be masked
        out.
    mask_strings : bool, optional
        If True, character data will also be masked out if it has special constants. If False, only
        numeric data will be masked out. Defaults to False.
    copy : bool, optional
        If True, the returned masked data is a copy. If False, a view is returned instead. Defaults to False.

    Returns
    -------
    np.ma.MaskedArray, np.ndarray or subclass
        If data to be masked is found, an ``np.ma.MaskedArray`` or subclass view (preserving input class
        if it was already a subclass of masked arrays). Otherwise the input *data* will be returned.
    """

    data = np.asanyarray(data)

    # Skip taking any action if there are no special constants to apply
    if special_constants is None:
        return data

    # Skip taking any action if the data is of character type and masking strings is not requested
    if (not mask_strings) and np.issubdtype(data.dtype, np.character):
        return data

    # Mask string values
    if np.issubdtype(data.dtype, np.character):

        # Match string-like Special_Constants after trimming leading/trailing spaces
        # (however the returned data will preserve whitespace)
        data_trimmed = np.char.strip(data)
        mask_array = np.zeros(0)

        for key, value in six.iteritems(special_constants):

            # Find which values should be masked, ignoring valid_* constants (which are actually valid data)
            if not key.startswith('valid_'):
                mask_array = np.ma.masked_where(data_trimmed == value.strip(), data, copy=False).mask

            # Mask as needed
            if mask_array.any():
                data = np.ma.masked_where(mask_array, data, copy=copy)
                data.set_fill_value(value)

    # Mask numeric values
    else:

        for key, value in six.iteritems(special_constants):

            # The data == value equality check below only works on similar data types, otherwise it will raise
            # warnings/errors. Thus we circumvent this by assuming equality is False when this is guaranteed.
            compatible_dtypes = (data.dtype.kind == np.asarray(value).dtype.kind) or \
                                (data.dtype.kind in 'fui' and np.asarray(value).dtype.kind in 'ui') or \
                                (data.dtype == np.object_) or (np.asarray(value).dtype == np.object_)

            # Mask the Special_Constants, except for valid_* constants (which are actually valid data)
            if (not key.startswith('valid_')) and compatible_dtypes:
                data = np.ma.masked_where(data == value, data, copy=copy)
                data.set_fill_value(value)

    return data


def get_min_integer_numpy_type(data):
    """ Obtain smallest integer NumPy dtype that can store every value in the input array.

    Parameters
    ----------
    data : array_like
        PDS4 integer data.

    Returns
    -------
    np.dtype
        The NumPy dtype that can store all integers in data.
    """

    # Find min, max (although built-in min() and max() work for NumPy arrays,
    # NumPy's implementation is much faster for large numpy arrays. We cast
    # to ``np.ndarray`` to go around bug in NumPy in min and max for masked object
    # arrays.)
    if isinstance(data, np.ndarray):
        data_min = data.view(np.ndarray).min()
        data_max = data.view(np.ndarray).max()

    else:
        data_min = min(data)
        data_max = max(data)

    abs_max = max(abs(data_min), abs(data_max))

    if abs_max <= 127:
        dtype = 'int8'

    elif abs_max <= 255:

        if data_min >= 0:
            dtype = 'uint8'
        else:
            dtype = 'int16'

    elif abs_max <= 32767:
        dtype = 'int16'

    elif abs_max <= 65535:

        if data_min >= 0:
            dtype = 'uint16'
        else:
            dtype = 'int32'

    elif abs_max <= 2147483647:
        dtype = 'int32'

    elif abs_max <= 4294967295:

        if data_min >= 0:
            dtype = 'uint32'
        else:
            dtype = 'int64'

    elif abs_max <= 9223372036854775807:
        dtype = 'int64'

    elif (abs_max <= 18446744073709551615) and (data_min >= 0):
        dtype = 'uint64'

    else:
        dtype = 'object'

    return np.dtype(dtype)


def is_pds_integer_data(data=None, pds_data_type=None):
    """ Determine, from a data array or from a PDS4 data type, whether such data is an integer.

    Notes
    -----
    This is necessary, as opposed to simply checking for dtype, because some PDS4 data is integer but may
    have the 'object' dtype because it may overflow 64-bit integers (e.g. ASCII_Numeric_Base data, which
    is not limited to 64-bit sizes by the PDS4 standard).

    Parameters
    ----------
    data : array_like, optional
        If given, checks whether this data is integer data.
    pds_data_type : str, unicode or PDSdtype, optional
        If given, checks whether this PDS data type corresponds to integer data.

    Returns
    -------
    bool
        True if *data* and/or *pds_data_type* contain or correspond to PDS4 integer data, False otherwise.
    """

    if (data is None) and (pds_data_type is None):
        raise ValueError('Must provide either an data or a PDS4 data type.')

    need_both = (data is not None) and (pds_data_type is not None)
    array_is_integer = None
    pds_type_is_integer = None

    # Check if data has a PDS4 integer data type
    if data is not None:

        data = np.asanyarray(data)

        # Check for integer dtype
        if np.issubdtype(data.dtype, np.integer):
            array_is_integer = True

        # Check if first instance of non-masked data is an integer (this is not thorough,
        # however checking all values is prohibitively expensive)
        elif data.dtype.type == np.object_:

            if np.ma.is_masked(data):
                data = data.compressed()

            if len(data) > 0 and isinstance(data[0], six.integer_types):
                array_is_integer = True

    # Check if data type is a PDS4 integer type
    if pds_data_type is not None:

        if pds_to_builtin_type(pds_data_type) == int:
            pds_type_is_integer = True

    # If both data and data type are given, return True only if both are not integers
    if need_both:
        return array_is_integer and pds_type_is_integer

    return array_is_integer or pds_type_is_integer


@six.python_2_unicode_compatible
class PDSdtype(object):
    """ A PDS4 data type object.

    Each PDS4 array and table field contains homogeneous values described by a PDSdtype
    object. This class is a wrapper around the named PDS4 data types, to make comparison
    of types easier.
    """

    _name = None

    def __new__(cls, name):
        """ Convert input into a PDS4 data type object.

        Notes
        -----
        No checking is currently done that the input is a valid PDS4 data type.

        Parameters
        ----------
        name : str, unicode or PDSdtype
            A PDS4 data type.

        Returns
        -------
        PDSdtype
            A PDS4 data type object.
        """

        if isinstance(name, cls):
            return name

        elif isinstance(name, six.string_types):
            obj = super(PDSdtype, cls).__new__(cls)
            obj._name = name

            return obj

        raise ValueError('Unknown data_type; must be a string or PDSdtype.')

    @property
    def name(self):
        """
        Returns
        -------
        str or unicode
            The PDS4 data type name.
        """
        return self._name

    def __str__(self):
        """
        Returns
        -------
        str or unicode
            A str representation of the object.
        """
        return six.text_type(self.name)

    def __repr__(self):
        """
        Returns
        -------
        str
            A repr representation of the object.
        """
        return "{0}({1})".format(self.__class__.__name__, repr(self.name))

    def __eq__(self, other):
        """ Compare if two data types are equal.

        Parameters
        ----------
        other : str, unicode or PDSdtype
            A PDS4 data type.

        Returns
        -------
        bool
            True if the data types are equal. PDSdtype objects are equal when their ``name`` attributes
            are identical, or if *other* is str-like then when it is equal to the object's ``name`` attribute.
        """

        if isinstance(other, PDSdtype):
            is_equal = other.name == self.name
        else:
            is_equal = other == self.name

        return is_equal

    def __ne__(self, other):
        """ Compare if two data types are not equal.

        Parameters
        ----------
        other : str, unicode or PDSdtype
            A PDS4 data type.

        Returns
        -------
        bool
            True if the data types are not equal. For equality comparison rules, see ``__eq__``.
        """

        return not (self == other)

    def __contains__(self, other):
        """ Check if a data type contains another.

        Parameters
        ----------
        other : str, unicode or PDSdtype
            A PDS4 data type.

        Returns
        -------
        bool
            True if ``name`` contains at least a portion of *other*.
        """

        if isinstance(other, PDSdtype):
            contains = other.name in self.name
        else:
            contains = other in self.name

        return contains

    def issubtype(self, subtype):
        """ Check if data type is a sub-type.

        Parameters
        ----------
        subtype : str or unicode
            Valid subtypes are int|integer|float|bool|datetime|bitstring|ascii|binary.
            Case-insensitive.

        Returns
        -------
        bool
            True if ``name`` is a sub-type of *subtype*. False otherwise.

        Raises
        ------
        ValueError
            Raised if an unknown subtype is specified.
        TypeError
            Raised if a non-string-like subtype is specified.
        """

        if isinstance(subtype, six.string_types):

            subtype = subtype.lower()

            if subtype in ('int', 'integer'):
                return pds_to_builtin_type(self._name) == builtins.int

            elif subtype in ('float', 'bool'):
                return pds_to_builtin_type(self._name) == getattr(builtins, subtype)

            elif subtype == 'datetime':
                return pds_to_builtin_type(self._name, decode_dates=True) in (dt.datetime, dt.date, dt.time)

            elif subtype in ('bitstring', 'ascii'):
                return subtype in self._name.lower()

            elif subtype == 'binary':
                return (self._name in PDS_NUMERIC_TYPES) and ('ascii' not in self._name.lower())

            raise ValueError('Unknown subtype specified: {0}'.format(subtype))

        raise TypeError('Subtype must be string-like.')
