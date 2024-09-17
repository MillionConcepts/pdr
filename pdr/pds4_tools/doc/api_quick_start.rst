:orphan:

.. _api_quick_start:

PDS4 Python Tools - API - Quick Start
=====================================

These pages are intended primarily for developers wishing to write new tools in
Python for PDS4. The pds4_tools API provides a simple interface to read-in PDS4
data and labels. The API also provides common meta-data directly from the labels
in an easily and programmatically consumable way.

We recommend that you first look at the :ref:`User Manual <user_manual>`  for
some familiarity with reading in PDS4 data. The :ref:`full API reference <index>`
is also available.

As the User Manual notes, to read-in data, you will most likely
use the ``pds4_tools.read`` function, which is an alias for,

`pds4_read`

Developers wishing to work with Labels may be interested in the ``Label``
object,

`Label`

This object provides a partial wrapper around Python's ``ElementTree``, while
greatly improving support for namespace handling, adding support for label
pretty printing, transformation to dictionaries and certain other features.

The ``pds4_read`` function will return a ``StructureList`` object,

`StructureList`

That object, which can be accessed in both the dict-like and list-like manner,
provides access to the ``Structure``'s, each of which contains the data and
label portions for a single data structure (e.g. for a single Array_3D, or a
single Table_Binary, etc).

The ``Structure``'s developers are most likely to find useful are:

| `ArrayStructure`
| `TableStructure`

We also recommend that you look at the attributes and methods they inherit
from the `Structure` class. Below we touch only on the most important attributes.

Each ``Structure`` has a .data, attribute. This attribute provides access
to the read-in data of the structure. For PDS4 arrays, the underlying data object
is a NumPy ``ndarray``, and for PDS4 tables it is a structured ``ndarray``.
The actual data object is a subclass of ``ndarray`` that allows most
``recarray`` functionality: `PDS_ndarray` for non-masked data and
`PDS_marray` for masked data (where masked data is present in delimited tables
with empty numeric field values or alternatively for Special_Constants per
the ``.as_masked`` method of a Structure). These data objects, may be used entirely
as normal ``ndarray``'s, while also containing a .meta_data attribute that describes
the label portion the field or array originated from (see below). For Tables,
in addition to accessing data directly from the underlying NumPy array, the
User Manual describes how fields and records can be accessed in multiple ways
via TableStructure methods.

Each ``Structure`` has a .meta_data attribute. This is essentially a ``dict``
representation of its .label attribute, along with certain methods that vary
based on the type of structure but generally serve to improve the usability
and accessibility of some commonly used aspects of the meta data. The goal of
the .meta_data attribute is to provides easy and convenient access to known
portions of the label for that structure. For Tables, each field's data
also has a .meta_data attribute (the array returned when accessing field data
subclasses ``ndarray`` to add this), which provides the meta data available
in the label for that particular Field (e.g. its PDS4 data type, description,
name, etc). For Arrays, meta data is also accessible via the .meta_data
attribute, which includes the label portion for the entire array. The relevant
meta data classes include: `Meta_ArrayStructure`, `Meta_TableStructure` and
`Meta_Field`.

Both ``StructureList`` and ``Structure`` have a .label attribute. The
former provides access to the entire label, the later provides access to
label portion describing just the structure. The attribute returns a
`Label` object. The ``Label`` object is very similar, but does not entirely
subclass, Python's `ElementTree <https://docs.python.org/2/library/xml.etree.elementtree/>`_.
However, it provides much of the same functionality, including .tag, .text,
.tail, .attrib, and the find(), findall() and findtext() methods, while also
providing certain improvements and compatibility across a wide swath of Python
versions. We recommend developers look at both ``Label`` and ``ElementTree``
documentation for additional details of how ``Label`` can be used. ``Label``
also allows easy extraction of the ElementTree object that underlies it if desired.

Developers interested in log handling should see `pds4_tools.set_loglevel`.

We recommend you look at the API of the above linked classes, as well as at the
:ref:`User Manual <user_manual>` for pds4_tools for additional explanations and
usage examples, which should answer most questions that likely came up
while reading this page. For the rest, including other convenience classes,
methods and functions, consult the full API reference.