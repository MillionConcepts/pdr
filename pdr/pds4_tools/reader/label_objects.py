from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import re
from itertools import chain
from xml.etree import ElementTree as ET

from .read_label import read_label
from .general_objects import Meta_Class

from ..utils import compat
from ..utils.constants import PDS4_NAMESPACES, PDS4_DATA_FILE_AREAS
from ..utils.helpers import xml_to_dict
from ..utils.logging import logger_init
from ..utils.exceptions import PDS4StandardsException

from ..extern import six

# Initialize the logger
logger = logger_init()

#################################


class Label(object):
    """ Stores a PDS4 label or a portion of a PDS4 label.

        This class is similar to an ``ElementTree`` Element; most of the basic attributes and methods
        for Element will also work here. Some additional convenience methods and features are provided
        to make it easier to work with PDS4 labels.

        Parameters
        ----------
        (in general `from_file` should be used instead of using __init__)

        convenient_root : ``ElementTree`` Element
            Root element of the PDS4 label or label portion, modified to normalize whitespace
            in all element and attribute values containing a single non-whitespace line, to
            strip the default namespace, and to use the default PDS4 prefixes for known namespaces.
        unmodified_root : ``ElementTree`` Element
            Root element of the PDS4 label or label portion.
        convenient_namespace_map : dict, optional
            Keys are the namespace URIs and values are the prefixes for the convenient root of this label.
        unmodified_namespace_map : dict, optional
            Keys are the namespace URIs and values are the prefixes for the unmodified root of this label.
        default_root : str or unicode, optional
            Specifies whether the root element used by default when calling methods and attributes
            in this object will be the convenient_root or unmodified_root. Must be one of
            'convenient' or 'unmodified'. Defaults to convenient.

        Examples
        --------

        To load a label from file,

        >>> lbl = Label.from_file('/path/to/label.xml')

        To search the entire label for logical_identifier (of which only one is allowed),

        >>> lbl.find('.//logical_identifier')

        To search the entire label for Display Settings in the 'disp' namespace
        (of which there could be multiple),

        >>> display_settings = lbl.findall('.//disp:Display_Settings')

        To search the Display Settings for the top-level element, Display_Direction,

        >>> display_settings.find('disp:Display_Direction')

        See method descriptions for more info.
    """

    def __init__(self, convenient_root=None, unmodified_root=None,
                 convenient_namespace_map=None, unmodified_namespace_map=None, default_root='convenient'):

        # ElementTree root containing read-in XML which was modified before storage
        # (see options set in from_file() below)
        self._convenient_root = convenient_root

        # ElementTree root containing the unmodified XML
        self._unmodified_root = unmodified_root

        # Dictionaries with keys being the namespace URIs and values being the namespace prefixes
        # for namespaces used this label
        self._convenient_namespace_map = convenient_namespace_map if convenient_namespace_map else {}
        self._unmodified_namespace_map = unmodified_namespace_map if unmodified_namespace_map else {}

        # Set default root (running it through setter)
        self._default_root = None
        self.default_root = default_root

    def __getitem__(self, key):
        """ Obtain subelement.

        Parameters
        ----------
        key : int or slice
            Specifies which subelement to select.

        Returns
        -------
        Label
            Subelement of label.
        """

        return Label(self._convenient_root[key], self._unmodified_root[key],
                     self._convenient_namespace_map, self._unmodified_namespace_map,
                     default_root=self.default_root)

    def __repr__(self):
        """
        Returns
        -------
        str
            A repr string identifying the tag element in a similar way to ``ElementTree`` Element.
        """

        if self._convenient_root is None:
            return super(Label, self).__repr__()
        else:
            return str('<{0} Element {1} at {2}>').format(
                self.__class__.__name__, repr(self._convenient_root.tag), hex(id(self)))

    def __len__(self):
        """
        Returns
        -------
        int
            Number of (direct) subelements this label has.
        """
        return len(self.getroot())

    @classmethod
    def from_file(cls, filename, default_root='convenient'):
        """ Create Label from a PDS4 XML label file.

        Parameters
        ----------
        filename : str or unicode
            Filename, including path, to XML label.
        default_root : str or unicode, optional
            Specifies whether the root element used by default when calling methods and attributes in
            this object will be the convenient_root or unmodified_root. Must be one of convenient|unmodified.
            Defaults to convenient.

        Returns
        -------
        Label
            Instance, with the contents being taken from *filename*.
        """

        convenient_root, convenient_namespace_map = read_label(filename,
                                            strip_extra_whitespace=True, enforce_default_prefixes=True,
                                            include_namespace_map=True, decode_py2=True)

        unmodified_root, unmodified_namespace_map = read_label(filename,
                                            strip_extra_whitespace=False, enforce_default_prefixes=False,
                                            include_namespace_map=True, decode_py2=True)

        obj = cls(convenient_root=convenient_root,
                  unmodified_root=unmodified_root,
                  convenient_namespace_map=convenient_namespace_map,
                  unmodified_namespace_map=unmodified_namespace_map,
                  default_root=default_root)

        return obj

    @property
    def text(self):
        """
        Returns
        -------
            Text of element.
        """
        return self.getroot().text

    @property
    def tail(self):
        """
        Returns
        -------
            Tail of element.
        """
        return self.getroot().tail

    @property
    def tag(self):
        """
        Returns
        -------
            Tag of element.
        """
        return self.getroot().tag

    @property
    def attrib(self):
        """
        Returns
        -------
            Attributes of element.
        """

        # Make a copy so that assignment of individual values with-in the dictionary cannot make the two
        # roots out of sync
        return self.getroot().attrib.copy()

    @property
    def default_root(self):
        """
        Returns
        -------
        str or unicode
            Either 'convenient' or 'unmodified'. Specifies whether the root element used by default when
            calling methods and attributes in this object will be the convenient_root or unmodified_root.
        """

        return self._default_root

    @text.setter
    def text(self, value):
        self.getroot(unmodified=True).text = value
        self.getroot(unmodified=False).text = value

    @tail.setter
    def tail(self, value):
        self.getroot(unmodified=True).tail = value
        self.getroot(unmodified=False).tail = value

    @tag.setter
    def tag(self, value):
        self.getroot(unmodified=True).tag = value
        self.getroot(unmodified=False).tag = value

    @attrib.setter
    def attrib(self, value):
        self.getroot(unmodified=True).attrib = value
        self.getroot(unmodified=False).attrib = value

    @default_root.setter
    def default_root(self, value):

        if value not in ('convenient', 'unmodified'):
            raise ValueError('Unknown default root for Label: {0}.'.format(value))

        self._default_root = value

    def get(self, key, default=None, unmodified=None):
        """ Gets the element attribute named *key*.

        Uses the same format as ``ElementTree.get``.

        Parameters
        ----------
        key : str or unicode
            Attribute name to select.
        default : optional
            Value to return if no attribute matching *key* is found. Defaults to None.
        unmodified : bool or None
            Looks for key in unmodified ``ElementTree`` root if True, or the convenient one if False.
            Defaults to None, which uses `Label.default_root` to decide.

        Returns
        -------
            Value of the attribute named *key* if it exists, or *default* otherwise.
        """
        return self.getroot(unmodified=unmodified).get(key, default)

    def getroot(self, unmodified=None):
        """ Obtains ``ElementTree`` root Element instance underlying this object.

        Parameters
        ----------
        unmodified : bool or None or None, optional
            If True, returns the unmodified (see `Label` docstring for meaning) ``ElementTree`` Element.
            If False, returns convenient root. Defaults to None, which uses `Label.default_root` to
            decide.

        Returns
        -------
        Element instance
            The ``ElementTree`` root element backing this Label.
        """

        root = self._convenient_root

        if self._resolve_unmodified(unmodified):
            root = self._unmodified_root

        return root

    def find(self, match, namespaces=None, unmodified=None, return_ET=False):
        """ Search for the first matching subelement.

        Uses the same format as ``ElementTree.find``. See `Label` docstring or ``ElementTree.find``
        documentation for examples and supported XPATH description.

        The namespaces found in the label, and those contained in the PDS4_NAMESPACES constant are registered
        automatically. If match contains other namespace prefixes then you must pass in *namespaces*
        parameter specifying the URI for each prefix. In case of duplicate prefixes for the same URI, prefixes
        in the label overwrite those in PDS4_NAMESPACES, and prefixes in *namespaces* overwrite both.

        Parameters
        ----------
        match : str or unicode
            XPATH search string.
        namespaces : dict, optional
            Dictionary with keys corresponding to prefix and values corresponding to URI for namespaces.
        unmodified : bool or None, optional
            Searches unmodified ``ElementTree`` root if True, or the convenient one if False.
            Defaults to None, which uses `Label.default_root` to decide.
        return_ET : bool, optional
            Returns an ``ElementTree`` Element instead of a Label if True. Defaults to False.

        Returns
        -------
        Label, ElementTree Element or None
            Matched subelement, or None if there is no match.
        """

        # Select the proper XML root to look in
        root = self.getroot(unmodified)

        # Append known namespaces if search contains them
        namespaces = self._append_known_namespaces(match, namespaces,  unmodified)

        # Find the matching element
        try:
            found_element = root.find(match, namespaces=namespaces)

        # Implement namespaces support and unicode searching for Python 2.6
        except TypeError:

            if namespaces is not None:
                match = self._add_namespaces_to_match(match, namespaces)

            match = self._unicode_match_to_str(match)

            found_element = root.find(match)

        # If return_ET is not used, find the other matching element
        if not return_ET and found_element is not None:

            unmodified = self._resolve_unmodified(unmodified)

            other_element = self._find_other_element(found_element, unmodified)
            args = [self._convenient_namespace_map, self._unmodified_namespace_map, self._default_root]

            if unmodified:
                label = Label(other_element, found_element, *args)
            else:
                label = Label(found_element, other_element, *args)

            found_element = label

        return found_element

    def findall(self, match, namespaces=None, unmodified=None, return_ET=False):
        """ Search for all matching subelements.

        Uses the same format as ``ElementTree.findall``. See `Label` docstring or ``ElementTree.findall``
        documentation for examples and supported XPATH description.

        The namespaces found in the label, and those contained in the PDS4_NAMESPACES constant are registered
        automatically. If match contains other namespace prefixes then you must pass in *namespaces*
        parameter specifying the URI for each prefix. In case of duplicate prefixes for the same URI, prefixes
        in the label overwrite those in PDS4_NAMESPACES, and prefixes in *namespaces* overwrite both.

        Parameters
        ----------
        match : str or unicode
            XPATH search string
        namespaces : dict, optional
            Dictionary with keys corresponding to prefix and values corresponding to URI for namespaces.
        unmodified : bool or None, optional
            Searches unmodified ``ElementTree`` root if True, or the convenient one if False.
            Defaults to None, which uses `Label.default_root` to decide.
        return_ET : bool, optional
            Returned list contains ``ElementTree`` Elements instead of Labels if True. Defaults to False.

        Returns
        -------
        List[Label or ElementTree Element]
            Matched subelements, or [] if there are no matches.
        """

        # Select the proper XML root to look in
        root = self.getroot(unmodified)

        # Append known namespaces if search contains them
        namespaces = self._append_known_namespaces(match, namespaces, unmodified)

        # Find the matching elements
        try:
            found_elements = root.findall(match, namespaces=namespaces)

        # Implement namespaces support and unicode searching for Python 2.6
        except TypeError:

            if namespaces is not None:
                match = self._add_namespaces_to_match(match, namespaces)

            match = self._unicode_match_to_str(match)

            found_elements = root.findall(match)

        # If return_ET is not used, find the other matching elements
        if not return_ET and found_elements is not None:

            labels = []
            unmodified = self._resolve_unmodified(unmodified)

            for element in found_elements:

                other_element = self._find_other_element(element, unmodified)
                args = [self._convenient_namespace_map, self._unmodified_namespace_map, self._default_root]

                if unmodified:
                    label = Label(other_element, element, *args)
                else:
                    label = Label(element, other_element, *args)

                labels.append(label)

            found_elements = labels

        return found_elements

    def findtext(self, match, default=None, namespaces=None, unmodified=None):
        """ Finds text for the first subelement matching *match*.

        Uses the same format as ``ElementTree.findtext``. See `Label` docstring or ``ElementTree.findtext``
        documentation for examples and supported XPATH description.

        The namespaces found in the label, and those contained in the PDS4_NAMESPACES constant are registered
        automatically. If match contains other namespace prefixes then you must pass in *namespaces*
        parameter specifying the URI for each prefix. In case of duplicate prefixes for the same URI, prefixes
        in the label overwrite those in PDS4_NAMESPACES, and prefixes in *namespaces* overwrite both.

        Parameters
        ----------
        match : str or unicode
            XPATH search string.
        default : optional
            Value to return if no match is found. Defaults to None.
        namespaces : dict, optional
            Dictionary with keys corresponding to prefixes and values corresponding to URIs for namespace.
        unmodified : bool or None, optional
            Searches unmodified ``ElementTree`` root if True, or the convenient one if False.
            Defaults to None, which uses `Label.default_root` to decide.

        Returns
        -------
        str or unicode
            Text of the first matched element, or *default* otherwise.
        """

        found_element = self.find(match, namespaces=namespaces, unmodified=unmodified, return_ET=True)

        if found_element is None:
            return default

        else:
            return found_element.text

    def iter(self, tag=None):
        """ Create an iterator containing the current element and all elements below it.

        Uses the same format as ``ElementTree.iter``.

        Parameters
        ----------
        tag : str or unicode, optional
            When given, include only elements with a matching tag name in the iterator.

        Returns
        -------
        Iterator[Label]
            An iterator yielding the current element and all elements below it in document (depth first) order.
            Filtered by *tag* when given.
        """

        if tag == "*":
            tag = None

        if (tag is None) or (self.tag == tag):
            yield self

        for child in self:
            for element in child.iter(tag):
                yield element

    def itertext(self):
        """ Create an iterator containing the inner text of the current element and all elements below it.

        Uses the same format as ``ElementTree.Element.itertext``.

        Notes
        -----
        Inner text is the text and tail attributes.

        Returns
        -------
        Iterator[str or unicode]
            An iterator yielding the inner text of the current element and all elements below it in document
            (depth first) order.
        """

        tag = self.tag
        if not isinstance(tag, six.string_types) and tag is not None:
            return

        text = self.text
        if text:
            yield text

        for child in self:

            for element in child.itertext():
                yield element

            tail = child.tail
            if tail:
                yield tail

    def to_string(self, unmodified=True, pretty_print=False):
        """ Generate a string representation of XML label.

        Parameters
        ----------
        unmodified : bool or None, optional
            Generates representation of unmodified ``ElementTree`` root if True, or the convenient one if
            False. None uses `Label.default_root` to decide. Defaults to True.
        pretty_print : bool, optional
            String representation is pretty-printed if True. Defaults to False.

        Returns
        -------
        unicode or str
            String representation of `Label`.
        """

        # Obtain root element, while also deepcopying it such that any modifications made
        # inside this method (e.g. during pretty printing) do not affect the original copy.
        root = self.copy(unmodified=unmodified, return_ET=True)

        # Adapted from effbot.org/zone/element-lib.htm#prettyprint, modified to properly dedent multi-line
        # values with different indents than used by this method (e.g., each line is indented by 4 spaces
        # but this method uses 2), and to preserve a single extra newline anywhere one or more are present.
        def pretty_format_xml(elem, level=0):

            i = level * '  '

            # Preserve single extra newline at the end of text (e.g. <Field>\n\n<offset>var</offset>...)
            i_text = '\n' + i
            if elem.text:

                if elem.text.count('\n') > 1:
                    i_text = ('\n' * 2) + i

            # Preserve single extra newline at the end of an element (e.g. <Field>var</Field>\n\n<offset>...)
            i_tail = '\n' + i
            if elem.tail:
                if elem.tail.count('\n') > 1:
                    i_tail = ('\n' * 2) + i

            # Remove extra space on each newline in multi-line text values
            if elem.text and elem.text.strip() and (elem.text.count('\n') > 0 or elem.text.count('\r') > 0):
                lines = elem.text.splitlines(True)

                # If each line beginning contains extra space (e.g., it used 4 spaces to align but we use 2)
                # then remove that extra space
                for j, line in enumerate(lines):
                    if line[0:len(i)] == i:
                        lines[j] = line[len(i)-1:]

                elem.text = ''.join(lines)

                # On last line of multi-line string, if it ends in a newline and spaces, remove them
                # and replace with a newline and spaces such that the closing tag is on the same level
                # as the opening tag
                if elem.text.rstrip(' ') != elem.text.rstrip():
                    last_newline = max(elem.text.rfind('\n'), elem.text.rfind('\r'))
                    elem.text = elem.text[:last_newline] + '\n' + i

            if len(elem):

                if not elem.text or not elem.text.strip():
                    elem.text = i_text + '  '
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i_tail
                for elem in elem:
                    pretty_format_xml(elem, level+1)
                if not elem.tail or not elem.tail.strip():
                    elem.tail = i_text
            else:
                if elem.text and not elem.text.strip():
                    elem.text = i_text
                if level and (not elem.tail or not elem.tail.strip()):
                    elem.tail = i_tail

        # Pretty-format root node
        if pretty_print:
            pretty_format_xml(root)

        # Remove newline characters from tail of the root element
        if root.tail is not None:
            root.tail = root.tail.strip('\n\r')

        # Obtain string representation, taking care to register_namespaces()
        self._register_namespaces('register', unmodified)
        string = ET.tostring(root, encoding=str('utf-8')).decode('utf-8')
        self._register_namespaces('unregister', unmodified)

        # Adjust to fix issue that in Python 2.6 it is not possible to specify a null prefix correctly
        if 'xmlns:=' in string:
            string = string.replace('xmlns:=', 'xmlns=')
            string = string.replace('<:', '<')
            string = string.replace('</:', '</')

        # Remove UTF-8 processing instruction from first line on Python 2
        if '<?xml' == string.lstrip()[0:5]:
            string_list = string.splitlines(True)
            string = ''.join(string_list[1:])

        # If label is not pretty printed, then we fix a potential issue with indented labels and ET
        # (The indent for an element is in the .tail attribute of the previous element, but for the
        # root element there is no element above it with a tail. We check what is the indent for the
        # closing tag of the root element and manually insert it for the opening tag.)
        if not pretty_print:
            last_tail = root[-1].tail if len(root) else root.text

            if last_tail is not None:
                num_leading_spaces = len(last_tail) - len(last_tail.rstrip(' '))
                num_leading_tabs = len(last_tail) - len(last_tail.rstrip('\t'))
                string = ' ' * num_leading_spaces + '\t' * num_leading_tabs + string

        return string

    def to_dict(self, unmodified=None, skip_attributes=True, cast_values=False, cast_ignore=()):
        """ Generate an ``OrderedDict`` representation of XML label.

        Parameters
        ----------
        unmodified : bool or None, optional
            Generates representation of unmodified ``ElementTree`` root if True, or the convenient one if
            False. Defaults to None, which uses `Label.default_root` to decide.
        skip_attributes : bool, optional
            If True, skips adding attributes from XML. Defaults to True.
        cast_values : bool, optional
            If True, float and int compatible values of element text and attribute values will be cast as such
            in the output dictionary. Defaults to False.
        cast_ignore : tuple[str or unicode], optional
            If given, then a tuple of element tags and/or attribute names. If *cast_values* is True, then
            for elements and attributes matching exactly the values in this tuple, values will not be cast.
            Attribute names must be prepended by an '@'. Empty by default.

        Returns
        -------
        OrderedDict
            A dictionary representation of `Label`.
        """

        root = self.getroot(unmodified)
        namespace_map = self.get_namespace_map(unmodified)

        # Achieve equivalent of register_namespaces() via tag_modify
        tag_modify = []
        for uri, prefix in namespace_map.items():
            if prefix.strip():
                tag_modify.append(('{{{0}}}'.format(uri), '{0}:'.format(prefix)))
            else:
                tag_modify.append(('{{{0}}}'.format(uri), ''))

        return xml_to_dict(root, skip_attributes=skip_attributes, cast_values=cast_values,
                           cast_ignore=cast_ignore, tag_modify=tuple(tag_modify))

    def get_namespace_map(self, unmodified=None):
        """ Obtain namespace map.

        Parameters
        ----------
        unmodified : bool or None, optional
            If True, returns the namespace map for the unmodified (see `Label` docstring) label. If False,
            it uses the convenient label. Defaults to None, which uses `Label.default_root` to decide.

        Returns
        -------
        dict
            A dict with keys being the namespace URIs and values being the namespace prefixes for this
            label.
        """

        namespace_map = self._convenient_namespace_map

        if self._resolve_unmodified(unmodified):
            namespace_map = self._unmodified_namespace_map

        return namespace_map

    def copy(self, unmodified=None, return_ET=False):
        """ Obtain a deepcopy of this Label.

        Parameters
        ----------
        unmodified : bool, optional
            If *return_ET* is True, then setting this to True will return a copy of the unmodified
            ``ElementTree`` root, or the convenient one if False. Defaults to None, which uses
            `Label.default_root` to decide.
        return_ET : bool, optional
            Returned value is a ``ElementTree`` Element instead of Label if True. Defaults to False.

        Returns
        -------
        Label or ElementTree Element
        """

        # This appears somewhat faster than copy.deepcopy and seems to have no ill effect
        def copy_tree(tree):
            return ET.fromstring(ET.tostring(tree, encoding=str('utf-8')))

        if return_ET:
            return copy_tree(self.getroot(unmodified=unmodified))

        else:

            convenient_root = copy_tree(self.getroot(unmodified=False))
            convenient_map = self.get_namespace_map(unmodified=False).copy()

            unmodified_root = copy_tree(self.getroot(unmodified=True))
            unmodified_map = self.get_namespace_map(unmodified=True).copy()

            copied_label = self.__class__(convenient_root=convenient_root,
                                          unmodified_root=unmodified_root,
                                          convenient_namespace_map=convenient_map,
                                          unmodified_namespace_map=unmodified_map,
                                          default_root=self.default_root)

            return copied_label

    def _resolve_unmodified(self, unmodified):
        """ Resolves *unmodified* to either True, or False.

        Parameters
        ----------
        unmodified : bool or None
            Variable to resolve.

        Returns
        -------
        bool
            If *unmodified* is bool, returns unchanged. If None, uses `Label.default_root` to decide
            whether to return True (if 'unmodified') or False (if 'convenient').
        """

        if isinstance(unmodified, bool):
            return unmodified

        elif unmodified is None:
            return self._default_root == 'unmodified'

        else:
            raise TypeError('Unknown unmodified variable: {0}.'.format(unmodified))

    def _find_other_element(self, element, was_unmodified):
        """
        When using `find` or `findall`, we initially search one of the two ``ElementTree`` representations
        (`_convenient_root` or `_unmodified_root`). The purpose of this method is to find the Element
        in the other representation.

        Parameters
        ----------
        element : Label or ElementTree Element
            Element to find
        was_unmodified : bool
            True if *element* was taken from `_unmodified_root`, False otherwise.


        Returns
        -------
        ``ElementTree`` Element
            Matched element.
        """

        other_element = None

        if was_unmodified:
            root = self.getroot(unmodified=True)
            other_root = self.getroot(unmodified=None)
        else:
            root = self.getroot(unmodified=None)
            other_root = self.getroot(unmodified=True)

        # Loop over all elements in root of element to find its number
        node_number = -1

        for i, child_elem in enumerate(compat.ET_Element_iter(root)):

            if element == child_elem:
                node_number = i
                break

        # Loop over all elements of other_root to find the matching node_number
        for i, child_elem in enumerate(compat.ET_Element_iter(other_root)):

            if i == node_number:
                other_element = child_elem
                break

        return other_element

    def _register_namespaces(self, action, unmodified):
        """
        Registers or unregisters namespace prefixes via ET's ``register_namespace``. The unregister
        functionality is provided because register_namespace is global, affecting any other ET usage.
        Register and unregister allow anything in-between them to effectively have a local namespace register.

        Parameters
        ----------
        action : str or unicode
            Either 'register' or 'unregister', specifying what action to take. Defaults to 'register'.
        unmodified : bool or None
            If True, uses prefixes taken from the unmodified root, instead of the convenient root,
            to register or unregister namespaces.

        Returns
        -------
        None
        """

        prefixes = ET._namespace_map.values()
        uris = ET._namespace_map.keys()

        namespace_map = self.get_namespace_map(unmodified)

        for uri, prefix in namespace_map.items():

            # Register namespaces
            if action == 'register':

                # Check if namespace prefix or URI already exists, then do not register the namespace if so.
                # This allows local namespaces that have the same prefix as a global prefix but a
                # different URI, which is valid in XML, to stay unique)
                if (prefix in prefixes) or (uri in uris):
                    continue

                # Register the namespace
                ET._namespace_map[uri] = prefix

            # Unregister the namespaces
            else:

                if (prefix in prefixes) and (uri in ET._namespace_map.keys()):
                    del ET._namespace_map[uri]

    def _append_known_namespaces(self, match, namespaces, unmodified):
        """
        Appends known namespaces (i.e., those in the namespace map for this label, and those in the
        constant PDS4_NAMESPACES) to *namespaces* if *match* contains prefixes (signified by the colon).
        In case of duplicate prefixes for the same URI, prefixes in the label overwrite those in
        PDS4_NAMESPACES, and prefixes in *namespaces* overwrite both.

        Parameters
        ----------
        match : str or unicode
            XPATH search string.
        namespaces : dict
            Dictionary with keys corresponding to prefix and values corresponding to URI for namespaces.
        unmodified : bool or None
            If True, uses namespace map created from the unmodified root, instead of the convenient root,
             as part of the known namespaces. If None, uses `Label.default_root` to decide.

        Returns
        -------
        dict
            New namespaces dictionary containing previous *namespaces* as well as PDS4_NAMESPACES,
            and those in the namespace map for this label.
        """

        # Merge PDS4_NAMESPACES and namespaces from this label into a single ``dict``. In case of conflict,
        # the latter take precedence. Additionally, if namespaces in this label have a case where a
        # single prefix refers to multiple URIs (via local prefixes), only one will be kept.
        namespace_map = self.get_namespace_map(unmodified)
        known_namespaces = dict(chain(
                                six.iteritems(PDS4_NAMESPACES),
                                six.iteritems(dict((v, k) for k, v in six.iteritems(namespace_map)))))

        if (':' in match) and (namespaces is None):
            namespaces = known_namespaces

        elif ':' in match:
            namespaces = dict(chain(six.iteritems(known_namespaces), six.iteritems(namespaces)))

        return namespaces

    @classmethod
    def _add_namespaces_to_match(cls, match, namespaces):
        """
        Python 2.6 does not support the namespaces parameter for ``ElementTree``'s `find`, `findall`,
        which are used in the implementation of `Label`'s `find`, `findall` and `findtext`. To add this
        support, in *match* we replace the prefix with the URI for that prefix contained in brackets.
        This is also how ``ElementPath`` works in Python 2.7 and above, from which this code is adapted.

        Parameters
        ----------
        match : str or unicode
            XPATH search string.
        namespaces : dict
            Dictionary with keys corresponding to prefix and values corresponding to URI for namespaces.

        Returns
        -------
        str or unicode
            A new XPATH search string, with prefix replaced by {URI}.

        Examples
        --------
        >>> match = './/disp:Display_Settings'
        >>> namespaces = {'disp': 'http://pds.nasa.gov/pds4/disp/v1', 'sp': 'http://pds.nasa.gov/pds4/sp/v1'}

        >>> match = self._add_namespaces_to_match(match, namespaces)
        >>> print match
        .//{http://pds.nasa.gov/pds4/disp/v1}Display_Settings
        """

        xpath_tokenizer_re = re.compile(r"("
                                        r"'[^']*'|\"[^\"]*\"|"
                                        r"::|"
                                        r"//?|"
                                        r"\.\.|"
                                        r"\(\)|"
                                        r"[/.*:\[\]\(\)@=])|"
                                        r"((?:\{[^}]+\})?[^/\[\]\(\)@=\s]+)|"
                                        r"\s+")
        modified_match = ''

        for token in xpath_tokenizer_re.findall(match):
            tag = token[1]

            if tag and tag[0] != '{' and ':' in tag:

                try:
                    prefix, uri = tag.split(":", 1)
                    if not namespaces:
                        raise KeyError

                    modified_match += '{0}{{{1}}}{2}'.format(token[0], namespaces[prefix], uri)
                except KeyError:
                    raise SyntaxError('prefix {0} not found in prefix map'.format(prefix))
            else:
                modified_match += '{0}{1}'.format(*token)

        return modified_match

    @classmethod
    def _unicode_match_to_str(cls, match):
        """
        Python 2.6 has a bug in ``ElementTree``'s `find`, `findall` and `findtext` that affects searching
        for unicode match strings. Specifically, when searching for at least the immediate descendents,
        ``ElementPath`` checks that type("") [which is ``str``] is equivalent to the tag, otherwise it sets
        the tag to none. This breaks certain searches, for example element.findall('.//Unicode_Tag') would
        not find a match if the Unicode_Tag element is a direct descendant of element. However just
        './Unicode_Tag' would work there.

        Parameters
        ----------
        match : str or unicode
            A search string for `find`, `findall` or `findtext`.

        Returns
        -------
        str or unicode
            The same search string as *match*, typecast to ``str`` type if *match* was ASCII-compatible.
        """

        try:
            match = str(match.decode('ascii'))

        except UnicodeError:
            logger.warning('Python 2.6 find, findall and findtext results may exclude valid matches when '
                           'the search string contains unicode characters. Detected unicode search: {0}'
                           .format(match))

        return match


