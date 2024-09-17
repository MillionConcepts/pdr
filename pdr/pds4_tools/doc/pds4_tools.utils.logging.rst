pds4_tools.utils.logging module
===============================

.. automodule:: pds4_tools.utils.logging

Classes
-------

.. autosummary::

    PDS4Logger
    PDS4StreamHandler
    PDS4SilentHandler
    PDS4Formatter

Functions
---------

.. autosummary::

    logger_init
    set_loglevel

Details
-------

.. function:: pds4_tools.set_loglevel

    An alias of :func:`set_loglevel`.

.. autoclass:: PDS4Logger
    :members:
    :undoc-members:
    :show-inheritance:

.. autoclass:: PDS4StreamHandler
    :members:
    :undoc-members:
    :show-inheritance:

.. autoclass:: PDS4SilentHandler
    :members:
    :undoc-members:
    :show-inheritance:

    .. autoattribute:: name
    .. autoattribute:: is_quiet

    .. automethod:: get_level
    .. automethod:: set_level
    .. automethod:: setLevel

.. autoclass:: PDS4Formatter
    :members:
    :undoc-members:
    :show-inheritance:


.. autofunction:: logger_init
.. autofunction:: set_loglevel
