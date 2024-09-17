from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

import sys
import copy
import logging

from ..extern import six

# Minimum logging levels for loud and quiet operation
_loud = logging.DEBUG
_quiet = logging.ERROR

# User-configured log level
_user_level = None


def logger_init():
    """ Initializes or obtains the logger for PDS4 tools and its handlers.

    Returns
    -------
    PDS4Logger
        The global logger for all pds4 tools.
    """

    # Obtain or create PDS4ToolsLogger
    original_class = logging.getLoggerClass()

    logging.setLoggerClass(PDS4Logger)
    logger = logging.getLogger('PDS4ToolsLogger')

    logging.setLoggerClass(original_class)

    # If this is a new logger then initialize its config
    if not logger.handlers:

        # Set default log level for entire logger
        logger.setLevel(_loud)

        # Create the stdout handler. This handler outputs to stdout and to warning and errors message boxes
        # in the viewer and can be silenced by user (via use of quiet or --quiet).
        stdout_handler = PDS4StreamHandler('stdout_handler')

        # Create the log handler. This handler does not output to stdout or to screen and should not
        # be silenced.
        log_handler = PDS4SilentHandler('log_handler')

        # Create the formatter and add it to the handlers
        formatter = PDS4Formatter()
        stdout_handler.setFormatter(formatter)
        log_handler.setFormatter(formatter)

        # Add handlers to logger
        logger.addHandler(stdout_handler)
        logger.addHandler(log_handler)

    return logger


def set_loglevel(level):
    """
    Enables log messages from the PDS4 tools logger to propagate to ancestor loggers based
    on the log level.

    By default log messages are not propagated. To receive info+ log messages, one would
    typically ``set_loglevel('info')``, while setting ``pds4_read(..., quiet=True)`` to
    avoid duplicate information to stdout.

    Parameters
    ----------
    level : int or str
        Level to set for handler. See Python documentation on logger levels for details.

    Returns
    -------
    None
    """

    global _user_level

    if isinstance(level, six.string_types):
        _user_level = getattr(logging, level.upper())
    else:
        _user_level = level


class PDS4Logger(logging.Logger, object):
    """ Custom PDS4 Logger, for its internal log use.

     Additional features over standard logger:
        - Get handlers by name
        - Has `quiet` or `loud` methods
        - Set maximum number of repetitions for a logging message via e.g. ``.log(... max_repeats=n)``
        - Set custom line terminator on per message basis for all stream handlers via e.g. ``.log(..., end='str')``

    """

    def __init__(self, *args, **kwargs):

        # Stores those messages (as keys) which have a max_repeat argument set (see _log() details)
        # and the number of repetitions they have had (as values)
        self._max_repeat_records = {}

        super(PDS4Logger, self).__init__(*args, **kwargs)

    @property
    def stream_handlers(self):
        """
        Returns
        -------
        logging.StreamHandler or subclasses
            Stream handlers bound to this logger.
        """

        return [handler for handler in self.handlers
                        if isinstance(handler, logging.StreamHandler)]

    def get_handler(self, handler_name):
        """ Obtain handler by name.

        Parameters
        ----------
        handler_name : str or unicode
            The name of the handler.

        Returns
        -------
        PDS4StreamHandler or PDS4SilentHandler
            Handler for this logger, matching the *handler_name*.
        """

        for handler in self.handlers:

            if handler.name == handler_name:
                return handler

        return None

    def quiet(self, handler_name='stdout_handler'):
        """ Sets a handler to log only errors.

        Parameters
        ----------
        handler_name : str or unicode, optional
            Handler name to select. Defaults to stdout handler.

        Returns
        -------
        None
        """

        self.get_handler(handler_name).setLevel(_quiet)

    def loud(self, handler_name='stdout_handler'):
        """ Sets a handler to log warnings and above.

        Parameters
        ----------
        handler_name : str or unicode, optional
            Handler name to select. Defaults to stdout handler.

        Returns
        -------
        None
        """

        self.get_handler(handler_name).setLevel(_loud)

    def is_quiet(self, handler_name='stdout_handler'):
        """ Obtains whether a handler is quiet.

        Parameters
        ----------
        handler_name : str or unicode, optional
            Handler name to select.  Defaults to stdout handler.

        Returns
        -------
        bool
            True if the logger is quiet, i.e. logs only errors; false otherwise.
        """
        return self.get_handler(handler_name).is_quiet

    def set_terminators(self, ends=None):
        """ Sets line terminator for all stream handlers.

        Parameters
        ----------
        ends : str, unicode or list[str or unicode]
            The line terminator (same for all stream handlers) or sequence of terminators.
            Sequence order must be same as order of stream handlers in `stream_handlers`
            attribute.

        Returns
        -------
        None
        """

        num_stream_handlers = len(self.stream_handlers)
        ends_is_array = isinstance(ends, (list, tuple))

        if ends_is_array and (len(ends) != num_stream_handlers):
            raise TypeError('Number of stream handlers ({0}) does not match number of ends ({1}).'
                            .format(len(ends), num_stream_handlers))

        elif not ends_is_array:

            ends = [ends] * num_stream_handlers

        for i, handler in enumerate(self.stream_handlers):
            handler.terminator = ends[i]

    def setLevel(self, level, handler_name=None):
        """ Set log level for entire logger or a specific handler.

        Parameters
        ----------
        level : int or str
            Level to set for logger or handler. See Python documentation on logger levels for details.
        handler_name : str or unicode, optional
            Handler name to select. Defaults to the entire logger.

        Returns
        -------
        None
        """

        if isinstance(level, six.string_types):
            level = level.upper()

        if handler_name is None:
            super(PDS4Logger, self).setLevel(level)
        else:
            self.get_handler(handler_name).setLevel(level)

    def _log(self, level, *args, **kwargs):
        """
        Subclassed to allow *end* and *max_repeat* arguments to every logger log call (e.g. ``logger.info``,
        ``logger.warning``, etc)

        When *end* is given, the message will end with the indicated line terminator instead of the handler's
             terminator setting.
        When *max_repeat* is given, the indicated message will only be emitted the number of times indicated
            from then on.

        Returns
        -------
        None
        """

        msg = args[1]
        max_repeat = kwargs.pop('max_repeat', None)
        end = kwargs.pop('end', None)

        # Determine if max repeats for this log message has been reached
        if max_repeat is not None:

            times_repeated = self._max_repeat_records.setdefault(msg, 0)
            self._max_repeat_records[msg] += 1

            if times_repeated >= max_repeat:
                return

        # Set line terminator (temporarily) for all handlers
        if end is not None:
            original_ends = [handler.terminator for handler in self.stream_handlers]
            self.set_terminators(end)

        # Enable or disable propagation to ancestor loggers based on ``set_loglevel``
        original_propagate = self.propagate
        if (_user_level is None) or (level < _user_level):
            self.propagate = False

        # Log the message
        super(PDS4Logger, self)._log(level, *args, **kwargs)

        # Revert log propagation and line terminator back to previous/default settings
        self.propagate = original_propagate

        if end is not None:
            self.set_terminators(original_ends)


