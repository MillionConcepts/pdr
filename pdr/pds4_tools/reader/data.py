from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import copy
import numpy as np

from .data_types import pds_to_numpy_name

from ..utils.compat import NUMPY_LT_2_0, OrderedDict, np_issubclass
from ..extern import six


# List of comparison functions. Used in __array_wrap__ to ensure they only
# return plain ``np.ndarray`` or ``np.ma.MaskedArray`` as opposed to `PDS_ndarray`
# or `PDS_marray`.
_comparison_functions = set(
    [np.greater, np.greater_equal, np.less, np.less_equal,
     np.not_equal, np.equal,
     np.isfinite, np.isinf, np.isnan, np.sign, np.signbit])


class PDS_array(object):
    """ A factory and helper class to work with PDS_ndarray and PDS_marray.

    Intended such that `PDS_ndarray` and `PDS_marray` never need to be separately imported or called, and
    rather that all initialization and type checking should go through this helper class.
    """

    def __new__(cls, data, meta_data=None, masked=None, **options):
        """ Convert the input into a PDS array.

        Parameters
        ----------
        data : array_like
            Input data, of any dimension or content.
        meta_data : Meta_ArrayStructure or Meta_Field, optional
            Input meta-data.
        masked: bool or None, optional
            If True, forces a PDS masked array as output. If False, forces a PDS non-masked array as output.
            Defaults to None, which determines output array-type based on input.
        options : dict, optional
            Arguments to pass directly into the NumPy array initializer.

        Returns
        -------
        PDS_ndarray or PDS_marray
            A ``PDS_ndarray`` is returned if the input data is not masked, otherwise a ``PDS_marray`` will
            be returned; unless ``masked`` is a bool. Both array types will contain a view (rather than a copy)
            of the original data if the input is an ``np.ndarray`` or its subtype.
        """

        use_masked = (masked is True) or (isinstance(data, np.ma.MaskedArray) and (masked is not False))
        use_unmasked = (masked is False) or (isinstance(data, (np.ndarray, list, tuple)) and (not use_masked))

        if use_masked:
            return PDS_marray(data, meta_data=meta_data, **options)

        elif use_unmasked:
            return PDS_ndarray(data, meta_data=meta_data, **options)

        raise TypeError('Unknown data kind.')

    @classmethod
    def get_array(cls, masked):
        """ Obtain a PDS array type.

        Parameters
        ----------
        masked : bool
            If True, a PDS array class subclassing ``np.ma.MaskedArray`` is returned. Otherwise a PDS
            array class subclassing the regular ``np.ndarray`` is returned.

        Returns
        -------
        PDS_ndarray or PDS_marray
            A PDS array class. See *masked*.
        """

        if masked:
            return cls.get_marray()

        return cls.get_ndarray()

    @staticmethod
    def get_ndarray():
        """
        Returns
        -------
        PDS_ndarray
            A PDS array class based on ``np.ndarray``.
        """
        return PDS_ndarray

    @staticmethod
    def get_marray():
        """
        Returns
        -------
        PDS_marray
            A PDS array class based on ``np.ma.MaskedArray``.
        """

        return PDS_marray

    @classmethod
    def isinstance(cls, input):
        """
        Parameters
        ----------
        input : any

        Returns
        -------
        bool
            True if *input* is an instance of PDS_ndarray or PDS_marray. False otherwise.
        """
        return isinstance(input, (cls.get_ndarray(), cls.get_marray()))


