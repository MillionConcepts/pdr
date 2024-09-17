# This module contains classes and methods that require
# matplotlib, but are used across more than one viewer
# window or do not better fit elsewhere

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import warnings

import numpy as np
import matplotlib as mpl

from ..utils.compat import OrderedDict
from ..extern.six.moves import reload_module

# Initialize TK backend for MPL safely prior to importing from backend
if mpl.get_backend() != 'TkAgg':

    # MPL v1.2 - v3.2
    try:
        mpl.use('TkAgg', warn=False, force=True)
    except TypeError:

        # MPL v3.3+
        try:
            mpl.use('TkAgg', force=True)

        # MPL v1.1-
        except TypeError:
            mpl.use('TkAgg', warn=False)
            if 'matplotlib.backends' in sys.modules:
                reload_module(sys.modules['matplotlib.backends'])

# After initializing TK as backend, import MPL
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

#################################


class FigureCanvas(object):
    """ FigureCanvas class; wrapper around MPL's FigureCanvasTkAgg """

    def __init__(self, figure, master=None):

        # Create the MPL canvas
        self.mpl_canvas = FigureCanvasTkAgg(figure, master=master)

        # Immediately remove highlightthickness and borders so the canvas' winfo_reqwidth() and
        # winfo_reqheight() are equivalent to get_dimensions(). Note that removing this line will subtly
        # break this class, because you can no longer rely on set_dimensions() to set the figure and
        # canvas sizes to be equivalent
        self.tk_widget.config(takefocus=False, bd=0, highlightthickness=0)

        # Immediately unbind <Configure>. On resize, MPL automatically redraws figure, which is
        # undesired because we want to manually control size, because it draws figure even if it had
        # never been drawn and was not yet intended to be drawn, and because it introduces extreme lag to
        # scrolling of large plots and possibly images
        self.tk_widget.unbind('<Configure>')

        # Freeze FigureCanvas by default until it is packed
        self.frozen = True

        # Contains FigureCanvas size in pixels if it has been resized while frozen; otherwise is set to None
        self._thawed_fig_size = None

    @property
    def mpl_figure(self):
        return self.mpl_canvas.figure

    @property
    def tk_widget(self):
        return self.mpl_canvas.get_tk_widget()

    @property
    def dpi(self):
        return self.mpl_figure.dpi

    # Update FigureCanvas to reflect any visual changes in the figure (e.g. updated image, plot, etc)
    def draw(self):

        if not self.frozen:

            # If FigureCanvas was resized while frozen, then we apply the resizing and redraw
            if self._thawed_fig_size is not None:
                self._resize_and_draw()

            # If FigureCanvas has not been resized while frozen then we just draw
            else:
                self.mpl_canvas.draw()

    # Pack and unfreeze the FigureCanvas
    def pack(self):
        self.tk_widget.pack()
        self.frozen = False

    # Clear the FigureCanvas
    def clear(self):

        # For some reason running clear() does not clear all memory used to draw the figure.
        # This can be seen by using only clear() and then opening/closing a large image;
        # the memory usage will be larger after closure than it was prior to opening.
        # Setting figure size to be 1x1 pixels, prior to running clear(), seems to negate
        # this issue (it is likely the leak still occurs but is much much smaller).

        # Since clear() is not intended to change the figure size, we restore it back after clearing.
        # Unfortunately this process does take a bit of time for large images.
        original_dimensions = self.get_dimensions(type='pixels')

        # Suppress MPL 2+ user warning on too small margins for plots, since this is intended
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=UserWarning)
            self.set_dimensions((1, 1), type='pixels', force=True)

        self.mpl_figure.clear()
        self.set_dimensions(original_dimensions, type='pixels', force=True)

    # Destroys the FigureCanvas. Must be called once this object is no longer being used to prevent a
    # memory leak
    def destroy(self):

        # For some reason running clear() does not clear all memory. This can be seen by
        # using only clear() and then opening/closing a large image; the memory usage
        # will be larger after closure than it was prior to opening. Setting figure size
        # to be 1x1 pixels, prior to running clear(), seems to negate this issue (it is
        # likely the leak still occurs but is much much smaller).

        # Suppress MPL 2+ user warning on too small margins for plots, since this is intended
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=UserWarning)
            self.set_dimensions((1, 1), type='pixels', force=True)

        self.mpl_figure.clear()
        self.tk_widget.destroy()

    # While frozen, the displayed figure image is not updated for changes even if requested
    def freeze(self):
        self.frozen = True

    # Thaw after being frozen, and by default also redraw to update figure image for changes made while frozen
    def thaw(self, redraw=True):
        self.frozen = False

        if redraw:
            self.draw()

    # Returns the FigureCanvas dimensions (MPL figure and its containing TK canvas have the same dimensions)
    # in units of type (pixels or inches)
    def get_dimensions(self, type='pixels'):

        # While frozen, we report the size the FigureCanvas will take on once redrawn
        if self._thawed_fig_size is not None:
            fig_size = self._thawed_fig_size

            # Get fig_size from pixels
            fig_size = self._fig_size_convert(fig_size, input_type='pixels', output_type=type)

        # Report the true FigureCanvas size
        else:
            fig_size = self.mpl_figure.get_size_inches()

            # Get fig_size from inches
            fig_size = self._fig_size_convert(fig_size, input_type='inches', output_type=type)

        return fig_size

    # Sets the FigureCanvas dimensions (MPL figure and its containing TK canvas have the same dimensions)
    # in units of type (pixels or inches). By default the FigureCanvas is resized immediately only when the
    # FigureCanvas is not frozen because on resize it will also be redrawn; `force` allows for immediate
    # resizing even when frozen.
    def set_dimensions(self, fig_size, type='pixels', force=False):

        # Get fig_size in pixels
        fig_size = self._fig_size_convert(fig_size, input_type=type, output_type='pixels')

        # Skip adjusting dimensions if they are not changing because this can be an expensive
        # operation for large images
        if fig_size == self.get_dimensions(type='pixels'):
            return

        # Set figure canvas size and resize, if the window is not frozen or immediate resize is being forced
        # (see `_resize_and_draw` for more info as to why a redraw command is implicit in the resize call)
        self._thawed_fig_size = fig_size

        if force or (not self.frozen):
            self._resize_and_draw()

    # Resize and redraw the FigureCanvas. The contents of this method could actually be part of
    # `set_dimensions`, however that would redraw the image immediately on resize every time, regardless of
    # whether the FigureCanvas is frozen (due to MPL's FigureCanvasTkAgg.resize calling draw). Therefore this
    # method is used to delay resizing when the image is frozen until it is thawed. While overloading MPL's
    # resize call is possible to remove its draw call, MPL resizing works by deleting the previous image and
    # totally redrawing it (especially for plots), therefore doing this would make the image vanish until
    # its drawn again; i.e. redrawing is an implicit part of resizing.
    def _resize_and_draw(self):

        class ResizeEvent(object):
            def __init__(self, width, height):
                self.width = width
                self.height = height

        fig_size = self._thawed_fig_size

        # Set containing TK canvas size
        self.tk_widget.config(width=fig_size[0], height=fig_size[1])

        # Set MPL Figure size, which also redraws the figure
        MPLCompat.canvas_resize(self.mpl_canvas, ResizeEvent(fig_size[0], fig_size[1]))

        # Reset thawed size to none (otherwise this will keep firing even when no resize needed)
        self._thawed_fig_size = None

    # Convert figure size from input type to output type. Valid options for both *input_type* and
    # *output_type* are pixels|inches.
    def _fig_size_convert(self, fig_size, input_type, output_type):

        # Ensure types are is valid
        types = ('pixels', 'inches')
        if (input_type not in types) or (output_type not in types):

            error_type = input_type if (input_type not in types) else output_type
            raise ValueError("Unknown type, '{0}'. Expected: {1}.".format(error_type, ' or '.join(types)))

        # Pixels -> Pixels
        if input_type == 'pixels' and output_type == 'pixels':
            fig_size = np.round(fig_size).astype('int')

        # Pixels -> Inches
        elif input_type == 'pixels' and output_type == 'inches':
            fig_size = np.asanyarray(fig_size) / self.dpi

        # Inches -> Inches
        elif input_type == 'inches' and output_type == 'inches':
            fig_size = fig_size

        # Inches -> Pixels
        elif input_type == 'inches' and output_type == 'pixels':
            fig_size = np.round(np.asanyarray(fig_size) * self.dpi).astype('int')

        return tuple(fig_size)