class PDS4StreamHandler(logging.StreamHandler):
    """ Custom StreamHandler that has a *name* and a *is_quiet* attributes. """

    def __init__(self, name, level=_loud):
        """ Initialize the handler.

        Parameters
        ----------
        name : str or unicode
            Name to give the handler.
        level : int, optional
            Default log level for this handler. Defaults to _loud.
        """

        # Using try due to stream parameter being renamed in Python <2.7)
        try:
            logging.StreamHandler.__init__(self, stream=sys.stdout)
        except TypeError:
            logging.StreamHandler.__init__(self, strm=sys.stdout)

        self._name = name

        if not hasattr(self, 'terminator'):
            self.terminator = '\n'

        self.set_level(level)

    def emit(self, record):
        """ Emit a record.

        Subclassed to allow ``handler.terminator`` to be used as the line terminator rather than hardcode the
        newline character on any supported Python version. This is a standard feature on Python >= 3.2, but
        not available earlier.
        """

        # Python >= 3.2 (i.e. all PY3 versions supported by this code) provides `self.terminator` by default
        if six.PY3:
            super(PDS4StreamHandler, self).emit(record)

        # For PY2, we copy directly from Python 2.7's emit, which also works for Python 2.6. A minor
        # modification is made to allow `self.terminator` attribute to work
        else:

            try:
                unicode
                _unicode = True
            except NameError:
                _unicode = False

            try:
                msg = self.format(record)
                stream = self.stream
                fs = b"%s{0}".format(self.terminator)
                if not _unicode:
                    stream.write(fs % msg)
                else:
                    try:
                        if (isinstance(msg, unicode) and
                                getattr(stream, 'encoding', None)):
                            ufs = u'%s{0}'.format(self.terminator)
                            try:
                                stream.write(ufs % msg)
                            except UnicodeEncodeError:
                                stream.write((ufs % msg).encode(stream.encoding))
                        else:
                            stream.write(fs % msg)
                    except UnicodeError:
                        stream.write(fs % msg.encode("UTF-8"))
                self.flush()
            except (KeyboardInterrupt, SystemExit):
                raise
            except:
                self.handleError(record)

    @property
    def name(self):
        """
        Returns
        -------
        str or unicode
            Name of the handler.
        """
        return self._name

    @property
    def is_quiet(self):
        """
        Returns
        -------
        bool
            True if handler is quiet, False otherwise.
        """
        return self.level >= _quiet

    def set_level(self, level):
        """ Set handler log level.

        Convenience method for setLevel.

        Parameters
        ----------
        level : int or str
            Level to set for handler. See Python documentation on logger levels for details.
        """
        self.setLevel(level)

    def get_level(self):
        """ Get handler log level.

        Convenience method for the *level* attribute.

        Returns
        -------
        int
            Level for handler. See Python documentation on logger levels for details.
        """
        return self.level

    def setLevel(self, level):
        """ Set handler log level.

        Overloads ``logging.StreamHandler.setLevel`` to automatically set whether logger is quiet or loud.

        Parameters
        ----------
        level : int or str
            Level to set for handler. See Python documentation on logger levels for details.
        """

        if isinstance(level, six.string_types):
            level = level.upper()

        logging.StreamHandler.setLevel(self, level)