class PDS_ndarray(np.ndarray):
    """ PDS ndarray, enabling some record array functionality and having a meta_data attribute.

    Subclasses ndarrays such that we can provide meta data for an individual array or table field.

    Inherits all Attributes from ``np.ndarray``.

    Parameters
    ----------
    data : array_like
        Data for the array.
    meta_data : Meta_ArrayStructure or Meta_Field, optional
        Meta-data for the array.
    options : dict, optional
        NumPy keywords to pass to the ``np.ndarray`` initializer.

    Attributes
    ----------
    meta_data : Meta_ArrayStructure, Meta_Field or None
        Meta-data for the array. Defaults to None if no meta-data was given on initialization
        or has been set.
    """

    def __new__(cls, data, meta_data=None, **options):
        obj = np.asanyarray(data, **options).view(cls)

        if meta_data is None:
            meta_data = getattr(data, 'meta_data', OrderedDict())

        obj.meta_data = meta_data

        return obj

    def __getitem__(self, idx):
        """
        Parameters
        ----------
        idx : str, slice, array_like
            Standard ``np.ndarray`` indexes: including field name, list of field names, record number or
            slice, or an array-like of record numbers.

        Returns
        -------
        PDS_ndarray, np.void, np.record, or any scalar
            Item(s) in the array for key. If the index is selecting a field(s) or multiple records
            then the meta_data will be preserved for those fields or records.
        """
        obj = super(PDS_ndarray, self).__getitem__(idx)

        # For structured arrays, retrieve the correct meta_data portion if we are not obtaining all of the
        # fields
        if isinstance(obj, np.ndarray):
            obj = obj.view(PDS_ndarray)
            obj.meta_data = self._meta_data_resolve(idx)

        return obj

    def __reduce__(self):
        """ Subclassed to ensure pickling preserves the ``meta_data`` attribute. """

        default_state = super(PDS_ndarray, self).__reduce__()
        new_state = default_state[2] + (self.meta_data,)

        return default_state[0], default_state[1], new_state

    def __setstate__(self, state):
        """ Subclassed to ensure pickling preserves the ``meta_data`` attribute. """

        self.meta_data = state[-1]
        super(PDS_ndarray, self).__setstate__(state[0:-1])

    def __repr__(self):
        """ Subclassed to ensure that scalars take-on their normal dtype, instead of being a 0-d array. """

        # For scalars convert to correct NumPy type and then use regular repr.  This ensures we do
        # not get back a type of this array with a single value when using functions that return just one
        # value (e.g. ``np.min`` or ``np.max``), but rather just the value, which preserved regular NumPy
        # behavior.
        if self.ndim == 0:
            return repr(self.item())

        return super(PDS_ndarray, self).__repr__()

    def __array_finalize__(self, obj):
        """
        Subclassed to ensure that creation and views correctly set and preserve the ``meta_data``
        attribute. """

        if obj is None:
            return

        self.meta_data = getattr(obj, 'meta_data', OrderedDict())

    def __array_wrap__(self, out_arr, context=None, return_scalar=False):
        """
        Based on AstroPy ``Column.__array_wrap__`` implementation. __array_wrap__ is
        called at the end of every ufunc.

        "Normally, we want a PDS_ndarray object back and do not have to do anything
        special. But there are two exceptions:

        1) If the output shape is different (e.g. for reduction ufuncs
           like sum() or mean()), a PDS_array makes little sense, so we return
           the output viewed as the array content (ndarray or MaskedArray).
           For this case, if numpy tells us to ``return_scalar`` (for numpy
           >= 2.0, otherwise assume to be true), we use "[()]" to ensure we
           convert a zero rank array to a scalar. (For some reason np.sum()
           returns a zero rank scalar array while np.mean() returns a scalar;
           So the [()] is needed for this case.)

        2) When the output is created by any function that returns a boolean
           we also want to consistently return an array rather than a PDS_ndarray"
        """

        if NUMPY_LT_2_0:
            out_arr = super(PDS_ndarray, self).__array_wrap__(out_arr, context)
            return_scalar = True
        else:
            out_arr = super(PDS_ndarray, self).__array_wrap__(out_arr, context, return_scalar)

        if (self.shape != out_arr.shape or
            (isinstance(out_arr, PDS_ndarray) and
             (context is not None and context[0] in _comparison_functions))):
            return out_arr[()] if return_scalar else out_arr.data
        else:
            return out_arr

    def copy(self, order='C'):
        """ Copy the array.

        Parameters
        ----------
        order : {'C', 'F', 'A', 'K'}, optional
            Controls the memory layout of the copy. 'C' means C-order, 'F' means F-order, 'A' means 'F' if
            a is Fortran contiguous, 'C' otherwise. 'K' means match the layout of a as closely as possible.

        Returns
        -------
        PDS_ndarray
            An array with both the data and meta data copied.
        """

        try:
            obj = super(PDS_ndarray, self).copy(order=order)
        except TypeError:
            obj = super(PDS_ndarray, self).copy()

        obj.meta_data = copy.deepcopy(getattr(self, 'meta_data', OrderedDict()))

        return obj

    def field(self, key, val=None):
        """ Get or set data for a single field.

        Parameters
        ----------
        key : int or str
            Key to select the field on. Either the name of the field, or its index.
        val : any, optional
            If given, sets the field specified by *key* to have value of *val*.

        Returns
        -------
        any or None
            A view of the selected field, if val is None. Otherwise returns None.
        """

        # Resolve field name from field index.
        if isinstance(key, int):
            key = self.dtype.names[key]

        # Obtain field
        obj = self.__getitem__(key)

        # Either set field values or return the field
        if val is not None:
            self.set_field(data=val, meta_data=obj.meta_data, name=key)

        else:
            return obj

    def set_field(self, data, meta_data, name=None):
        """ Set data and meta data for a single field.

        Parameters
        ----------
        data : any
            Data to set for the field.
        meta_data : Meta_Field
            Meta data to set for the field. If *name* is None, then the field name to set *data* for will
            be pulled from this attribute.
        name : str, optional
            The name of the field to set data for.

        Returns
        -------
        None
        """

        if (name is None) and (meta_data is not None):
            name = pds_to_numpy_name(meta_data.full_name())

        self[name] = data
        self.meta_data[name] = meta_data

    def _meta_data_resolve(self, key):
        """
        Parameters
        ----------
        key : str, slice, array_like
            Standard ``np.ndarray`` indexes, including field name, list of field names, record number or
            slice, or an array-like of record numbers.

        Returns
        -------
        any
            Meta data for the *key*.
        """

        meta_data = OrderedDict()

        # For a string key, we are requesting a single field and therefore just that field's meta data
        if isinstance(key, six.string_types):
            meta_data = self.meta_data.get(key)

        # For a slice, we must be requesting records, and therefore all fields, and therefore all meta data
        elif isinstance(key, slice):
            meta_data = self.meta_data

        # For multi-valued keys
        elif isinstance(key, (np.ndarray, tuple, list)):

            # Cast multi-valued keys to an ndarray so we can get its type
            key = np.asarray(key)

            # For character multi-valued keys, we must be requesting multiple fields
            if np.issubdtype(key.dtype, np.character):

                meta_data = OrderedDict()

                for _key in key:

                    if _key in self.meta_data:
                        meta_data[_key] = self.meta_data.get(_key)

            # For non-character multiple-valued fields, we must be requesting specific records and therefore
            # all fields, and therefore all meta data
            else:
                meta_data = self.meta_data

        return meta_data