class MPLCompat(object):
    """ Compatibility fixes for various versions of MPL. """

    @staticmethod
    def _get_navigation_toolbar():

        # Allow safe import of NavigationToolbar2Tk (available in MPL v2+)
        try:
            from matplotlib.backends.backend_tkagg import NavigationToolbar2Tk
        except ImportError:
            from matplotlib.backends.backend_tkagg import NavigationToolbar2TkAgg as NavigationToolbar2Tk

        return NavigationToolbar2Tk

    @staticmethod
    def _get_power_norm():

        # Allow safe import of PowerNorm (available in MPL v1.4+)
        try:
            from matplotlib.colors import PowerNorm

        except ImportError:
            PowerNorm = None

        return PowerNorm

    @staticmethod
    def _get_deprecation_warning():

        # Allow safe import of MatplotlibDeprecationWarning
        # MPL v3+
        try:
            from matplotlib import MatplotlibDeprecationWarning
        except ImportError:
            # MPL v1.3+
            try:
                from matplotlib.cbook import MatplotlibDeprecationWarning
            except ImportError:
                MatplotlibDeprecationWarning = DeprecationWarning

        return MatplotlibDeprecationWarning

    @staticmethod
    def _mpl_version():
        version_split = mpl.__version__.split('.')
        return [int(v) for v in version_split]

    NavigationToolbar2Tk = _get_navigation_toolbar.__get__(object)()
    DeprecationWarning = _get_deprecation_warning.__get__(object)()
    PowerNorm = _get_power_norm.__get__(object)()

    @staticmethod
    def canvas_resize(canvas, resize_event):

        # Resize an MPL figure
        canvas.resize(resize_event)

        # Force-refresh the image. Older MPL versions (prior to MPL v3.4.0) had a draw call in resize
        # that new versions removed. Resizing results in a blinking image without such a draw call.
        mpl_version = MPLCompat._mpl_version()
        if mpl_version[0] > 3 or (mpl_version[0] == 3 and mpl_version[1] >= 4):
            canvas.draw()

    @staticmethod
    def axis_set_facecolor(axis, color):
        """ Allow safe use of Axes.set_facecolor (available in MPL v1.5.x) """

        try:
            axis.set_facecolor(color)
        except AttributeError:
            axis.set_axis_bgcolor(color)

    @staticmethod
    def axis_set_grid(axis, **kwargs):
        """ Allow safe use of Axes.grid(visible=bool) (available in MPL v3.5.x) """

        if 'b' in kwargs:
            raise ValueError('Use *visible* instead of *b*.')

        kwargs['b'] = kwargs.pop('visible', None)

        try:
            axis.grid(**kwargs)
        except ValueError:
            kwargs['visible'] = kwargs.pop('b', None)
            axis.grid(**kwargs)


