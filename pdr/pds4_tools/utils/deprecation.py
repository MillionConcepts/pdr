from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import warnings
import textwrap
import functools

from . import compat


class PDS4ToolsDeprecationWarning(UserWarning):
    """ Custom warning for deprecated PDS4 Tools features.

    Notes
    -----
    Inherits from ``UserWarning`` rather than ``DeprecationWarning`` because the latter is not
    necessarily shown to user by default.

    Parameters
    ----------
    message : str, optional
        Message to show to user. When given, all other options are ignored.
    name : str, optional
        Name of feature that is deprecated. Required when *message* is absent.
    obj_type : str, optional
        Type of feature that is deprecated; e.g., function or class.  Required when *message* is absent.
    since : str, optional
        Version from which feature is deprecated.  Required when *message* is absent.
    removal : str or bool, optional
        Version from which feature may be removed. Defaults to the next release after *since*,
        unless set to False.
    alternative : str, optional
        An alternative API to suggest to the user.
    addendum : str, optional
        An addendum following the main deprecation message.
    """

    def __init__(self, message=None, name=None, obj_type=None, since=None, removal=None,
                 alternative=None, addendum=None):

        if not message:
            message = ('\nThe {0} {1} was deprecated in PDS4 Tools v{2}'.format(name, obj_type, since)
                    + (' and may be removed in v{0}.'.format(removal) if isinstance(removal, str) else
                      (' and may be removed in the following release.' if removal is not False else '.'))
                    + (' Use {0} instead.'.format(alternative) if alternative else '')
                    + (' {0}'.format(addendum) if addendum else ''))

        super(PDS4ToolsDeprecationWarning, self).__init__(message)


def warn_deprecated(since=None, message=None, name=None, obj_type=None, removal=None,
                    alternative=None, addendum=None, stacklevel=1):
    """ Emit a warning that a PDS4 Tools feature is deprecated.

    Parameters
    ----------
    since : str, optional
        Version from which feature is deprecated.  Required when *message* is absent.
    message : str, optional
        Message to show to user. When given, all other options are ignored.
    name : str, optional
        Name of feature that is deprecated. Required when *message* is absent.
    obj_type : str, optional
        Type of feature that is deprecated; e.g., function or class.  Required when *message* is absent.
    removal : str or bool, optional
        Version from which feature may be removed. Defaults to the next release after *since*,
        unless set to False.
    alternative : str, optional
        An alternative API to suggest to the user.
    addendum : str, optional
        An addendum following the main deprecation message.
    stacklevel : int, optional
        When above 1, makes the warning refer to deprecation()'s caller, rather than to the source of
        deprecation() itself. Defaults to 1.

    Returns
    -------
    None
    """

    warn_cls = PDS4ToolsDeprecationWarning
    warning = warn_cls(message=message,
                       name=name,
                       obj_type=obj_type,
                       since=since,
                       removal=removal,
                       alternative=alternative,
                       addendum=addendum)

    warnings.warn(warning, category=PDS4ToolsDeprecationWarning, stacklevel=stacklevel)


