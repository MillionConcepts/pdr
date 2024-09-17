:orphan:

.. _user_manual:

PDS4 Python Tools - User Manual
===============================

.. contents:: Table of Contents
    :local:
    :backlinks: none

1.1  Introduction
-----------------

PDS4 Python Tools are several modules integrated into a Python library to
provide access to PDS4 data.


1.2  Installation
-----------------

Installation instructions are currently provided at:

https://sbnwiki.astro.umd.edu/wiki/Python_PDS4_Tools#Installation


1.3  Quick Tutorial
-------------------

This chapter provides a quick introduction into using PDS4 Python Tools. The
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>> import pds4_toolsfrom pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>> import pds4_toolsfrom pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>> import pds4_tools
from pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>> import pds4_tools
from pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>>
from pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>>
from pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>>
from pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>>
from pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>>
from pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>>
from pdr import pds4_tools
goal is to demonstrate basic features without getting into too much detail.
If you are a first time or occasional user, this is where you should start.

After installing PDS4 Python Tools, start Python and load the PDS4 tools library.
Note that the module name is all lower case.

>>> import pds4_tools

Opening a PDS4 file
___________________

Once ``pds4_tools`` is imported, we can open an existing data file from its
describing label,

>>> structures = pds4_tools.read('/path/to/label.xml')       # Local
>>> structures = pds4_tools.read('http://url.com/label.xml') # Remote

For remote URLs, the files will be downloaded to a temporary on-disk cache
and deleted upon Python interpreter exit.

The `pds4_tools.read()` function has several optional arguments that control warnings,
scaling, and lazy-loading. It returns a PDS4 Tools object called a `StructureList`
which is a ``list``-like object, consisting of Structure objects. A Structure typically
consists of a data array or table, and the label portion that describes that it.

>>> structures[0]                   # First Structure
>>> structures[0:2]                 # First two Structures
>>> structures['Integration']       # Structure with LID or name of 'Integration'

The StructureList has a useful method, `StructureList.info()`, which summarizes
the data structure content of the opened PDS4 file::

    0 : Array_3D_Spectrum 'Primary' (3 axes, 21 x 10 x 36)
    1 : Table_Binary 'Integration' (9 fields x 1000 records)
    2 : Table_Binary 'Engineering' (38 fields x 1000  records)
    3 : Table_Binary 'Binning' (9 fields x 1000 records)
    4 : Table_Binary 'PixelGeometry' (12 fields x 10000 records)
    5 : Table_Binary 'SpacecraftGeometry' (36 fields x 21 records)
    6 : Table_Binary 'Observation' (22 fields x 1 records)

Note that LIDs and names are case-sensitive.

Working with large files
________________________

The `pds4_tools.read()` function, with default arguments, will immediately read
all data structures into memory all at once. This may not be desired for labels
describing many large data structures at once, and for this reason the
function supports a ``lazy_load=True`` argument.

>>> structures = pds4_tools.read('/path/to/label.xml', lazy_load=True)

When enabled, this argument ensures that data will only be transparently read-in
upon first attempt to access that data. This has minimal impact on smaller files
as well.

Additionally, an interface is available to read only portions of PDS4 arrays into
memory at once. For more information, see
:ref:`Working with Image and Array Data <working_with_image_data>`.

.. _working_with_pds4_labels:

Working with PDS4 Labels
________________________

As mentioned earlier, each element of a `StructureList` is a `Structure` object
with ``.label``, ``.meta_data`` and ``.data`` attributes that can be used to
access the label and data portions of the Structure. The StructureList
itself contains a ``.label`` attribute, which can be used to access the entire
label.

If you are not familiar with XML, a brief example would be,

.. code-block:: xml

    <record_length unit="byte">65</record_length>

Where the ``record_length`` is called an element, the ``unit`` is called an
attribute, its value is called an attribute value, and in this case the
elementâ€™s text is ``65``.

The ``.label`` attribute of a `StructureList` or a `Structure` is a `Label` instance,
another PDS4 Tools object. It provides access to the XML label content, although
some knowledge of `XPATH expressions <https://docs.python.org/3/library/xml.etree.elementtree.html#example>`_
is generally required for search and usage. You may however use the
``label.to_dict()`` and ``label.to_string()`` methods to obtain more familiar
access. Below we provide some examples of using ``.label`` and ``.meta_data``.