def get_mpl_linestyles(inverse=None, include_none=True):
    """ Obtain MPL's line styles.

    Parameters
    ----------
    inverse : str, unicode or None, optional
        If given, searches for an MPL line style based on its description. A string containing
        the found MPL line style instead of a dictionary is returned, KeyError raised if no match found.
    include_none : bool, optional
        If True, then the returned dictionary will also contain acceptable variations of none (no line).
        Defaults to True.

    Returns
    -------
    OrderedDict, str or unicode
        A dictionary containing MPL marker line as keys, and line descriptions as values. If the
        inverse parameter is used, a string containing the found MPL line style will be returned.

    Raises
    ------
    KeyError
        If the inverse parameter is used, but a line style corresponding to the passed in description
        does not exist.
    """

    # Create a dict containing MPL linestyles and their descriptions
    _mpl_linestyles = [('-', 'solid'),
                       ('--', 'dashed'),
                       (':',  'dotted'),
                       ('-.', 'dashdot')]

    if include_none:

        _mpl_linestyles += [('none', 'nothing'),
                            ('None', 'nothing'),
                            (None, 'nothing'),
                            (' ',  'nothing'),
                            ('',   'nothing')]

    mpl_linestyles = OrderedDict(_mpl_linestyles)

    # If inverse parameter is specified, find and return an MPL linestyle from its description
    if inverse is not None:

        style_idx = list(mpl_linestyles.values()).index(inverse)
        mpl_linestyle = list(mpl_linestyles.keys())[style_idx]

        return mpl_linestyle

    return mpl_linestyles