def deprecated(since=None, message=None, name=None, removal=None, alternative=None, addendum=None):
    """ Decorator to mark a function, property or class as deprecated.

    Notes
    -----
    Adapted from ``mpl._api.deprecation.deprecated``.

    Parameters
    ----------
    since : str, optional
        Version from which feature is deprecated.  Required when *message* is absent.
    message : str, optional
        Message to show to user. When given, all other options are ignored.
    name : str, optional
        Name of feature that is deprecated. Required when *message* is absent.
    removal : str or bool, optional
        Version from which feature may be removed. Defaults to the next release after *since*,
        unless set to False.
    alternative : str, optional
        An alternative API to suggest to the user.
    addendum : str, optional
        An addendum following the main deprecation message.

    Examples
    --------
    ::

        @deprecated('1.3')
        def func_to_deprecate():
            pass
    """

    def deprecate(obj, message=message, name=name, removal=removal,
                  alternative=alternative, addendum=addendum):

        if isinstance(obj, type):
            obj_type = 'class'
            func = obj.__init__
            name = name or obj.__name__
            old_doc = obj.__doc__

            def finalize(wrapper, new_doc):
                try:
                    obj.__doc__ = new_doc
                except (AttributeError, TypeError):
                    pass
                obj.__init__ = wrapper
                return obj

        elif isinstance(obj, property):
            obj_type = 'attribute'
            func = None
            name = name or obj.fget.__name__
            old_doc = obj.__doc__

            class _deprecated_property(property):

                def __init__(self, *args, **kwargs):
                    self.__doc__ = kwargs.get('doc')
                    super(_deprecated_property, self).__init__(*args, **kwargs)

                def __get__(self, instance, owner):
                    if instance is not None:
                        warn_deprecated(message=message, stacklevel=3)
                    return super(_deprecated_property, self).__get__(instance, owner)

                def __set__(self, instance, value):
                    if instance is not None:
                        warn_deprecated(message=message, stacklevel=3)
                    return super(_deprecated_property, self).__set__(instance, value)

                def __delete__(self, instance):
                    if instance is not None:
                        warn_deprecated(message=message, stacklevel=3)
                    return super(_deprecated_property, self).__delete__(instance)

            def finalize(_, new_doc):
                return _deprecated_property(
                    fget=obj.fget, fset=obj.fset, fdel=obj.fdel, doc=new_doc)

        else:
            obj_type = 'function'
            name = name or obj.__name__

            if isinstance(obj, classmethod):
                func = obj.__func__
                old_doc = obj.__doc__

                def finalize(wrapper, new_doc):
                    wrapper = functools.wraps(func)(wrapper)
                    wrapper.__doc__ = new_doc
                    return classmethod(wrapper)
            else:
                func = obj
                old_doc = obj.__doc__

                def finalize(wrapper, new_doc):
                    wrapper = functools.wraps(func)(wrapper)
                    wrapper.__doc__ = new_doc
                    return wrapper

        # Create deprecation message
        _warning = PDS4ToolsDeprecationWarning(name=name, obj_type=obj_type,
                                               since=since, removal=removal,
                                               alternative=alternative, addendum=addendum)
        message = str(_warning)

        # Create adjusted docstring that notes deprecation
        old_doc = textwrap.dedent(old_doc or '').strip('\n')

        notes_header = '\nNotes\n-----'
        if notes_header in old_doc:
            idx = old_doc.index(notes_header) + len(notes_header)
            pre_notes = old_doc[:idx]
            post_notes = old_doc[idx:]
        else:
            pre_notes = old_doc + '\n' + notes_header
            post_notes = ''

        new_doc = ('*[Deprecated]* {0}\n'
                   '.. deprecated:: {1}\n'
                   '   {2}\n'
                   '{3}').format(pre_notes, since, message.strip(), post_notes)

        def wrapper(*args, **kwargs):
            warn_deprecated(message=message, stacklevel=3)
            return func(*args, **kwargs)

        return finalize(wrapper, new_doc)

    return deprecate


def rename_parameter(since, old, new, func=None, removal=None):
    """ Decorator to indicate that parameter *old* of *func* is renamed to *new*.

    The actual implementation of *func* should use *new*, not *old*.  If *old*
    is passed to *func*, a deprecation warning is emitted, and its value is
    used unless *new* was also passed.

    Notes
    -----
    Adapted from ``mpl._api.deprecation.rename_parameter``.

    Parameters
    ----------
    since : str
        Version in which the parameter was renamed.
    old : str
        Old name of the parameter.
    new : str
        New name of the parameter.
    func : func, optional
        Function in which the parameter was renamed.
    removal : str or bool, optional
        Version in which support for the old parameter will be fully dropped.
        Defaults to the next release after *since*, unless set to False.

    Examples
    --------
    ::

        @rename_parameter('1.3', 'bad_name', 'good_name')
        def func(good_name):
            pass
    """

    if func is None:
        return functools.partial(rename_parameter, since, old, new, removal=removal)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        if old in kwargs:
            message = ('\nThe {0} parameter of {1} has been renamed {2} '.format(old, func.__name__, new)
                    + 'since PDS4 Tools v{0}'.format(since)
                    + (' and may be removed in v{0}.'.format(removal) if isinstance(removal, str) else
                      (' and may be removed in the following release.' if removal is not False else '.')))
            warn_deprecated(message=message, stacklevel=3)
            if new not in kwargs:
                kwargs[new] = kwargs.pop(old)
        return func(*args, **kwargs)

    return wrapper


def delete_parameter(since, name, func=None, removal=None, alternative=None):
    """ Decorator to indicate that parameter *name* of *func* is being deprecated.

    The actual implementation of *func* should keep the *name* parameter in its
    signature.

    Parameters that come after the deprecated parameter effectively become keyword-only.

    Notes
    -----
    Adapted from ``mpl._api.deprecation.delete_parameter``.

    Parameters
    ----------
    since : str
        Version in which the parameter was deprecated.
    name : str
        Name of the parameter.
    func : func, optional
        Function in which the parameter is deprecated.
    removal : str or bool, optional
        Version in which support for the parameter will be fully dropped. Defaults
        to the next release after *since*, unless set to False.
    alternative : str, optional
        An alternative API to suggest to the user.

    Examples
    --------
    ::

        @delete_parameter('1.3', 'unused')
        def func(used_arg, other_arg, unused, more_args):
            pass
    """

    if func is None:
        return functools.partial(delete_parameter, since, name, removal=removal, alternative=alternative)

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        arguments = compat.bind_arguments(func, *args, **kwargs)
        if name in arguments:
            addendum = ('If any parameters follow {0}, they should be passed as keywords, '.format(name)
                      + 'not positionally.')
            warn_deprecated(since=since, name=name, obj_type='parameter', removal=removal,
                            alternative=alternative, addendum=addendum, stacklevel=3)
        return func(*args, **kwargs)

    return wrapper