class PDS_marray(np.ma.MaskedArray, PDS_ndarray):
    """ PDS masked array, enabling some record array functionality and having a meta_data attribute.

    Subclasses np.ma.MaskedArray such that we can provide meta data for an individual array or table field.

    Inherits all Attributes from ``np.ma.MaskedArray``.

    Parameters
    ----------
    data : array_like
        Data for the array.
    meta_data : Meta_ArrayStructure or Meta_Field, optional
        Meta-data for the array.
    options : dict, optional
        NumPy keywords to pass to the ``np.ndarray`` initializer.

    Attributes
    ----------
    meta_data : Meta_ArrayStructure, Meta_Field or None
        Meta-data for the array. Defaults to None if no meta-data was given on initialization
        or has been set.
    """

    def __new__(cls, data, meta_data=None, **options):

        obj = np.ma.MaskedArray.__new__(cls, data=data, **options)

        if meta_data is None:
            meta_data = getattr(data, 'meta_data', OrderedDict())

        obj.meta_data = meta_data

        return obj

    def __getitem__(self, idx):
        """
        Parameters
        ----------
        idx : str, slice, array_like
            Standard ``np.ndarray`` indexes: including field name, list of field names, record number or
            slice, or an array-like of record numbers.

        Returns
        -------
        PDS_marray, np.ma.mvoid, any scalar
            Item(s) in the array for key. If the index is selecting a field(s) or multiple records
            then the meta_data will be preserved for those fields or records.
        """

        obj = super(PDS_marray, self).__getitem__(idx)

        # For structured arrays, retrieve the correct meta_data portion if we are not obtaining all of the
        # fields
        if isinstance(obj, np.ndarray) and not isinstance(obj, np.ma.mvoid) and \
                not isinstance(obj, np.ma.core.MaskedConstant):

            meta_data = self._meta_data_resolve(idx)
            obj = obj.view(PDS_marray)
            obj.meta_data = meta_data

            # We update _optinfo, because otherwise selecting a single field from multiple fields, and then
            # selecting a few records for that single field will give all meta-data rather than for a single
            # field (via recovering it from _optinfo in ``np.ma.MaskedArray._update_from``)
            if 'meta_data' in obj._optinfo:
                obj._optinfo['meta_data'] = meta_data

        return obj

    def __reduce__(self):
        """ Subclassed to ensure pickling preserves the ``meta_data`` attribute. """

        default_state = super(PDS_marray, self).__reduce__()
        new_state = default_state[2] + (self.meta_data,)

        return default_state[0], default_state[1], new_state

    def __setstate__(self, state):
        """ Subclassed to ensure pickling preserves the ``meta_data`` attribute. """

        self.meta_data = state[-1]
        super(PDS_marray, self).__setstate__(state[0:-1])

    def __repr__(self):
        """ Subclassed to ensure that scalars take-on their normal dtype, instead of being a 0-d array,
            and to adjust returned value to properly reflect the class name. """

        # For scalars convert to correct NumPy type and then use regular repr.  This ensures we do
        # not get back a type of this array with a single value when using functions that return just one
        # value (e.g. ``np.min`` or ``np.max``), but rather just the value, which preserved regular NumPy
        # behavior.
        if self.ndim == 0:
            return repr(self.item())

        # Avoid outputting masked_PDS_marray[...] or masked_PDS_ndarray, instead use just PDS_marray[...]
        repr_str = super(PDS_marray, self).__repr__()

        try:
            idx = repr_str.index('(')
            repr_str = self.__class__.__name__ + repr_str[idx:]

        except ValueError:
            pass

        return repr_str

    def __array_finalize__(self, obj):
        """
        Subclassed to ensure that creation and views correctly set and preserve the ``meta_data``
        attribute.
        """

        if obj is None:
            return

        self.meta_data = getattr(obj, 'meta_data', OrderedDict())
        np.ma.MaskedArray.__array_finalize__(self, obj)

    def __array_wrap__(self, out_arr, context=None, return_scalar=False):
        """
        Based on AstroPy ``Column.__array_wrap__`` implementation. __array_wrap__ is
        called at the end of every ufunc.

        "Normally, we want a PDS_marray object back and do not have to do anything
        special. But there are two exceptions:

        1) If the output shape is different (e.g. for reduction ufuncs
           like sum() or mean()), a PDS_array makes little sense, so we return
           the output viewed as the array content (ndarray or MaskedArray).
           For this case, if numpy tells us to ``return_scalar`` (for numpy
           >= 2.0, otherwise assume to be true), we use "[()]" to ensure we
           convert a zero rank array to a scalar. (For some reason np.sum()
           returns a zero rank scalar array while np.mean() returns a scalar;
           So the [()] is needed for this case.)

        2) When the output is created by any function that returns a boolean
           we also want to consistently return an array rather than a PDS_marray."
        """

        if NUMPY_LT_2_0:
            out_arr = super(PDS_marray, self).__array_wrap__(out_arr, context)
            return_scalar = True
        else:
            out_arr = super(PDS_marray, self).__array_wrap__(out_arr, context, return_scalar)

        if (self.shape != out_arr.shape or
                (isinstance(out_arr, PDS_marray) and
                     (context is not None and context[0] in _comparison_functions))):
            return out_arr[()] if return_scalar else out_arr.data
        else:
            return out_arr

    def _update_from(self, obj):
        """ Subclassed to ensure the ``meta_data`` attribute is not lost under some conditions.

        Upon certain operations that create a new masked array, NumPy uses ``_update_from`` to set properties
        the new array to match an old one.
        """

        if hasattr(obj, 'meta_data'):
            self.meta_data = obj.meta_data

        super(PDS_marray, self)._update_from(obj)

    def view(self, dtype=None, type=None, fill_value=None):
        """ Return a view of the PDS_marray data.

        Subclassed to fix a NumPy bug that breaks setting fill_value when subselecting a field from a
        structured array.
        """

        try:

            obj = super(PDS_marray, self).view(dtype=dtype, type=type, fill_value=fill_value)

            # Fix bug in NumPy < v1.10, which resets fill value on ``view`` if mask is not nomask
            if ((dtype is None) or ((type is None) and np_issubclass(dtype, np.ma.MaskedArray))) and \
                (fill_value is None):

                obj._fill_value = self._fill_value

        except TypeError:

            # NumPy < v1.8 did not have a fill value attribute for ``view``
            obj = super(PDS_marray, self).view(dtype=dtype, type=type)

        return obj

    def filled(self, fill_value=None):
        """ Return a copy of self, with masked values filled with a given value.

        Parameters
        ----------
        fill_value : scalar, optional
            The value to use for invalid entries. If None, the ``fill_value`` attribute
            of the array is used instead. Defaults to None.

        Returns
        -------
        PDS_ndarray
            A copy of ``self`` with invalid entries replaced by *fill_value*.
        """

        obj = super(PDS_marray, self).filled(fill_value)
        obj = obj.view(PDS_ndarray)
        obj.meta_data = copy.deepcopy(getattr(self, 'meta_data', OrderedDict()))

        return obj

    def compressed(self):
        """ Return a copy of all the non-masked data as a 1-D array.

        Returns
        -------
        PDS_ndarray
            A new array holding the non-masked data is returned.
        """

        obj = super(PDS_marray, self).compressed()
        obj = obj.view(PDS_ndarray)
        obj.meta_data = copy.deepcopy(getattr(self, 'meta_data', OrderedDict()))

        return obj

    def copy(self, order='C'):
        """ Copy the array.

        Parameters
        ----------
        order : {'C', 'F', 'A', 'K'}, optional
            Controls the memory layout of the copy. 'C' means C-order, 'F' means F-order, 'A' means 'F' if
            a is Fortran contiguous, 'C' otherwise. 'K' means match the layout of a as closely as possible.

        Returns
        -------
        PDS_marray
            An array with both the data and meta data copied.
        """

        try:
            obj = super(PDS_marray, self).copy(order=order)
        except TypeError:
            obj = super(PDS_marray, self).copy()

        obj.meta_data = copy.deepcopy(getattr(self, 'meta_data', OrderedDict()))

        return obj

    @property
    def fill_value(self):
        return super(PDS_marray, self).fill_value

    @fill_value.setter
    def fill_value(self, value):
        self.set_fill_value(value)

    def set_fill_value(self, value=None):
        """ Set the filling value.

        Parameters
        ----------
        value : scalar, optional
            A value used to fill the invalid entries of the masked array.

        Returns
        -------
        None
        """

        # Partial fix for NumPy bug 9748
        # Multi-dimensional fields in structured masked arrays raise exceptions upon attempt
        # to set fill_value under some NumPy versions. This fix properly sets fill value, however
        # the fill value is not saved upstream in the PDS_marray the multi-dimensional field it
        # was subselected from until NumPy implements the fix in the ticket.
        if np.isscalar(self._fill_value) and (self.ndim > 1):
            self._fill_value = np.array(self._fill_value)

        super(PDS_marray, self).set_fill_value(value)

    def set_field(self, data, meta_data, name=None):
        """ Set data and meta data for a single field.

        Parameters
        ----------
        data : any
            Data to set for the field.
        meta_data : Meta_Field
            Meta data to set for the field. If *name* is None, then the field name to set *data* for will
            be pulled from this attribute.
        name : str, optional
            The name of the field to set data for.

        Returns
        -------
        None
        """

        if (name is None) and (meta_data is not None):
            name = pds_to_numpy_name(meta_data.full_name())

        if isinstance(data, np.ma.MaskedArray):
            # NumPy does not properly set fill value in record arrays for multi-dimensional fields
            if isinstance(self.fill_value[name], np.ndarray) and self.fill_value[name].ndim > 0:
                self.fill_value[name][:] = data.fill_value
            else:
                self[name].set_fill_value(data.fill_value)

        super(PDS_marray, self).set_field(data, meta_data, name=name)