def get_mpl_markerstyles(inverse=None, include_none=True):
    """ Obtain MPL's marker styles.

    Parameters
    ----------
    inverse : str, unicode or None, optional
        If given, searches for an MPL marker style based on its description. A string containing
        the found MPL marker style instead of a dictionary is returned, KeyError is raised if no match found.
    include_none : bool, optinoal
        If True, then the returned dictionary will also contain acceptable variations of none (no marker).
        Defaults to True.

    Returns
    -------
    OrderedDict, str or unicode
        A dictionary containing MPL marker styles as keys, and marker descriptions as values. If the
        inverse parameter is used, a string containing the found MPL marker style will be returned.

    Raises
    ------
    KeyError
        If the inverse parameter is used, but a marker style corresponding to the passed in description
        does not exist.
    """

    # Create a dict containing MPL marker styles and their descriptions
    _mpl_markerstyles = [('.', 'point'),
                         (',', 'pixel'),
                         ('o', 'circle'),
                         ('s', 'square'),
                         ('v', 'triangle down'),
                         ('^', 'triangle up'),
                         ('+', 'plus'),
                         ('D', 'diamond')]

    if include_none:

        _mpl_markerstyles += ([('None', 'nothing'),
                               ('none', 'nothing'),
                               (None,   'nothing'),
                               (' ',    'nothing'),
                               ('',     'nothing')])

    mpl_markerstyles = OrderedDict(_mpl_markerstyles)

    # If inverse parameter is specified, find and return an MPL marker style from its description
    if inverse is not None:

        style_idx = list(mpl_markerstyles.values()).index(inverse)
        mpl_markerstyle = list(mpl_markerstyles.keys())[style_idx]

        return mpl_markerstyle

    return mpl_markerstyles


def mpl_color_to_rgb(mpl_color):
    """ Converts any MPL color to an RGB tuple.

    Parameters
    ----------
    mpl_color : tuple, str or unicode
        An MPL color, which is any color that MPL would natively accept into its color functions.

    Returns
    -------
    tuple
        An three-valued tuple representing the red, green and blue values, each of which ranges from 0-1
        (where traditionally 0 is 0, and 1 is 255).
    """

    rgb_color = mpl.colors.ColorConverter().to_rgb(mpl_color)

    return rgb_color


def mpl_color_to_hex(mpl_color):
    """ Converts any MPL color to HEX string.

    Parameters
    ----------
    mpl_color : tuple, str or unicode
        An MPL color, which is any color that MPL would natively accept into its color functions.

    Returns
    -------
    str or unicode
        A HEX color string.
    """

    rgb_color = mpl.colors.ColorConverter().to_rgb(mpl_color)
    hex_color = mpl.colors.rgb2hex(rgb_color)

    return hex_color


def mpl_color_to_inverted_rgb(mpl_color):
    """ Converts any MPL color to the inverted color as an RGB tuple.

    Parameters
    ----------
    mpl_color : tuple, str or unicode
        An MPL color, which is any color that MPL would natively accept into its color functions.

    Returns
    -------
    tuple
        An three-valued tuple representing the red, green and blue values, each of which ranges from 0-1
        (where traditionally 0 is 0, and 1 is 255). Colors are inverted from the input color.
    """

    rgb_color = mpl_color_to_rgb(mpl_color)
    inverted_rgb = [(1.0 - color) for color in rgb_color]

    return tuple(inverted_rgb)


_mpl_user_defaults = mpl.rcParams.copy()

def set_default_mpl_rcparams():
    """ Set rcparams for matplotlib to their default values.

    Returns
    -------
    None
    """

    global _mpl_user_defaults

    _mpl_user_defaults = mpl.rcParams.copy()
    mpl.rcdefaults()


def restore_mpl_rcparams():
    """ Restores rcparams for matplotlib to original user values.

    Returns
    -------
    None
    """

    global _mpl_user_defaults

    # While restoring, we ignore MPL depreciation warnings for old rcParams. In some MPL versions
    # (e.g. MPL v3.0) there are deprecated settings in even the default mpl.rcParams. Thus when
    # restoring, they give out spurious warnings.
    with warnings.catch_warnings():

        warnings.simplefilter('ignore', MPLCompat.DeprecationWarning)
        mpl.rcParams.update(_mpl_user_defaults)