class Meta_DisplaySettings(Meta_Class):
    """ Stores PDS4 Display Settings meta data for a single PDS4 data structure.

    Meta data stored in this class is accessed in ``dict``-like fashion. Normally this meta data originates
    from the label (from the beginning of the Display_Settings tag, to its closing tag), via the `from_label`
    or `from_full_label` methods.

    Attributes
    ----------
    valid : bool
        True if Display Settings conform to supported PDS4 Standards, False otherwise.
    """

    def __init__(self, *args, **kwds):
        super(Meta_DisplaySettings, self).__init__(*args, **kwds)

        # Set to True if Display Dictionary has all necessary keys and is otherwise valid/supported
        self.valid = None

    @classmethod
    def from_label(cls, xml_display_settings):
        """ Create a Meta_DisplaySettings from the XML portion describing it.

        Parameters
        ----------
        xml_display_settings : Label or ElementTree Element
            The portion of the label describing the Display_Settings.

        Returns
        -------
        Meta_SpectralCharacteristics
            Instance containing display settings meta data.
        """

        obj = cls()

        tag_modify = ('{{{0}}}'.format(PDS4_NAMESPACES['disp']), '')
        obj._load_keys_from_xml(xml_display_settings, tag_modify=tag_modify)

        obj.valid = obj.is_valid()

        return obj

    @classmethod
    def from_full_label(cls, label, structure_lid):
        """ Loads meta data into self from XML.

        Parameters
        ----------
        label : Label or ElementTree Element
            The entire label for the PDS4 product containing the Display Settings.
        structure_lid : str or unicode
            The local_identifier for the Array data structure which uses the Display Settings.

        Returns
        -------
        Meta_DisplaySettings
            Instance containing display settings meta data for a particular data structure.

        Raises
        ------
        KeyError
            Raised if Display Settings do not exist for the specified *structure_lid*.
        PDS4StandardsException
            Raised if a data structure having the local_identifier *structure_lid* was not found.
        """

        display_settings = get_display_settings_for_lid(structure_lid, label)
        if display_settings is None:
            raise KeyError("No Display_Settings exist in label for local identifier '{0}'".
                           format(structure_lid))

        # Find all structures in the label
        found_structures = []

        for file_area_name in PDS4_DATA_FILE_AREAS:
            found_structures += label.findall('.//{0}/*'.format(file_area_name))

        # Find structure being referenced by structure_lid
        xml_structure = None

        for found_structure in found_structures:

            found_lid = found_structure.findtext('local_identifier')

            if (found_lid is not None) and (found_lid == structure_lid):
                xml_structure = found_structure

        if xml_structure is None:
            raise PDS4StandardsException("A Data Structure having the LID '{0}', specified in "
                                         "Display_Settings, was not found".format(structure_lid))

        obj = cls.from_label(display_settings)
        obj.valid = obj.is_valid(xml_structure)

        return obj

    def is_valid(self, xml_structure=None, raise_on_error=False):
        """ Checks if the the Display Settings to conform to supported PDS4 Standards.

        Parameters
        ----------
        xml_structure : Label or ElementTree Element, optional
            Portion of label describing the Array data structure which uses the Display Settings. If
            given, will validate that the Array data structure has the axes referred to by the Display
            Settings.
        raise_on_error: bool, optional
            If True, raised if Display Settings found are invalid or unsupported. Defaults to False.

        Returns
        -------
        bool
            True if Display Settings are both valid and supported, False otherwise.

        Raises
        ------
        PDS4StandardsException
            Raised if *raise_on_error* is True and if the Display Settings are invalid or unsupported.
        """

        try:

            # Ensure required keys for Display_Settings exist
            keys_must_exist = ['Local_Internal_Reference', 'Display_Direction']
            self._check_keys_exist(keys_must_exist)

            # Ensure required keys for Local_Internal_Reference exist
            reference_keys_must_exist = ['local_identifier_reference', 'local_reference_type']
            self._check_keys_exist(reference_keys_must_exist, sub_element='Local_Internal_Reference')

            # Ensure required keys for Display_Direction exist
            display_keys_must_exist = ['horizontal_display_axis', 'horizontal_display_direction',
                                       'vertical_display_axis', 'vertical_display_direction']
            self._check_keys_exist(display_keys_must_exist, sub_element='Display_Direction')

            # Ensure required keys for Color_Display_Settings exists, if the class exists
            if 'Color_Display_Settings' in self:

                color_keys_must_exist = ['color_display_axis', 'red_channel_band', 'green_channel_band',
                                         'blue_channel_band']
                self._check_keys_exist(color_keys_must_exist, sub_element='Color_Display_Settings')

            # Ensure required key for Movie_Display_Settings exists, if the class exists
            if 'Movie_Display_Settings' in self:
                self._check_keys_exist(['time_display_axis'], sub_element='Movie_Display_Settings')

            # Ensure required axes referenced by the Display Dictionary actually exist in the structure
            if xml_structure is not None:

                axes_arrays = xml_structure.findall('Axis_Array')
                display_direction = self['Display_Direction']
                color_settings = self.get('Color_Display_Settings')
                movie_settings = self.get('Movie_Display_Settings')

                horizontal_axis_exists = False
                vertical_axis_exists = False
                color_axis_exists = False
                movie_axis_exists = False

                for axis in axes_arrays:

                    axis_name = axis.findtext('axis_name')

                    if axis_name == display_direction['horizontal_display_axis']:
                        horizontal_axis_exists = True

                    if axis_name == display_direction['vertical_display_axis']:
                        vertical_axis_exists = True

                    if (color_settings is not None) and (axis_name == color_settings['color_display_axis']):
                        color_axis_exists = True

                    if (movie_settings is not None) and (axis_name == movie_settings['time_display_axis']):
                        movie_axis_exists = True

                display_axes_error = (not horizontal_axis_exists) or (not vertical_axis_exists)
                color_axis_error = (color_settings is not None) and (not color_axis_exists)
                movie_axis_error = (movie_settings is not None) and (not movie_axis_exists)

                if display_axes_error or color_axis_error or movie_axis_error:
                    structure_lid = xml_structure.find('local_identifier')
                    raise PDS4StandardsException("An axis_name, specified in the Display Dictionary "
                                                 "for LID '{0}', was not found".format(structure_lid))

        except PDS4StandardsException:

            if raise_on_error:
                raise

            else:
                return False

        return True


