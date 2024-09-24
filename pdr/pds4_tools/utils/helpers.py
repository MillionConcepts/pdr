from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import functools
import numpy as np

from ..utils.compat import OrderedDict
from ..extern import six

#################################


def cast_int_float_string(value):
    """ Cast given string value, if possible, to an int, float or returns unchanged.

    Parameters
    ----------
    value : str or unicode
        Value to try casting to an int and float.

    Returns
    -------
    int, float, str or unicode
        Cast *value*.
    """

    try:
        return int(value)

    except ValueError:

        try:
            return float(value)

        except ValueError:
            return value


def is_array_like(value):
    """
    Array-like values are defined as those that implement __len__ (such as ``list``, ``tuple``,
    ``array.array``, ``np.ndarray``, etc) but are not ``str``, ``unicode`` or ``bytes``.

    Parameters
    ----------
    value
        Any kind of value.

    Returns
    -------
    bool
        True if *value* is array-like, false otherwise.
    """

    # Checks if value implements __len__, and ensures its not a string (six is used because
    # str, unicode, and bytes can all represent strings, depending on the Python version)
    if hasattr(value, '__len__') and (not isinstance(value, (
            six.binary_type, six.text_type,
            np.ma.core.MaskedConstant))):
        return True

    return False


def finite_min_max(array_like):
    """ Obtain finite (non-NaN, non-Inf) minimum and maximum of an array.

    Parameters
    ----------
    array_like : array_like
        A numeric array of some kind, possibly containing NaN or Inf values.

    Returns
    -------
    tuple
        Two-valued tuple containing the finite minimum and maximum of *array_like*.
    """

    array_like = np.asanyarray(array_like)
    finite_values = array_like[np.isfinite(array_like)]

    return finite_values.min(), finite_values.max()


def dict_extract(nested_dict, key):
    """ Recursively searches nested dictionaries.

    *nested_dict* may contain other dictionaries, or other array-like's that have dictionaries
    inside: all dictionaries anywhere will be searched.

    Adapted from http://stackoverflow.com/a/29652561.

    Notes
    -----
    This code is generally efficient. However, if you pass it a dictionary that has a huge array
    nested within it, it will not be performant because it will try to search each value in the
    array for a dictionary (this is by design; the intent if non-dict array-like's are present
    is to search them on the assumption they will be small where using this function makes sense).

    Parameters
    ----------
    nested_dict : dict or OrderedDict
        A dictionary potentially containing an arbitrary number of other dictionaries.
    key : str or unicode
        The key to search for in *nested_dict*.

    Returns
    -------
    generator
        Found values for *key* in any dictionary inside *nested_dict*.

    Examples
    --------

    >>> d = { "id" : "abcde",
              "key1" : "blah",
              "key2" : "blah blah",
              "nestedlist" : [
                "blah blah",
                { "id" : "qwerty",
                "key1": "blah"} ]
            }
    >>> result = dict_extract(d, 'id')

    >>> print(list(result))
    ['abcde', 'qwerty']
    """

    if hasattr(nested_dict, 'items'):

        for k, v in nested_dict.items():
            if k == key:
                yield v
            if isinstance(v, dict):
                for result in dict_extract(v, key):
                    yield result
            elif is_array_like(v):
                for d in v:
                    for result in dict_extract(d, key):
                        yield result


def xml_to_dict(xml_element, skip_attributes=False, cast_values=False, cast_ignore=(), tag_modify=()):
    """ Transforms XML to an ``OrderedDict``.

    Takes an XML ``ElementTree`` Element or a `Label` and creates an equivalent ``OrderedDict``.
    Keys of the dictionary represent tag names and values represent the text values of the elements.
    In case of a (sub)element having child elements, values will be another ``OrderedDict``, inside
    which the text of the element has key '_text'. In case of (sub)elements having child elements with
    the same key, the value for the key will be a ``list``. In case of (sub)elements with attributes,
    the value will be an ``OrderedDict``, inside which the key for each attribute starts with '@' and
    the text of the element has key '_text'. For text elements, the text value is not preserved (and
    a '_text' key is not created) if it contains only whitespace (including spaces, tabs and newlines);
    otherwise whitespaces are preserved.

    Preserves order of elements in most cases. The exception is when an element has 2 or more sets
    of children, where each set has the same key names (i.e., there are at least 4 children, and 2 of
    those children have one key, and 2 have another key) and the order of the children with the
    non-matching keys is intertwined, in such a case the order of the intertwined keys will not be preserved.

    Adapted from http://stackoverflow.com/a/10076823.

    Parameters
    ----------
    xml_element : ``ElementTree`` Element or Label
        XML representation which will be turned into a dictionary.
    skip_attributes : bool, optional
        If True, skips adding attributes from XML. Defaults to False.
    cast_values : bool, optional
        If True, float and int compatible values of element text and attribute values will be cast as such
        in the output dictionary. Defaults to False.
    cast_ignore : tuple[str or unicode], optional
        If given, then a tuple of element tags and/or attribute names. If *cast_values* is True, then
        for elements and attributes matching exactly the values in this tuple, values will not be cast.
        Attribute names must be prepended by an '@'. If *tag_modify* is set, then tags and attribute names
        specified by *cast_ignore* should be the already tag modified versions. Empty by default.
    tag_modify : tuple, optional
        If given, then a 2-valued tuple with str or unicode values, or a tuple of 2-valued tuples. Any match,
        including partial, in element tag names and/or attributes names for each tag_modify[0] is replaced
        with tag_modify[1]. Empty by default.

    Returns
    -------
    OrderedDict
        Dictionary representation of the XML input.
    """

    # Modify tags if requested
    element_tag = xml_element.tag

    if tag_modify:

        if not is_array_like(tag_modify[0]):
            tag_modify = (tag_modify, )

        for tag in tag_modify:
            element_tag = element_tag.replace(tag[0], tag[1])

    d = {element_tag: OrderedDict() if xml_element.attrib else None}
    children = list(xml_element)

    # Add children
    if children:

        dd = OrderedDict()

        xml_to_dict_func = functools.partial(xml_to_dict,
                                             skip_attributes=skip_attributes, cast_values=cast_values,
                                             cast_ignore=cast_ignore, tag_modify=tag_modify)

        for dc in map(xml_to_dict_func, children):
            for k, v in six.iteritems(dc):
                try:
                    dd[k].append(v)
                except KeyError:
                    dd[k] = [v]

        ddd = OrderedDict()

        for k, v in six.iteritems(dd):
            if len(v) == 1:
                ddd[k] = v[0]
            else:
                ddd[k] = v

        d = {element_tag: ddd}

    has_attribs = xml_element.attrib and not skip_attributes

    # Add attributes
    if has_attribs:

        attrib = OrderedDict()

        for k, v in six.iteritems(xml_element.attrib):

            # Tag modify for attribute names
            new_k = '@' + k
            if tag_modify:

                for tag in tag_modify:
                    new_k = new_k.replace(tag[0], tag[1])

            # Cast value for attribute values
            new_v = v
            if cast_values and (new_k not in cast_ignore):
                new_v = cast_int_float_string(new_v)

            attrib[new_k] = new_v

        d[element_tag].update((k, v) for k, v in six.iteritems(attrib))

    # Add text elements
    text = xml_element.text
    if (text is not None) and (text.strip()):

        if cast_values and (element_tag not in cast_ignore):
            text = cast_int_float_string(text)

        if children or has_attribs:
            if text:
                d[element_tag]['_text'] = text

        else:
            d[element_tag] = text

    return d
