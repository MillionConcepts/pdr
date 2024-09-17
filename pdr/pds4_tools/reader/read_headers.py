from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .header_objects import HeaderStructure


def _read_header_byte_data(header_structure):
    """ Reads the byte data from the data file for a PDS4 Header.

    Determines, from the structure's meta data, the relevant start and stop bytes in the data file prior to
    reading.

    Parameters
    ----------
    header_structure : HeaderStructure
        The PDS4 Header data structure for which the byte data needs to be read. Should have been
        initialized via `HeaderStructure.from_file` method, or contain the required meta data.

    Returns
    -------
    str or bytes
        The exact byte data for the header.
    """

    from .core import read_byte_data

    meta_data = header_structure.meta_data

    start_byte = meta_data['offset']
    stop_byte = start_byte + meta_data['object_length']

    return read_byte_data(header_structure.parent_filename, start_byte, stop_byte)


def new_header(input, **structure_kwargs):
    """ Create an header structure from PDS-compliant data.

    Parameters
    ----------
    input : bytes, str or unicode
        A string or bytes containing the data for header.
    structure_kwargs :  dict, optional
        Keywords that are passed directly to the `HeaderStructure` constructor.

    Returns
    -------
    HeaderStructure
        An object representing the PDS4 header structure. The data attribute will contain *input*.
        Other attributes may be specified via *structure_kwargs*.
    """

    # Create the HeaderStructure
    header_structure = HeaderStructure(**structure_kwargs)
    header_structure.data = input

    return header_structure


def read_header_data(header_structure):
    """
    Reads the data for a single PDS4 header structure, modifies *header_structure* to contain said data.

    Parameters
    ----------
    header_structure : HeaderStructure
        The PDS4 Header data structure to which the data should be added.

    Returns
    -------
    None
    """

    header_byte_data = _read_header_byte_data(header_structure)

    header_structure.data = new_header(header_byte_data).data


def read_header(full_label, header_label, data_filename, lazy_load=False, decode_strings=False):
    """ Create the `HeaderStructure`, containing label, data and meta data for a PDS4 Header from a file.

    Headers refer to PDS4 header data structures, which typically describe a portion of the data that serves
    as a header for some other data format.

    Parameters
    ----------
    full_label : Label
        The entire label for a PDS4 product, from which *header_label* originated.
    header_label : Label
        Portion of label that defines the PDS4 header data structure.
    data_filename : str or unicode
        Filename, including the full path, of the data file that contains the data for this header.
    lazy_load : bool, optional
        If True, does not read-in the data of this header until the first attempt to access it.
        Defaults to False.
    decode_strings : bool, optional
        If True, the header data will be decoded to the ``unicode`` type in Python 2, and to the
        ``str`` type in Python 3. If False, leaves said data as a byte string. Defaults to False.

    Returns
    -------
    HeaderStructure
        An object representing the header; contains its label, data and meta data

    Raises
    ------
    TypeError
        Raised if called on a non-header according to *header_label*.
    """

    # Skip over data structure if its not actually an Array
    if 'Header' not in header_label.tag:
        raise TypeError('Attempted to read_header() on a non-header: ' + header_label.tag)

    # Create the data structure for this array
    header_structure = HeaderStructure.from_file(data_filename, header_label, full_label,
                                                 lazy_load=lazy_load, decode_strings=decode_strings)

    return header_structure