class Meta_SpectralCharacteristics(Meta_Class):
    """ Stores PDS4 Spectral Characteristics meta data for a single PDS4 data structure.

    Meta data stored in this class is accessed in ``dict``-like fashion. Normally this meta data originates
    from the label (from the beginning of the Spectral_Characteristics tag, to its closing tag), via
    the `from_label` or `from_full_label` methods.

    Attributes
    ----------
    valid : bool
        True if the Spectral Characteristics conform to supported PDS4 Standards, False otherwise.
    """

    def __init__(self, *args, **kwds):
        super(Meta_SpectralCharacteristics, self).__init__(*args, **kwds)

        # Set to True if Spectral Characteristics are valid/supported
        self.valid = None

    @classmethod
    def from_label(cls, xml_spectral_chars):
        """ Create a Meta_SpectralCharacteristics from the XML portion describing it.

        Parameters
        ----------
        xml_spectral_chars : Label or ElementTree Element
            The portion of the label describing the Spectral_Characteristics.

        Returns
        -------
        Meta_SpectralCharacteristics
            Instance containing spectral characteristics meta data.
        """

        obj = cls()

        tag_modify = ('{{{0}}}'.format(PDS4_NAMESPACES['sp']), '')
        obj._load_keys_from_xml(xml_spectral_chars, tag_modify=tag_modify)

        obj.valid = obj.is_valid()

        return obj

    @classmethod
    def from_full_label(cls, label, structure_lid):
        """ Loads meta data into self from XML.

        Parameters
        ----------
        label : Label or ElementTree Element
            The entire label for the PDS4 product containing the Spectral Characteristics.
        structure_lid : str or unicode
            The local_identifier for the Array data structure which uses the Spectral Characteristics.

        Returns
        -------
        Meta_SpectralCharacteristics
            Instance containing spectral characteristics meta data for a particular data structure.

        Raises
        ------
        KeyError
            Raised if Spectral Characteristics do not exist for the specified *structure_lid*
        PDS4StandardsException
            Raised if a data structure having the local_identifier *structure_lid* was not found
        """

        spectral_chars = get_spectral_characteristics_for_lid(structure_lid, label)
        if spectral_chars is None:
            raise KeyError("No Spectral_Characteristics exist in label for local identifier '{0}'.".
                           format(structure_lid))

        # Find all structures in the label
        found_structures = []

        for file_area_name in PDS4_DATA_FILE_AREAS:
            found_structures += label.findall('.//{0}/*'.format(file_area_name))

        # Find structure being referenced by structure_lid
        xml_structure = None

        for found_structure in found_structures:

            found_lid = found_structure.findtext('local_identifier')

            if (found_lid is not None) and (found_lid == structure_lid):
                xml_structure = found_structure

        if xml_structure is None:
            raise PDS4StandardsException("A Data Structure having the LID '{0}', specified in "
                                         "Spectral_Characteristics, was not found".format(structure_lid))

        obj = cls.from_label(spectral_chars)
        obj.valid = obj.is_valid(xml_structure)

        return obj

    def is_valid(self, xml_structure=None, raise_on_error=False):

        # We do not currently validate Spectral Characteristics since nothing is ever done with them
        # except display as label
        return None