To search a Label instance, you may use,

.. code-block:: python

    >>> structures.label.find('.//record_length').text
    65
    >>> structures.label.find('.//record_length').attrib
    {'unit': 'byte'}
    >>> structures.label.find('.//start_date_time').text
    '2015-06-01T00:36:23.03Z'

This uses XPATH to find the first occurrence of the ``start_date_time`` and
``record_length`` elements, no matter how deep in the XML tree they are.

If there are multiple occurrences of an element, you may use,

.. code-block:: python

    >>> lids = structures.label.findall('.//local_identifier')
    >>> lids[0].text
    'Primary'
    >>> lids[1].text
    'Integration'

To search for elements outside of the core PDS namespace, one may use,

.. code-block:: python

    >>> reference_time = structures.label.find('.//geom:geometry_reference_time_utc')
    >>> reference_time.text
    '2019-05-24T10:30:06.724Z'

For more details, we encourage you to see the `Supported XPATH syntax section
<https://docs.python.org/3/library/xml.etree.elementtree.html#example>`_
of the Python manual for ElementTree, which underlines the implementation of
the PDS4 Tools' Label object.

For an individual `Structure`, we can use ``.meta_data`` attribute to access the
associated label information. This attribute may be a number of `Meta_Class`
derived instances, all of which inherit from the ``OrderedDict`` Python data structure.
Below we show some sample meta data for an array described by the label,

.. code-block:: python

    >>> array_structure = structures['Primary']

    >>> array_structure.type
    'Array_3D_Spectrum'

    >>> array_structure.meta_data.keys()
    ['local_identifier', 'offset', 'axes', 'axis_index_order', 'description', 'Element_Array', 'Axis_Array']

    >>> array_structure.meta_data['local_identifier']
    'Primary'

    >>> array_structure.meta_data['Axis_Array']['axis_name']
    'Time'

The organization and naming of ``.meta_data`` attributes directly follow those in
the label, with a few exceptions that are discussed in the notes for each relevant
meta data class.

Working with Data
_________________

.. _working_with_image_data:

Image and Array Data
~~~~~~~~~~~~~~~~~~~~

If a Structure's data is an array, the data attribute of the `ArrayStructure`
object will be an object that is for all intents and purposes identical to a NumPy
``ndarray`` object, except possessing an additional meta_data attribute.
Refer to the `NumPy documentation <http://docs.scipy.org/doc/numpy/user/quickstart.html>`_
for the complete details on manipulating these numerical arrays.

.. code-block:: python

    >>> structures[0].id
    'Primary'
    >>> data = structures[0].data

Here ``data`` contains the data of the first `Structure`, which
corresponds to the Structure with a local identifier of ``Primary``.
Alternatively, you can access a Structure by its local identifier or its name,

.. code-block:: python

    >>> data = structures['Primary'].data

For very large arrays it may be convenient to read-in only portions of the array
into memory at a time. This may be done with the `ArraySection` interface if
``lazy_load`` is set during the initial read-in call,

.. code-block:: python

    >>> data = structures['Large_Array'].section[0:50000, 25000:50000]

For data with Special Constants, such as flag values indicating missing data,
you may access a version of the structure where numeric flag values are masked.

.. code-block:: python

    >>> data = structures['Primary'].as_masked().data
    >>> data = structures['Large_Array'].as_masked().section[0:50000, 25000:50000]

For data access through masked arrays, mathematical functions such as minimum and
maximum and many other operations will return correct results instead of counting
flag values.

In all cases, the returned data has many useful attributes and methods for a
user to get information about the array; e.g.,

.. code-block:: python

    >>> data.shape
    (21, 10, 36)
    >>> data.dtype.name
    'float32'

Since image data is a NumPy array, we can slice it, view it, and perform mathematical
operations on it. To see the pixel value at i1=5, i2=2, i3=10:

.. code-block:: python

    >>> print(data[4, 1, 9])

Note that Python is 0-indexed. Additionally, all PDS4 data is required to be
last index fastest, and the read-in array dimensions will follow the
``sequence_number`` as provided in the labels.

The next example shows that NumPy array data can be manipulated in a single
command, specifically a multiplication and division of all values,

.. code-block:: python

    >>> data = (data * 10) / 5

