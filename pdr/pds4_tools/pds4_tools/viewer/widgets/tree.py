from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import textwrap
import uuid

from ...utils.compat import OrderedDict
from ...extern import six


class TreeView(object):
    """ A TreeView-like widget for TK. Supports Python 2.6, 2.7 and 3+.

     This widget creates a tree-view, including the ability to minimize and maximize individual leafs.
     It works by taking in a Text widget, and creating a tree-like view inside of it. You must also input a
     (potentially nested) `dict` or `OrderedDict` from which the keys and values for the leaves are taken.
     Each leaf has a key and may have a value. Leaves without any values are considered headers. You may
     specify the font for headers, keys, values and for the size of the space prior to headers. """

    def __init__(self, text_pad, dictionary,
                 header_font=None, key_font=None, value_font=None, spacing_font=None):

        self._text_pad = text_pad

        # Add Elements to TreeView
        self._elements = _make_elements_from_dict(self._text_pad, None, dictionary,
                                                  header_font=header_font, key_font=key_font,
                                                  value_font=value_font, spacing_font=spacing_font)

        # Delete first and last line of text pad if these are extra blank lines
        self._text_pad.config(state='normal')

        for line_index in [['1.0', '2.0'], ['end-1c linestart', 'end']]:

            if self._text_pad.get(*line_index).strip() == '':
                self._text_pad.delete(*line_index)

        self._text_pad.config(state='disabled')

    @property
    def text_pad(self):
        return self._text_pad

    @property
    def elements(self):
        return self._elements

    def __len__(self):

        num_elements = 0

        for element in self._elements:
            num_elements += len(element)

        return num_elements

    def destroy(self):
        self._text_pad.destroy()

    # Find element in TreeView by element id
    def find_element_by_id(self, id):

        found_element = None

        for element in self._elements:

            if element.id == id:
                found_element = element

            else:
                found_element = element.find_child_by_id(id)

            if found_element is not None:
                break

        return found_element


