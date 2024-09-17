from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import xml.etree.ElementTree as ET
from xml.parsers.expat import ExpatError

from ..utils import compat
from ..utils.constants import PDS4_NAMESPACES
from ..utils.logging import logger_init

from ..extern import six

# Initialize the logger
logger = logger_init()

#################################


def read_label(filename, strip_extra_whitespace=True, enforce_default_prefixes=False,
               include_namespace_map=False, decode_py2=False):

    """ Reads a PDS4 XML Label into an ``ElementTree`` Element object.

        Parameters
        ----------
        filename : str or unicode
            The filename, including the path, of the XML label.
        strip_extra_whitespace : bool, optional
            If True, then for element text and attribute values, it collapses
            contiguous whitespaces (including space, tab and newlines) into a
            single space, and removes leading and trailing whitespace altogether.
            However, this only done if the value has a single line with
            non-whitespace characters. Defaults to False.
        enforce_default_prefixes : bool, optional
            If True, strips the default namespace, and ensures that
            default PDS4 prefixes are used for known namespaces (PDS4_NAMESPACES).
            Defaults to False.
        include_namespace_map : bool, optional
            If True, changes method return to a tuple, where the first
            value is the label ElementTree object as usual and the second
            is a ``dict`` with keys being the namespace URIs and values being
            the namespace prefixes in this label. Defaults to False.
        decode_py2 : bool, optional
            If True, decodes UTF-8 byte strings (``str``) into ``unicode``
            strings in Python 2. Option is ignored in Python 3. Defaults to False.

        Returns
        -------
        ``ElementTree`` Element
            Root element for the read-in PDS4 label

    """

    # Read-in XML tree
    try:
        xml_tree = ET.iterparse(filename, events=('start-ns', 'end'))
    except IOError:
        raise IOError('Unable to locate or read label file: ' + filename)

    # Adjust XML tree
    try:

        namespace_map = {}

        for event, elem in xml_tree:

            # Add namespace to the namespace map
            if event == 'start-ns':

                if enforce_default_prefixes:

                    for prefix, uri in six.iteritems(PDS4_NAMESPACES):

                        # Ensure the PDS4 namespace is the default prefix
                        if elem[1] == PDS4_NAMESPACES['pds']:
                            elem = ('', elem[1])

                        # Ensure that dictionaries which are referred to in code
                        # by prefix (such as disp and sp) have the expected prefix
                        elif uri == elem[1]:
                            elem = (prefix, elem[1])

                # Add namespace to map (different prefixes for an existing namespace URI are skipped)
                # Technical note: this map is stored dict[URI] = prefix for two reasons:
                #   (1) ElementTree itself internally stores the namespace map like this, despite taking
                #       it in opposite relation from user
                #   (2) It seems ever slightly more legitimate to remember a single prefix to referring to
                #       multiple URI (e.g. via local prefixes) than to remember two prefixes referring to
                #       the same URI.
                #   These are not necessarily good reasons.
                if elem[1] not in namespace_map:
                    namespace_map[elem[1]] = elem[0]

                continue

            # Strip PDS4 namespace tag (a continuation of ensuring default prefix is PDS4 namespace)
            if (enforce_default_prefixes) and (PDS4_NAMESPACES['pds'] in elem.tag):
                elem.tag = elem.tag.split('{', 1)[0] + elem.tag.split('}', 1)[1]

            # Strip whitespace in elements and attributes if requested
            if strip_extra_whitespace:

                subiter = compat.ET_Tree_iter(ET.ElementTree(elem))
                attribs = six.iteritems(elem.attrib)

                # Strip whitespaces at beginning and end of value in elements that do not have children
                if len(elem) == 0:
                    for elem_content in subiter:

                        if (elem_content.text) and (_non_blank_line_count(elem_content.text) == 1):
                            elem_content.text = _normalize(elem_content.text)

                # Strip whitespaces at beginning and end of attribute values
                for name, value in attribs:
                    if _non_blank_line_count(value) == 1:
                        elem.attrib[name] = _normalize(value)

        label_xml_root = xml_tree.root

        # For Python 2, we can decode all ``str`` to ``unicode``, such that all meta data strings
        # are consistently unicode.
        if six.PY2 and decode_py2:
            label_xml_root = _decode_tree(label_xml_root)

    # Raise exception if XML cannot be parsed. In Python 3 we raise from None to avoid confusing re-raise
    except (ExpatError, compat.ET_ParseError):
        six.raise_from(
            ExpatError('The requested PDS4 label file does not appear contain valid XML: ' + filename), None)

    if include_namespace_map:
        return label_xml_root, namespace_map

    else:
        return label_xml_root


def _decode_tree(xml_tree):
    """ Decode an XML tree from UTF-8 encoded ``str`` to ``unicode``.

    Decodes all element tags and text, as well as attribute names and values. Do not call gratuitously
    due to efficiency concerns.

    Notes
    -----
    This function is intended to be used solely in Python 2. Python 3 has no ``unicode`` data type,
    all ``str`` are essentially ``unicode`` by default.

    Parameters
    ----------
    xml_tree : ``ElementTree`` Element
        The XML tree to decoded.

    Returns
    -------
    ``ElementTree`` Element
        The decoded XML tree, with all strings converted to ``unicode`` from UTF-8 ``str``.
    """

    # This function is designed to work solely in Python 2; otherwise we return the tree unchanged.
    if not six.PY2:
        return xml_tree

    # Function that decodes all passed in text to unicode, assuming it's encoded as UTF-8
    def decode(text):

        if text is None:
            return None

        if isinstance(text, str):
            return text.decode('utf-8')

        return text

    # Loop over all elements in the tree
    for elem in compat.ET_Element_iter(xml_tree):

        # Decode elements
        elem.tag = decode(elem.tag)
        elem.text = decode(elem.text)
        elem.tail = decode(elem.tail)

        # Decode attributes
        for name, value in elem.attrib.items():

            del elem.attrib[name]
            name = decode(name)

            value = decode(value)

            elem.attrib[name] = value

    return xml_tree


def _non_blank_line_count(string):
    """
    Parameters
    ----------
    string : str or unicode
        String (potentially multi-line) to search in.

    Returns
    -------
    int
        Number of non-blank lines in string.
    """

    non_blank_counter = 0

    for line in string.splitlines():

        if line.strip():
            non_blank_counter += 1

    return non_blank_counter


def _normalize(string):
    """ Normalize whitepace in a string according to PDS4 Standards.

    Notes
    -----
    There are a number of ways to implement this method. The employed implementation is generally
    either the fastest or close to the fastest between the various platforms.

    Parameters
    ----------
    string : str or unicode
        String to normalize.

    Returns
    -------
    str or unicode
        Whitespace-collapsed string. Collapses contiguous spaces (including line feeds, carriage returns,
        tabs) into a single space character, and removes leading and trailing spaces entirely.
         white space collapsed
    """
    return ' '.join(string.split())