To access label meta data for an `ArrayStructure`, we may use its ``.meta_data``
attribute. See the :ref:`Working with PDS4 Labels <working_with_pds4_labels>`
section for examples, as well as the `Meta_ArrayStructure` class.

Table Data
~~~~~~~~~~

If working with a table, the data inside the `TableStructure` can be accessed
in multiple ways. Similar to array data, an individual field's data will be an
object that is for all intents and purposes identical to a NumPy ``ndarray``
object, except possessing an additional meta_data attribute. The underlying
data object containing all fields is similar to a ``recarray``. Refer to the
`NumPy documentation <http://docs.scipy.org/doc/numpy/user/quickstart.html>`_
for the complete details on manipulating these numerical arrays.

Common ways to access data for individual columns (or fields, in PDS4 parlance) are,

.. code-block:: python

    # Access the 'Wavelength' field in the 'Integration' Table
    >>> structures['Integration']['Wavelength']
    >>> structures['Integration'].field('Wavelength')

    # Access the first field
    >>> structures['Integration'].field(0)

    # Access multiple fields at the same time
    >>> structures['Integration'][['Timestamp', 'Wavelength']]

As can be seen in these examples, a field can be obtained by either index or
by name.

In many cases it is preferable to access fields by their name, as the field
name is entirely independent of its physical order in the table. As with
Structure names, field names are case-sensitive.

To access the data record-wise,

.. code-block:: python

    # Access the entire first record (all fields) in the 'Integration' Table
    >>> structures['Integration'][0]

    # Access the first 10 records (all fields)
    >>> structures['Integration'][0:10]

The underlying data object, which is essentially a NumPy record array, may be
accessed directly via,

.. code-block:: python

    >>> structures['Integration'].data

The NumPy array returned by the above calls contain the data for the
requested selection. We can slice it, view it, and perform mathematical operations
as desired.

.. code-block:: python

    >>> field = structures['Integration']['Wavelength']

    >>> field[0:10]   # The first 10 rows for field 'Wavelength'
    >>> field.mean()  # Take the mean of the field
    >>> field * 5     # Multiply each value in the field by 5

For data with Special Constants, such as flag values indicating missing data,
you may access a version of the structure where numeric flag values are masked.

.. code-block:: python

    # Access a view of the table where flag values are masked
    >>> masked_table = structures['Integration'].as_masked()

    # Data access and operations are unchanged, e.g.:
    >>> masked_table['Wavelength']
    >>> masked_table.field('Wavelength')
    >>> masked_table.field(0)

For data access through masked tables, mathematical functions such as minimum and
maximum and many other operations will return correct results instead of counting
flag values. This is also often advantageous when plotting data, where common
software will exclude masked values. The underlying label must correctly describe
Special Constants for them to be masked.

The object returned when accessing individual fields is for all intents and purposes
identical to a NumPy ``ndarray`` object. However, it also provides a ``.meta_data``
than can give the field's meta data as recorded in the label,

.. code-block:: python

    >>> field.meta_data['unit']
    'deg'

    >>> field.meta_data.keys()
    ['name', 'location', 'data_type', 'length', 'unit', 'description']

To access label meta data for the entire `TableStructure`, we may use its
``.meta_data`` attribute. See the :ref:`Working with PDS4 Labels <working_with_pds4_labels>`
section for examples, as well as the `Meta_TableStructure` class.

Visualization
_____________

PDS4 Tools ship with a GUI that enables basic visualization of PDS4 data. To use
this,

.. code-block:: python

    >>> import pds4_tools

You may then call the GUI via,

.. code-block:: python

    >>> # Call an empty Viewer, allowing you to browse disk for file
    >>> pds4_tools.view()
    >>>
    >>> # Specify path to label describing the data product to visualize
    >>> pds4_tools.view('/path/to/label.xml')
    >>>
    >>> # Specify structures that have already been read-in
    >>> structures = pds4_tools.read('/path/to/label.xml')
    >>> pds4_tools.view(from_existing_structures=structures)

Note that the basic GUI works via Tkinter, which generally ships with
installations of Python. To enable Image View and Plot View, you must
also have recent versions of `Matplotlib <http://matplotlib.org>`_
installed.

1.4  API
--------

The full API reference is available :ref:`here <index>`.