class PDS4SilentHandler(PDS4StreamHandler):
    """ Custom StreamHandler that saves emitted records to *records* attribute.

    Able to print out previously emitted records via `to_string`. """

    def __init__(self, name):

        PDS4StreamHandler.__init__(self, name)

        self.records = []
        self._recording_start = None

    def emit(self, record):
        """ Saves emitted record.

        Emitted record is shallow copied, then message is modified as described. First, we insert
        the current line terminator, as otherwise this information would be lost. Second, if the
        current or prior record contains a stand alone carriage-return character, we save only
        the final state of the stream output as it would be if printed to a terminal. Generally
        carriage return is likely only to be used to overwrite old messages on the same line
        (e.g. how a download progress bar works); saving each message would pollute the message
        queue, and potentially take a huge amount of memory.

        Parameters
        ----------
        record : logger.LogRecord
            Record to emit.

        Returns
        -------
        None
        """

        # Special processing for messages containing the CR (\r) character
        # (see docstring for explanation)
        record = copy.copy(record)
        new_msg = record.msg
        last_msg = self.records[-1].msg if self.records else None

        new_msg_has_cr = isinstance(new_msg, six.string_types) and ('\r' in new_msg)
        last_msg_has_cr = isinstance(last_msg, six.string_types) and ('\r' in last_msg)

        if new_msg_has_cr or last_msg_has_cr:

            last_newline_idx = -1

            for i in range(len(self.records) - 1, 0, -1):

                value = self.records[i].msg
                if '\n' in value:
                    last_newline_idx = i
                    break

            last_record = self.records[last_newline_idx].msg + new_msg

            # Special case when there are no newlines in previous records at all
            if last_newline_idx < 0:
                self.records = []

            # Deal with '\r\n', which generally acts equivalent to '\n' in terminals
            not_contain_str = '\n|'
            while not_contain_str in last_record:
                not_contain_str += '|'
            last_record = last_record.replace('\r\n', not_contain_str)

            # Truncate messages from '\r' to previous newline
            prev_msg = ''
            new_msg = last_record
            while ('\r' in new_msg) and (new_msg.count('\r') > 1 or not new_msg.endswith('\r')):
                head, _, new_msg = new_msg.partition('\r')
                prev_msg += head[0:head.rfind('\n') + 1]

            record.msg = '{0}{1}'.format(prev_msg, new_msg)
            record.msg = record.msg.replace(not_contain_str, '\r\n')

            self.records = self.records[0:last_newline_idx]

        # Save the record
        record.msg = '{0}{1}'.format(record.msg, self.terminator)
        self.records.append(record)

    def begin_recording(self):
        """
        Used in conjunction with `get_recording`. Records emitted after this method is called will be
        returned by `get_recording`.

        Returns
        -------
        None
        """
        self._recording_start = len(self.records)

    def get_recording(self, reset=True):
        """
        Obtains records since `begin_recording` was called as a joined string.

        Parameters
        ----------
        reset : bool, optional
            If True, begins a new recording from now on. If False, recording from previous point
            continues. Defaults to True.

        Returns
        -------
        str or unicode
            A string containing the messages that were emitted since `begin_recording` was called.

        Raises
        ------
        RuntimeError
            Raised if `begin_recording` was not called prior to calling this method.
        """
        record_start = self._recording_start

        if record_start is None:
            raise RuntimeError('Cannot obtain recording: no recording was started.')

        if reset:
            self.begin_recording()

        return self.to_string(start_i=record_start)

    def to_string(self, start_i=0, end_i=None):
        """ Output emitted records as a joined string.

        Parameters
        ----------
        start_i : int, optional
            Index of first record to include. Defaults to 0 (include records from the beginning).
        end_i : int, optional
            Index of last record to include. Defaults to None (include records until the end).

        Returns
        -------
        str or unicode
            A string containing the messages in the records that were previously emitted.
        """

        formatted_records = [self.format(record) for record in self.records[start_i:end_i]]

        return ''.join(formatted_records)


class PDS4Formatter(logging.Formatter):
    """ Custom formatter that varies format according to log level. """

    def format(self, record):
        """
        Parameters
        ----------
        record : logger.LogRecord
            The record to format.

        Returns
        -------
        str or unicode
            The formatted record string.

        """
        formatter = logging.Formatter('%(message)s')
        formatted_value = logging.Formatter.format(formatter, record)

        if record.levelno != logging.INFO:
            formatted_value = record.levelname.capitalize() + ': ' + formatted_value

        return formatted_value
