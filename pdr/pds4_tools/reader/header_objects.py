from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys

from .general_objects import Structure, Meta_Structure

from ..extern.cached_property import threaded_cached_property
from ..extern import six


class HeaderStructure(Structure):
    """ Stores a single PDS4 header data structure.

    Contains the header's data, meta data and label portion.

    See `Structure`'s and `pds4_read`'s docstrings for attributes, properties and usage instructions
    of this object.

    Inherits all Attributes, Parameters and Properties from `Structure`. Overrides `info`, `data`
    and `from_file` methods to implement them.
    """

    @classmethod
    def from_file(cls, data_filename, structure_label, full_label,
                  lazy_load=False, no_scale=None, decode_strings=None):
        """ Create an header structure from relevant labels and file for the data.

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
        no_scale : None, optional
            Has no effect because Headers do not contain data that can be scaled. Defaults to None.
        decode_strings : bool, optional
            Has no effect because Headers are not necessarily plain-text. See ``parser`` method instead.
            Defaults to None.

        Returns
        -------
        HeaderStructure
            An object representing the PDS4 header structure; contains its label, data and meta data.
        """

        # Create the meta data structure for this header
        meta_header_structure = Meta_HeaderStructure.from_label(structure_label)

        # Create the data structure for this array
        header_structure = cls(structure_data=None, structure_meta_data=meta_header_structure,
                               structure_label=structure_label, full_label=full_label,
                               parent_filename=data_filename)

        # Attempt to access the data property such that the data gets read-in (if not on lazy-load)
        if not lazy_load:
            header_structure.data

        return header_structure

    @classmethod
    def from_bytes(cls, input, **structure_kwargs):
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

        from .read_headers import new_header

        return new_header(input, **structure_kwargs)

    def info(self, abbreviated=False, output=None):
        """ Prints a summary of this data structure.

        Contains the type and dimensions of the Array, and if *abbreviated* is False then
        also outputs the name and number of elements of each axis in the array.

        Parameters
        ----------
        abbreviated : bool, optional
            Has no effect on header data structures.
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
        id = "'{0}'".format(self.id)
        parsing_std_info = '{0}'.format(self.meta_data['parsing_standard_id'])

        summary_args = [self.type, id, parsing_std_info]
        abbreviated_info = "{0} {1} ({2})".format(*summary_args)

        # If output is false, return list representing the various parameters of the summary
        if not output:
            return summary_args

        # Otherwise write out summary to output
        output.write(abbreviated_info)
        output.write('\n')
        output.flush()

    @threaded_cached_property
    def data(self):
        """ All data in the PDS4 header data structure.

        This property is implemented as a thread-safe cacheable attribute. Once it is run
        for the first time, it replaces itself with an attribute having the exact
        data that was originally returned.

        Unlike normal properties, this property/attribute is settable without a __set__ method.
        To never run the read-in routine inside this property, you need to manually create the
        the ``.data`` attribute prior to ever invoking this method (or pass in the data to the
        constructor on object instantiation, which does this for you).

        Returns
        -------
        str, unicode or bytes
            The header described by this data structure.
        """

        super(HeaderStructure, self).data()

        from .read_headers import read_header_data
        read_header_data(self)

        return self.data

    def parser(self):
        """ Obtain a parser for the data in the header.

        Returns
        -------
        HeaderParser
            A parser for the header.
        """
        return HeaderParser().get_parser(self)


class Meta_HeaderStructure(Meta_Structure):
    """ Meta data about a PDS4 header data structure.

    Meta data stored in this class is accessed in ``dict``-like fashion.  Normally this meta data
    originates from the label (e.g., if this is a Header then everything from the opening tag of
    Header to its closing tag will be stored in this object), via the `from_label` method.

    Inherits all Attributes, Parameters and Properties from `Meta_Structure`.

    Examples
    --------

    Supposing the following Header definition from a label::

        <Header>
          <local_identifier>header</local_identifier>
          <offset unit="byte">0</offset>
          <object_length unit="byte">2880</object_length>
          <parsing_standard_id>FITS 3.0</parsing_standard_id>
        </Header>

    >>> meta_array = Meta_HeaderStructure.from_label(header_xml)

    >>> print(meta_array['local_identifier'])
    header

    >>> print(meta_array['parsing_standard_id']
    FITS 3.0
    """

    @classmethod
    def from_label(cls, xml_header):
        """ Create a Meta_HeaderStructure from the XML portion describing it in the label.

        Parameters
        ----------
        xml_header : Label or ElementTree Element
            Portion of label that defines the Header data structure.

        Returns
        -------
        Meta_HeaderStructure
            Instance containing meta data about the header structure, as taken from the XML label.

        Raises
        ------
        PDS4StandardsException
            Raised if required meta data is absent.
        """

        obj = cls()
        obj._load_keys_from_xml(xml_header)

        # Ensure required keys for Array_* exist
        keys_must_exist = ['object_length', 'offset', 'parsing_standard_id']
        obj._check_keys_exist(keys_must_exist)

        return obj

    def is_plain_text(self):
        """ Obtain whether a Header is in plain text.

        Under the definition of plain-text taken here, this includes all data that contains "only
        characters of readable material but not its graphical representation nor other objects
        (images, etc)."

        Returns
        -------
        bool
            True if the Header's data is plain text, False otherwise.
        """

        plain_text_standards = ['7-Bit ASCII Text', 'UTF-8 Text', 'PDS3', 'Pre-PDS3', 'PDS ODL 2',
                                'PDS DSV 1', 'FITS 3.0', 'FITS 4.0', 'VICAR1', 'VICAR2',
                                'ISIS2 History Label']

        return self['parsing_standard_id'] in plain_text_standards


class HeaderParser(object):
    """ Provides a base class for parsers of any PDS Header object.

    Parsers for specific header objects should inherit from this class. Where a specific parser
    is not available, this object may serve as a general parser.

    Parameters
    ----------
    header_structure : HeaderStructure, optional
        The header structure to provide parsing capability for.

    Attributes
    ----------
    structure : HeaderStructure or None
        The header structure to provide parsing capability for.
     """

    def __init__(self, header_structure=None):

        self.structure = header_structure

    @staticmethod
    def get_parser(header_structure):
        """ Factory method to obtain the most specific parser for the data.

        Parameters
        ----------
        header_structure : HeaderStructure, optional
            The header structure to provide a parser for.

        Returns
        -------
        HeaderParser
            A parser (whether specific, if available, or generic) for the header.
        """

        meta_data = header_structure.meta_data

        if 'FITS' in meta_data['parsing_standard_id']:
            return HeaderFITSParser(header_structure)

        elif meta_data.is_plain_text():
            return HeaderPlainTextParser(header_structure)

        else:
            return HeaderParser(header_structure)


class HeaderPlainTextParser(HeaderParser):
    """ A generic parser for any plain-text header. """

    def to_string(self):
        """
        Returns
        -------
        str or unicode
            An unmodified version of the plain-text string that forms the header.
        """

        data = self.structure.data

        if isinstance(data, six.binary_type):
            data = data.decode('utf-8')

        return data


class HeaderFITSParser(HeaderPlainTextParser):
    """ A parser for FITS headers. """

    def to_string(self):
        """
        Returns
        -------
        str or unicode
            A human-readable representation of the FITS header, which leaves it unmodified except
            for splitting each CARD (80 characters) into their own lines and removing padding.
        """

        data = super(HeaderFITSParser, self).to_string()

        # Add newlines every 80 characters
        data = [data[i:i + 80] for i in range(0, len(data), 80)]
        data = ('\r\n'.join(data))

        return data.strip()