class Element(object):

    def __init__(self, master, parent, key, value, **kwargs):

        self._id = str(uuid.uuid4())

        self._text_pad = master
        self._parent = parent

        self._key = key
        self._value = value
        self._children = []
        self._minimized = False

        key, value, children = self._extract_key_value_children()

        # Set element key and value text, if Element has children
        if children:

            self._set_key_value_text(key='\n', append=True, key_font=kwargs.get('spacing_font'))
            self._set_key_value_text(key=key, add_newline=True, key_font=kwargs.get('header_font'))

            self._children = _make_elements_from_dict(self._text_pad, self, children, **kwargs)

            self._text_pad.tag_bind(self._id, '<Enter>', lambda e: self._text_pad.config(cursor='arrow'))
            self._text_pad.tag_bind(self._id, '<Leave>', lambda e: self._text_pad.config(cursor='xterm'))
            self._text_pad.tag_bind(self._id, '<Button-1>', self.toggle_view)

        # Set element key and value text
        else:

            self._set_key_value_text(key=key, value=value, add_newline=True,
                           key_font=kwargs.get('key_font'), value_font=kwargs.get('value_font'))

    @property
    def id(self):
        return self._id

    @property
    def parent(self):
        return self._parent

    @property
    def key(self):
        return self._key

    @property
    def value(self):
        return self._value

    @property
    def children(self):
        return self._children

    @property
    def minimized(self):
        return self._minimized

    # Extracts a key and value, used to set the element's key and value text, and children
    # (if value contains them)
    def _extract_key_value_children(self):

        key = None
        value = None
        children = OrderedDict()

        # If this element has children or attributes
        if isinstance(self._value, (dict, OrderedDict)):

            attributes = ''

            for k, v in list(self._value.items()):

                # Extract the attributes (go into key)
                if k[0] == '@':
                    attributes += '{0}: {1}, '.format(k.replace('@', ''), v)

                # Extract the value
                elif k == '_text':
                    value = v

                else:
                    children[k] = v

            if attributes != '':
                attributes = '(' + attributes[0:-2] + ')'
                key = '{0}  {1}'.format(self._key, attributes)

            else:
                key = self._key

        # If this element has neither children or attributes
        else:

            key = self._key
            value = self._value

        return key, value, children

    # Sets key and/or value given into the proper spot in text_pad
    def _set_key_value_text(self, key, value=None, key_font=None, value_font=None,
                            append=False,  add_newline=False):

        num_parents = 0
        parent = self._parent

        # Add newline and appropriate whitespace when adding a new key/element pair if not appending
        if not append:

            # Determine number of parents for this element
            while True:

                if parent is not None:
                    num_parents += 1
                    parent = parent.parent

                else:
                    break

            # Determine amount of whitespace (based on number of parents) before text
            whitespace = ' ' * (4 * num_parents)

            # Add whitespace prior to key
            self._set_text(whitespace)

        # Remove any whitespace at the beginning and end of value, for a more consistent appearance
        if value is not None:
            value = six.text_type(value).strip()

        # Add newline after text if requested
        if add_newline:

            if value is None:
                key = '{0}{1}'.format(key, '\n')

            else:
                value = '{0}{1}'.format(value, '\n')

        # Add spacing key
        if key == '\n':
            self._set_text(key, type='spacing', font=key_font)

        # Add key
        else:
            self._set_text(key, type='key', font=key_font)

        # Add value, if it is given
        if value is not None:

            value_list = value.splitlines(True)

            # Make necessary adjustments if this is a multi-line value
            if len(value_list) > 1:

                # Determine whitespace necessary for each line to right-align on key
                cursor_x_position = int(self._text_pad.index('insert').split('.')[1])
                right_align_whitespace = ' ' * cursor_x_position

                # Dedent text, regardless of spacing of first line
                value = '{0}{1}'.format(value_list[0], textwrap.dedent(''.join(value_list[1:])))
                value_list = value.splitlines(True)

                # Adjust first line spacing to match second line
                second_line_whitespace = ' ' * (len(value_list[1]) - len(value_list[1].lstrip(' ')))
                value_list[0] = '{0}{1}{2}'.format(second_line_whitespace, right_align_whitespace,
                                                   value_list[0].lstrip(' '))

                # Add newline prior to first line (such that multi-line values always start below their key)
                value_list[0] = '\n{0}'.format(value_list[0])

                # Add a newline after the last line (such that multi-line values always have one line buffer)
                value_list[-1] = '{0}\n'.format(value_list[-1])

                # Add necessary whitespace to right-align on key to each line
                for i, line in enumerate(value_list):
                    value_list[i] = '{0}{1}'.format(right_align_whitespace, line)

                # Merge back into a single string
                value = ''.join(value_list)

            # Add semi-colon between key and value
            value = ': {0}'.format(value)

            self._set_text(value, type='value', font=value_font)

    # Inserts specified text following the current 'insert' cursor of text pad
    def _set_text(self, text, type=None, font=None):

        # Determine the ID tag for this Element (such that all its text has its id as a tag)
        id_tag = self._id

        self._text_pad.config(state='normal')

        # Insert text, setting font for it if one was given
        if font is not None:

            font_tag = '{0}_{1}'.format(self._id, type)
            tags = '{0} {1}'.format(id_tag, font_tag)

            self._text_pad.insert('insert', text, tags)
            self._text_pad.tag_config(font_tag, font=font)

        else:
            self._text_pad.insert('insert', text, id_tag)

        self._text_pad.config(state='disabled')

    def __len__(self):

        num_elements = 1

        for child in self._children:
            num_elements += len(child)

        return num_elements

    def toggle_view(self, *args):

        if self._minimized:
            self.maximize()

        else:
            self.minimize()

    # Minimizes Element (and all its children)
    def minimize(self):

        # Do nothing if already minimized
        if self._minimized:
            return

        # Hide all children
        for child in self._children:

            if child.children:
                child.minimize()

            self._text_pad.tag_config(child.id, elide=True)

        self._minimized = True

    # Maximizes Element (and all its children)
    def maximize(self):

        # Do nothing if already maximized
        if not self._minimized:
            return

        # Show all children
        for child in self._children:

            if child.children:
                child.maximize()

            self._text_pad.tag_config(child.id, elide=False)

        self._minimized = False

    # Returns a list containing all parents of this element in (descending) order of distance from
    # this element
    def parents(self):

        parents = []
        parent = self._parent

        while True:

            if parent is not None:
                parents.append(parent)
                parent = parent.parent

            else:
                break

        return parents

    # Find child element by element id
    def find_child_by_id(self, id):

        found_element = None

        for child in self._children:

            if child.id == id:
                found_element = child

            else:
                found_element = child.find_child_by_id(id)

            if found_element is not None:
                break

        return found_element


def _make_elements_from_dict(master, parent, dictionary, **kwargs):

    elements = []

    for key, value in list(dictionary.items()):
        elements += _make_elements(master, parent, key, value, **kwargs)

    return elements


def _make_elements(master, parent, key, value, **kwargs):

    elements = []

    if isinstance(value, list):

        for i in value:
            elements.append(Element(master, parent, key, i, **kwargs))

    else:
        elements.append(Element(master, parent, key, value, **kwargs))

    return elements