def get_display_settings_for_lid(local_identifier, label):
    """ Search a PDS4 label for Display_Settings of a data structure with local_identifier.

    Parameters
    ----------
    local_identifier : str or unicode
        The local identifier of the data structure to which the display settings belong.
    label : Label or ElementTree Element
        Label for a PDS4 product with-in which to look for the display settings.

    Returns
    -------
    Label, ElementTree Element or None
        Found Display_Settings section with same return type as *label*, or None if not found.
    """

    matching_display = None

    # Find all the Display Settings classes in the label
    displays = label.findall('.//disp:Display_Settings')
    if not displays:
        return None

    # Find the particular Display Settings for this LID
    for display in displays:

        # Look in both PDS and DISP namespace due to standards changes in the display dictionary
        disp_lids = display.findall('.*/disp:local_identifier_reference')
        pds_lids = display.findall('.*/local_identifier_reference')
        all_lids = [lid.text for lid in disp_lids + pds_lids]

        if all_lids.count(local_identifier):
            matching_display = display
            break

    return matching_display


def get_spectral_characteristics_for_lid(local_identifier, label):
    """ Search a PDS4 label for Spectral_Characteristics of a data structure with local_identifier.

    Parameters
    ----------
    local_identifier : str or unicode
        The local identifier of the data structure to which the spectral characteristics belong.
    label : Label or ElementTree Element
        Label for a PDS4 product with-in which to look for the spectral characteristics.

    Returns
    -------
    Label,  ElementTree Element or None
        Found Spectral_Characteristics section with same return type as *label*, or None if not found.
    """

    matching_spectral = None

    # Find all the Spectral Characteristics classes in the label
    spectra = label.findall('.//sp:Spectral_Characteristics')
    if not spectra:
        return None

    # Find the particular Spectral Characteristics for this LID
    for spectral in spectra:

        # Look in both PDS and SP namespace due to standards changes in the spectral dictionary
        sp_lids = spectral.findall('.*/sp:local_identifier_reference')
        pds_lids = spectral.findall('.*/local_identifier_reference')
        all_lids = [lid.text for lid in sp_lids + pds_lids]

        if all_lids.count(local_identifier):
            matching_spectral = spectral
            break

    return matching_spectral


def get_mission_area(label):
    """ Search a PDS4 label for a Mission_Area.

    Parameters
    ----------
    label : Label or ElementTree Element
        Full label for a PDS4 product with-in which to look for a mission area.

    Returns
    -------
    Label, ElementTree Element or None
        Found Mission_Area section with same return type as *label*, or None if not found.
    """

    return label.find('*/Mission_Area')


def get_discipline_area(label):
    """ Search a PDS4 label for a Discipline_Area.

    Parameters
    ----------
    label : Label or ElementTree Element
        Full label for a PDS4 product with-in which to look for a discipline area.

    Returns
    -------
    Label, ElementTree Element or None
        Found Discipline_Area section with same return type as *label*, or None if not found.
    """

    return label.find('*/Discipline_Area')
