from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import re
import copy
import platform
import functools
import itertools
from fractions import Fraction

import numpy as np
import matplotlib as mpl
from matplotlib.figure import Figure

from . import label_view, cache
from .core import DataViewWindow, MessageWindow, Window
from .mpl import (FigureCanvas, MPLCompat, get_mpl_linestyles, get_mpl_markerstyles,
                  mpl_color_to_hex, mpl_color_to_inverted_rgb)
from .widgets.notebook import TabBar, Tab

from ..reader.data_types import is_pds_integer_data, data_type_convert_dates
from ..reader.table_objects import Meta_Field

from ..utils.compat import OrderedDict

from ..extern import six
from ..extern.six.moves import tkinter_colorchooser
from ..extern.six.moves.tkinter import (Frame, Scrollbar, Listbox, Label, Entry, Button, Checkbutton,
                                        OptionMenu, DoubleVar, IntVar, BooleanVar, StringVar)
from ..extern.six.moves.tkinter_tkfiledialog import asksaveasfilename

#################################


class PlotViewWindow(DataViewWindow):
    """ Window that displays PDS4 data as plots.

    This window will display plots. After creating it, you should use the load_table() method to load
    the table that it needs to display.
    """

    def __init__(self, viewer):

        # Create basic data view window
        super(PlotViewWindow, self).__init__(viewer)

        # Pack the display frame, which contains the scrollbars and the scrollable canvas
        self._display_frame.pack(side='left', anchor='nw', expand=1, fill='both')

        # Control variable for `freeze_display` and `thaw_display`. Image will not be updated on screen
        # when counter is greater than 1.
        self._freeze_display_counter = 0

        # Will be set to an instance of FigureCanvas (containing the main image/slice being displayed)
        self._figure_canvas = None

        # Will be set to an instance of MPL's Axes
        self._plot = None

        # Will be set to an instance of MPL's toolbar for TK
        self._toolbar = None

        # Will contain _Series objects, which describe each line/point series added to the plot
        self.series = []

        # Contains sub-widgets of the header
        self._header_widgets = {'x': None, 'y': None}

        # Menu option variables. These are TKinter type wrappers around standard Python variables. The
        # advantage is that you can use trace(func) on them, to automatically call func whenever one of
        # these variables is changed
        menu_options = [
            {'name': 'axis_limits',      'type': StringVar(),  'default': 'intelligent',   'trace': self._update_axis_limits},
            {'name': 'axis_scaling',     'type': StringVar(),  'default': 'linear-linear', 'trace': self._update_axis_scaling},
            {'name': 'show_title',       'type': BooleanVar(), 'default': False,           'trace': self._update_labels},
            {'name': 'show_labels',      'type': BooleanVar(), 'default': True,            'trace': self._update_labels},
            {'name': 'show_border',      'type': BooleanVar(), 'default': True,            'trace': self._update_border},
            {'name': 'tick_direction',   'type': StringVar(),  'default': 'in',            'trace': self._update_ticks},
            {'name': 'show_major_ticks', 'type': BooleanVar(), 'default': True,            'trace': self._update_ticks},
            {'name': 'show_minor_ticks', 'type': BooleanVar(), 'default': True,            'trace': self._update_ticks},
            {'name': 'show_tick_labels', 'type': StringVar(),  'default': 'both',          'trace': self._update_ticks},
            {'name': 'show_major_grid',  'type': BooleanVar(), 'default': False,           'trace': self._update_grid},
            {'name': 'show_minor_grid',  'type': BooleanVar(), 'default': False,           'trace': self._update_grid},
            {'name': 'grid_linestyle',   'type': StringVar(),  'default': 'dotted',        'trace': self._update_grid},
            {'name': 'invert_axis',      'type': StringVar(),  'default': 'none',          'trace': self._update_invert_axis},
            {'name': 'enlarge_level',    'type': DoubleVar(),  'default': 1,               'trace': self._update_enlarge_level},
            {'name': 'pan',              'type': BooleanVar(), 'default': False,           'trace': self._pan},
            {'name': 'axis_limits_to_rectangle', 'type': BooleanVar(), 'default': False,   'trace': self._axis_limits_to_rectangle}
        ]

        for option in menu_options:

            var = option['type']
            self._menu_options[option['name']] = var

            self._add_trace(var, 'w', option['trace'], option['default'])

    @property
    def settings(self):

        settings = super(PlotViewWindow, self).settings
        settings['labels'] = copy.deepcopy(settings['labels'])

        return settings

    # Loads the table structure into this window, displays a plot for the selected axes. axis_selections
    # is a list of field indexes in the table to use for the plot in the order x,y,x_err,y_err; to have one
    # of the indexes be row number, the string 'row' may be used for a field index. Set `lines` to have lines
    # connecting the data points; set `points` to have markers shown on data points. Set `mask_special` to
    # ignore special values (such as nulls and special constants) in plot.
    def load_table(self, table_structure, axis_selections, lines=True, points=False, mask_special=False):

        # Add series to storage
        series = _Series(table_structure, axis_selections)
        series_idx = len(self.series)
        self.series.append(series)

        # Add series to plot, do not continue with initialization if it has been done before
        if self._data_open:

            self._draw_series(series_idx, lines=lines, points=points, mask_special=mask_special)
            return

        # Set necessary instance variables for this DataViewWindow
        self._settings = {'title': None,
                          'labels': {'x': {'visible': self.menu_option('show_labels'),  'name': None},
                                     'y': {'visible': self.menu_option('show_labels'),  'name': None}},
                          'pixel_init_dimensions': (0, 0), 'dpi': 80.}

        # Set a title for the window
        self.set_window_title("{0} - Plot from '{1}'".format(self.get_window_title(), table_structure.id))

        # Create the header
        self._draw_header()

        # Add vertical scrollbar for the plot
        self._vert_scrollbar = Scrollbar(self._display_frame, orient='vertical', command=self._scrollable_canvas.yview)
        self._scrollable_canvas.config(yscrollcommand=self._vert_scrollbar.set)
        self._vert_scrollbar.pack(side='right', fill='y')

        # Add horizontal scrollbar for the plot
        self._horz_scrollbar = Scrollbar(self._display_frame, orient='horizontal', command=self._scrollable_canvas.xview)
        self._scrollable_canvas.config(xscrollcommand=self._horz_scrollbar.set)
        self._horz_scrollbar.pack(side='bottom', fill='x')

        # Pack the static canvas, which contains the scrollable canvas
        self._static_canvas.config(background='white')
        self._static_canvas.pack(side='left', anchor='nw', expand=1, fill='both')

        # Place the scrollable canvas, which contains the plot itself
        self._scrollable_canvas.config(background='white')
        self._scrollable_canvas.place(relx=0.5, rely=0.5, anchor='center')

        # Update idletasks such that the window takes on its real size
        self._widget.update_idletasks()

        # Draw plot / series to the screen
        self._draw_series(series_idx, lines=lines, points=points, mask_special=mask_special)

        # Add notify event for window resizing
        self._display_frame.bind('<Configure>', self._window_resize)

        # Add notify event for scroll wheel (used to change plot size via scroll wheel)
        self._bind_scroll_event(self._mousewheel_scroll)

        # Add notify event for mouse pointer exiting _scrollable_canvas (used to display locations
        # under the mouse pointer)
        self._figure_canvas.tk_widget.bind('<Leave>', self._update_mouse_pixel_value)

        # Add notify event for mouse motion (used to display pixel location under pointer)
        self._figure_canvas.mpl_canvas.mpl_connect('motion_notify_event', self._update_mouse_pixel_value)

        self._add_menus()
        self._data_open = True

    # Current enlarge level. E.g., a value of 2 means double the dimensions of the original plot.
    def get_enlarge_level(self):
        return self.menu_option('enlarge_level')

    # Current title. By default a string is returned; if mpl_text is True, an MPL text object for the title
    # label is returned instead. If the if_visible parameter is true, the title is returned only if it
    # is visible on the plot, otherwise None is returned.
    def get_title(self, mpl_text=False, if_visible=False):

        if if_visible and (not self.is_title_shown()):
            title = None

        elif mpl_text:
            title = self._plot.axes.title

        else:
            title = self._settings['title']

        return title

    # Current axis labels. Valid options for axis are x|y. By default a string is returned; if mpl_text is
    # True, an MPL text object for the axis label is returned instead. If the if_visible parameter is true,
    # the label is returned only if it is visible on the plot, otherwise None is returned.
    def get_axis_label(self, axis, mpl_text=False, if_visible=False):

        if axis not in ('x', 'y'):
            raise ValueError('Unknown label type: {0}'.format(axis))

        if if_visible and (not self.is_label_shown(axis)):
            axis_label = None

        elif mpl_text:

            ax = self._plot.axes
            axis = ax.xaxis if axis == 'x' else ax.yaxis

            axis_label = axis.get_label()

        else:
            axis_label = self._settings['labels'][axis]['name']

        return axis_label

    # Current tick labels. Valid options for axis are x|y, and for which are major|minor|both. By default a
    # string is returned; if mpl_text is True, an MPL text object for the axis label is returned instead. If
    # the if_visible parameter is true, the labels are returned only if visible on the plot, otherwise
    # None is returned.
    def get_tick_labels(self, axis, which='both', mpl_text=False, if_visible=False):

        # Ensure proper axis and which options specified
        if axis not in ('x', 'y'):
            raise ValueError('Unknown tick label type: {0}'.format(axis))

        elif which not in ('major', 'minor', 'both'):
            raise ValueError('Unknown tick label type: {0}'.format(which))

        # Gather proper tick labels
        tick_labels = []

        if (not if_visible) or self.is_tick_labels_shown(axis):

            ax = self._plot.axes
            axis = ax.xaxis if axis == 'x' else ax.yaxis
            tick_types = ['minor', 'major'] if which == 'both' else [which]

            for tick_type in tick_types:
                mpl_labels = axis.get_ticklabels(minor=(tick_type == 'minor'))

                if mpl_text:
                    tick_labels += mpl_labels

                else:
                    tick_labels += [label.get_text() for label in mpl_labels]

        return tick_labels

    # Current axis limits
    def get_axis_limits(self):

        ax = self._plot.axes
        return list(ax.get_xlim()), list(ax.get_ylim())

    # Current line options for the specified series
    def get_line_options(self, series):

        line = self.series[series].plot_line

        line_options = {
            'visible': self.is_series_shown(series, which='line'),
            'style': get_mpl_linestyles()[line.get_linestyle()],
            'width': line.get_linewidth(),
            'color': mpl_color_to_hex(line.get_color())
        }

        return line_options

    # Current point options for the specified series
    def get_point_options(self, series):

        line = self.series[series].plot_line

        point_options = {
            'visible': self.is_series_shown(series, which='points'),
            'style': get_mpl_markerstyles()[line.get_marker()],
            'width': line.get_markersize(),
            'color': mpl_color_to_hex(line.get_markerfacecolor()),
            'frequency': line.get_markevery()
        }

        return point_options

    # Current error bar options for the specified series and direction (vertical or horizontal)
    def get_error_bar_options(self, series, which):

        if which not in ('vertical', 'horizontal'):
            raise ValueError('Unknown error bar type: {0}'.format(which))

        error_line = self.series[series].error_lines[which]
        error_caps = self.series[series].error_caps[which]

        if (error_line is None) or (not error_caps):
            return None

        # Calling MPL's `get_linestyle` on collections does not actually return the same value as passed in
        # when doing `set_linestyle`. E.g., it does not return 'solid', 'dashed', etc but rather a different
        # metric for the same thing. To obtain the name, we use two different methods below.
        try:
            # For MPL 1.x
            dash_dict = mpl.backend_bases.GraphicsContextBase.dashd

        except AttributeError:

            # For MPL 2.x
            from matplotlib.lines import _get_dash_pattern
            dash_dict = {}
            for key in ('solid', 'dashed', 'dotted', 'dashdot'):
                value = _get_dash_pattern(key)
                dash_dict[key] = value if not isinstance(value[1], (tuple, list)) else (value[0], list(value[1]))

        line_style = [key for key, value in six.iteritems(dash_dict)
                      if error_line.get_linestyle()[0] == value]

        error_bar_options = {
            'visible': self.is_error_bar_shown(series, which=which),
            'style': line_style[0],
            'width': error_line.get_linewidth()[0],
            'color': mpl_color_to_hex(error_line.get_color()[0])
        }

        return error_bar_options

    # Get colors, as hex strings, of certain plot elements. Includes the plot and axes backgrounds,
    # the border, the ticks, the title and axis labels. All other colors can be obtained in other more
    # specific methods.
    def get_colors(self):

        colors = {}
        ax = self._plot.axes

        # Background color of middle portion of the plot (where the data lines are)
        try:
            colors['plot_background'] = ax.get_facecolor()
        except AttributeError:
            colors['plot_background'] = ax.get_axis_bgcolor()

        # Background color for outside portion of the plot (where axes are)
        colors['axes_background'] = self._figure_canvas.mpl_figure.get_facecolor()

        # Color of border
        colors['border'] = ax.spines['bottom'].get_edgecolor()

        # Color of ticks
        inverted_plot_bg = mpl_color_to_inverted_rgb(colors['plot_background'])
        ticks = ax.xaxis.get_ticklines()
        colors['ticks'] = ticks[0].get_color() if ticks else inverted_plot_bg

        # Color of tick labels
        inverted_axes_bg = mpl_color_to_inverted_rgb(colors['axes_background'])
        tick_labels = ax.xaxis.get_ticklabels()
        colors['tick_labels'] = tick_labels[0].get_color() if tick_labels else inverted_axes_bg

        # Color of title
        colors['title'] = ax.title.get_color()

        # Color of X-label
        colors['x_label'] = ax.xaxis.get_label().get_color()

        # Color of Y-label
        colors['y_label'] = ax.yaxis.get_label().get_color()

        # Convert to MPL colors to a hex string
        for name, mpl_color in six.iteritems(colors):

            colors[name] = mpl_color_to_hex(mpl_color)

        return colors

    # Current grid options for the specified grid lines, either major|minor
    def get_grid_options(self, which):

        if which not in ('major', 'minor'):
            raise ValueError('Unknown grid type: {0}'.format(which))

        axis = self._plot.axes.xaxis
        ticks = axis.majorTicks if which == 'major' else axis.minorTicks
        grid_line = ticks[0].gridline

        grid_options = {
            'visible': self._menu_options['show_{0}_grid'.format(which)],
            'style': get_mpl_linestyles()[grid_line.get_linestyle()],
            'color': mpl_color_to_hex(grid_line.get_color())
        }

        return grid_options

    # Current tick options for the specified type of tick marks, either major|minor
    def get_tick_options(self, which):

        if which not in ('major', 'minor'):
            raise ValueError('Unknown tick type: {0}'.format(which))

        tick_options = {
            'visible': self.menu_option('show_{0}_ticks'.format(which)),
            'direction': self.menu_option('tick_direction'),
            'labels': self._menu_options('show_tick_labels'),
        }

        return tick_options

    # Determine if the title is visible
    def is_title_shown(self):
        return self.menu_option('show_title')

    # Determine if the x and/or y axis labels are visible. Valid options for axis are x|y|both|any.
    def is_label_shown(self, axis):

        x_shown = self._settings['labels']['x']['visible']
        y_shown = self._settings['labels']['y']['visible']

        if axis == 'x':
            return x_shown

        elif axis == 'y':
            return y_shown

        elif axis == 'both':
            return x_shown and y_shown

        elif axis == 'any':
            return x_shown or y_shown

        else:
            raise ValueError('Unknown label type: {0}'.format(axis))

    # Determines if the tick labels are shown. Valid options for axis are x|y|both|any.
    def is_tick_labels_shown(self, axis):

        show_tick_labels = self.menu_option('show_tick_labels')

        if axis in ('x', 'y', 'both'):
            return show_tick_labels == axis

        elif axis == 'any':
            return show_tick_labels in ('x', 'y', 'both')

        else:
            raise ValueError('Unknown tick label type: {0}'.format(axis))

    # Determine if series is shown, as either line|points|both|any.
    def is_series_shown(self, series, which='any'):

        line = self.series[series].plot_line

        line_shown = get_mpl_linestyles()[line.get_linestyle()] != 'nothing'
        points_shown = get_mpl_markerstyles()[line.get_marker()] != 'nothing'

        if which == 'line':
            return line_shown

        elif which == 'points':
            return points_shown

        elif which == 'both':
            return line_shown and points_shown

        elif which == 'any':
            return line_shown or points_shown

        elif which not in('any', 'both', 'line', 'points'):
            raise ValueError('Unknown series type: {0}'.format(which))

    # Determine if error bars for a series are shown. Valid options for which are vertical|horizontal|both|any.
    # To determine whether error bars exist at all, set exist_only to True.
    def is_error_bar_shown(self, series, which='any', exist_only=False):

        vertical_error_lines = self.series[series].error_lines['vertical']
        horizontal_error_lines = self.series[series].error_lines['horizontal']
        vertical_shown = (vertical_error_lines is not None) and (exist_only or vertical_error_lines.get_visible())
        horizontal_shown = (horizontal_error_lines is not None) and (exist_only or horizontal_error_lines.get_visible())

        if (which == 'vertical') and vertical_shown:
            return True

        elif (which == 'horizontal') and horizontal_shown:
            return True

        elif (which == 'any') and (vertical_shown or horizontal_shown):
            return True

        elif (which == 'both') and (vertical_shown and horizontal_shown):
            return True

        elif which not in('vertical', 'horizontal', 'both', 'any'):
            raise ValueError('Unknown error bar type: {0}'.format(which))

        return False

    # Enlarges the initial plot dimensions by enlarge_level (e.g. enlarge_level of 2 will double the
    # dimensions of the original plot, a level of 0.5 will shrink it to half the original size.)
    def set_enlarge_level(self, enlarge_level):
        self._menu_options['enlarge_level'].set(enlarge_level)

    # Sets the axis title, and controls whether it is shown. If keyword is set to None, the current option
    # for that setting will be kept.
    def set_title(self, title=None, show=None, **kwargs):

        ax = self._plot.axes

        # Save the new title settings
        if title is not None:
            self._settings['title'] = title

        if show is not None:

            # We only adjust show_title in menu_options if it is not already set, otherwise there
            # is effectively an infinite loop since it calls this method again
            if self.is_title_shown() != show:
                self._menu_options['show_title'].set(show)

        # Set new title settings. We set an empty title if the title is not currently being shown
        # such that we can save font settings.
        if self.is_title_shown():
            title = self.get_title()

        else:
            title = ''

        # On set_title, MPL will override the below default_kwargs unless they are specified. To preserve
        # existing options, we obtain them and pass them on again unless they are overridden by *kwargs*.
        old_title = self.get_title(mpl_text=True)
        default_kwargs = {
            'fontsize':   old_title.get_fontsize(),
            'fontweight': old_title.get_fontweight(),
            'verticalalignment': old_title.get_verticalalignment(),
            'horizontalalignment': old_title.get_horizontalalignment()}

        default_kwargs.update(kwargs)
        final_kwargs = default_kwargs

        ax.set_title(title, **final_kwargs)

        self._figure_canvas.draw()

    # Sets the axis labels, and controls whether they are shown. If keyword is set to None, the current option
    # for that setting will be kept.
    def set_axis_label(self, axis, label=None, show=None, **kwargs):

        ax = self._plot.axes

        if axis in ('x', 'y'):

            # Save new axis label settings
            settings = self._settings['labels'][axis]

            if label is not None:
                settings['name'] = label

            if show is not None:
                settings['visible'] = show

            # Set show_labels in current menu_options to True if at least one label is being shown,
            # We only adjust it if it does not already match, otherwise there is effectively an infinite
            # loop since it calls this method again
            any_label_shown = self.is_label_shown('any')
            show_labels = self._menu_options['show_labels']

            if any_label_shown != show_labels.get():
                show_labels.set(any_label_shown)

            # Set a new axis label if necessary. We set an empty label if the label is not currently
            # being shown such that we can save font settings.
            if self.is_label_shown(axis):
                label = self.get_axis_label(axis)

            else:
                label = ''

            if axis == 'x':
                ax.set_xlabel(label, **kwargs)

            else:
                ax.set_ylabel(label, **kwargs)

        else:
            raise ValueError('Unknown axis for axis labels: {0}'.format(axis))

        self._figure_canvas.draw()

    # Sets the axis limits. You may manually set axis limits, or use auto limits with the available options
    # being intelligent|auto|tight|manual. If set to None, the current axis limits will be kept.
    def set_axis_limits(self, x=None, y=None, auto=None):

        # Set auto limits
        if auto is not None:
            self._menu_options['axis_limits'].set(auto)

        # Set manual limits
        if (x is not None) or (y is not None):

            ax = self._plot.axes
            self._menu_options['axis_limits'].set('manual')

            if x is not None:
                ax.set_xlim(x)

            if y is not None:
                ax.set_ylim(y)

        self._figure_canvas.draw()

    # Sets axis scaling. Available options for each are linear|log|symlog. If set to None, the current axis
    # scaling will be kept for that axis.
    def set_axis_scaling(self, x=None, y=None):

        # Obtain the current axis scaling setting
        axis_scaling = self.menu_option('axis_scaling')
        x_scale, y_scale = axis_scaling.split('-')

        if x is None:
            x = x_scale

        if y is None:
            y = y_scale

        # Set new axis scaling
        axis_scaling = '{0}-{1}'.format(x, y)
        self._menu_options['axis_scaling'].set(axis_scaling)

    # Set plot and axes background colors, as well as colors of border and ticks. Other colors can be set
    # in other more specific methods. Each color must be an MPL acceptable color.
    def set_colors(self, plot_background=None, axes_background=None, border=None, ticks=None):

        ax = self._plot.axes

        # Set background color of middle portion of the plot (where the data lines are)
        MPLCompat.axis_set_facecolor(ax, plot_background)

        # Set background color for outside portion of the plot (where axes are)
        self._figure_canvas.mpl_figure.set_facecolor(axes_background)
        self._static_canvas.config(bg=mpl_color_to_hex(axes_background))

        # Set color of border
        for spine in ('top', 'bottom', 'left', 'right'):
            ax.spines[spine].set_color(border)

        # Set color of ticks
        tick_lines = (ax.xaxis.get_majorticklines() + ax.xaxis.get_minorticklines() +
                      ax.yaxis.get_majorticklines() + ax.yaxis.get_minorticklines())

        for tick_line in tick_lines:
            tick_line.set_color(ticks)

        self._figure_canvas.draw()

    def invert_colors(self):

        # Freeze the plot display temporarily so it is not needlessly re-drawn multiple times
        self.freeze_display()

        colors = self.get_colors()

        # Set most colors
        kwargs = {}

        for option in ('plot_background', 'axes_background', 'border', 'ticks'):
            kwargs[option] = mpl_color_to_inverted_rgb(colors[option])

        self.set_colors(**kwargs)

        # Set grid color
        for grid_type in ('major', 'minor'):
            grid_color_hex = self.get_grid_options(grid_type)['color']
            grid_color = mpl_color_to_inverted_rgb(grid_color_hex)
            self.set_grid_options(grid_type, color=grid_color)

        # Set label and title colors
        title_color = mpl_color_to_inverted_rgb(colors['title'])
        x_label_color = mpl_color_to_inverted_rgb(colors['x_label'])
        y_label_color = mpl_color_to_inverted_rgb(colors['y_label'])
        tick_label_color = mpl_color_to_inverted_rgb(colors['tick_labels'])

        self.set_title(color=title_color)
        self.set_axis_label('x', color=x_label_color)
        self.set_axis_label('y', color=y_label_color)
        self.set_tick_label_options('both', which='both', color=tick_label_color)

        # Thaw the plot display since it was frozen above
        self.thaw_display()

    # Sets line options for each data series on the currently displayed plot. series specifies the index
    # for the data series on which the line options are to be adjusted. style is an MPL line style for the
    # error bar, color is an MPL color for the line, width is an integer controlling the width of the
    # line. The boolean show controls whether the line is visible on the plot.
    def set_line_options(self, series, style=None, width=None, color=None, show=None):

        line = self.series[series].plot_line

        # Show or hide line
        if (not show) or ((show is None) and (not self.is_series_shown(series, which='line'))):
            line.set_linestyle('none')

        elif style is not None:

            if style not in get_mpl_linestyles():
                style = get_mpl_linestyles(inverse=style)

            line.set_linestyle(style)

        # Set line options (can be set even if line is not shown)
        if width is not None:
            line.set_linewidth(width)

        if color is not None:
            line.set_color(color)

        self._figure_canvas.draw()

    # Sets point options for each data series on the currently displayed plot. series specifies the index
    # for the data series on which the point options are to be adjusted. style is an MPL marker name for the
    # error bar, color is an MPL color for the points, width is an integer controlling the width of the
    # points. The boolean show controls whether the points are visible on the plot.
    def set_point_options(self, series, style=None, width=None, color=None, frequency=None, show=None):

        line = self.series[series].plot_line

        # Show or hide points
        if (not show) or ((show is None) and (not self.is_series_shown(series, which='points'))):
            line.set_marker('None')

        elif style is not None:

            if style not in get_mpl_markerstyles():
                style = get_mpl_markerstyles(inverse=style)

            line.set_marker(style)

        # Set point options (can be set even if points are not shown)
        if width is not None:
            line.set_markersize(width)

        if frequency is not None:
            line.set_markevery(frequency)

        if color is not None:
            line.set_markerfacecolor(color)
            line.set_markeredgecolor(color)

        self._figure_canvas.draw()

    # Sets error bar options for each data series on the currently displayed plot. series specifies the index
    # for the data series on which the error bar options are to be adjusted. which can have values
    # vertical|horizontal|both, specifying for which error bar to set the selected options. style is an MPL
    # line style for the error bar, color is an MPL color for the error line, width is an integer controlling
    # the width of the error line.  The boolean show controls whether the error bars are visible on the plot.
    def set_error_bar_options(self, series, which='both', style=None, width=None, color=None, show=None):

        _series = self.series[series]
        directions = ('vertical', 'horizontal') if which == 'both' else (which,)

        for which in directions:

            # Check if error bars exist for this direction prior to setting options
            if not self.is_error_bar_shown(series, which=which, exist_only=True):
                continue

            # Set error cap options
            for cap in _series.error_caps[which]:

                if show is not None:
                    cap.set_visible(show)

                if color is not None:
                    cap.set_markeredgecolor(color)

                # Error cap widths are set to preserve initial MPL proportions to error bar line width
                if width is not None:
                    cap.set_markersize(4+width)
                    cap.set_markeredgewidth(width/2)

            # Set error line options
            error_line = _series.error_lines[which]

            if show is not None:
                error_line.set_visible(show)

            if color is not None:
                error_line.set_color(color)

            if width is not None:
                error_line.set_linewidth(width)

            if style is not None:

                if style not in get_mpl_linestyles():
                    style = get_mpl_linestyles(inverse=style)

                error_line.set_linestyle(style)

        self._figure_canvas.draw()

    # Sets grid options on the currently displayed plot. which can have values major|minor|both, specifying
    # to which grid lines the rest of the options apply. style is a MPL line style for the grid line,
    # color is an MPL line color and the show boolean specifies whether the grid lines will be visible. To
    # keep existing value for any variable use None.
    def set_grid_options(self, which='both', style=None, color=None, show=None):

        if which in ('major', 'minor', 'both'):

            # Show or hide grid
            if show is not None:

                if which in ('major', 'both'):
                    self._menu_options['show_major_grid'].set(show)

                if which in ('minor', 'both'):
                    self._menu_options['show_minor_grid'].set(show)

            # Set grid style
            if style is not None:
                self.menu_option('grid_linestyle').set(style)

            # Set grid color
            if color is not None:
                self._plot.axes.grid(which=which, color=color)

            # Setting the grid color above automatically displays grid even if it was not suppose to be
            # displayed. We run `_update_grid` to ensure it is hidden if it should be, while preserving
            # the linestyle and color changes.
            self._update_grid()

        else:
            raise ValueError('Unknown grid type: {0}'.format(which))

        self._figure_canvas.draw()

    # Sets tick options on the currently displayed plot. which can have values major|minor|both, specifying
    # which ticks to show or hide via the show boolean. direction can have values in|out, specifying in which
    # direction the ticks are facing in the plot if they are shown. To keep existing value for any variable
    # use None.
    def set_tick_options(self, which='both', direction=None, show=None):

        if which in ('major', 'minor', 'both'):

            # Show or hide ticks
            if show is not None:

                if which in ('major', 'both'):
                    self._menu_options['show_major_ticks'].set(show)

                if which in ('minor', 'both'):
                    self._menu_options['show_minor_ticks'].set(show)

            # Set tick direction
            if direction is not None:
                self._menu_options['tick_direction'].set(direction)

        else:
            raise ValueError('Unknown tick type: {0}'.format(which))

    # Set tick label options on the currently displayed plot. axis can have values x|y|both, and which
    # can have values major|minor|both, specifying which tick labels to adjust. show can have values
    # x|y|both|none, indicating which tick labels to show on the plot.
    def set_tick_label_options(self, axis, which='major', show=None, **kwargs):

        # Find the right axes to set tick labels
        if axis == 'both':
            axes = ('x', 'y')

        else:
            axes = (axis,)

        # Update whether tick labels for an axis are shown or not
        if show is not None:
            self._menu_options['show_tick_labels'].set(show)

        # Update tick label options for selected axes (must be done once they are shown)
        for axis in axes:

            tick_labels = self.get_tick_labels(axis=axis, which=which, mpl_text=True)

            for label in tick_labels:
                label.update(kwargs)

        self._figure_canvas.draw()

    # Controls certain axes display options for current plot. invert_axis can have values x|y|both|none.
    # show_border is a boolean that controls whether a border is displayed around image. To keep existing
    # values use None.
    def set_axes_display(self, invert_axis=None, show_border=None):

        if invert_axis is not None:
            self._menu_options['invert_axis'].set(invert_axis)

        if show_border is not None:
            self._menu_options['show_border'].set(show_border)

    # Save the plot image to disk (as currently displayed). The extension in filename controls the image
    # format unless *format* is set; likely supported formats are support png, pdf, ps, eps and svg.
    def save_image(self, filename, format=None):

        # Save figure, ensure facecolor is not ignored
        mpl_canvas = self._figure_canvas.mpl_canvas
        mpl_canvas.print_figure(filename,
                                dpi=self._settings['dpi'],
                                facecolor=self._figure_canvas.mpl_figure.get_facecolor(),
                                format=format)

    # Freezes redrawing of image/plot on the screen, such that any updates to the plot are not reflected
    # until it is thawed via `thaw_display`. This can be helpful, both for performance reasons and to hide
    # ugly redrawing, if the plot would otherwise be redrawn a number of intermediate times.
    def freeze_display(self):

        # Increment counter that stores number of times freeze_display/thaw_display has been called
        self._freeze_display_counter += 1

        # If display is not already frozen, freeze it (by unpacking display_frame and freezing the canvas)
        if self._freeze_display_counter == 1:

            if self._figure_canvas is not None:
                self._figure_canvas.freeze()

    # Thaws a frozen display (see `freeze_display`)
    def thaw_display(self):

        # Decrement counter that stores number of times freeze_display/thaw_display has been called
        if self._freeze_display_counter > 0:
            self._freeze_display_counter -= 1

        # If display should be thawed, then do so
        if self._freeze_display_counter == 0:

            # Thaw the image now that its being displayed again
            if self._figure_canvas is not None:
                self._figure_canvas.thaw()

            # Update scrollable canvas to account for new scrollregion needed
            self._update_scrollable_canvas_dimensions()

    # Adds menu options used for manipulating the data display
    def _add_menus(self):

        # Add Save Plot option to the File menu
        file_menu = self._menu('File', in_menu='main')
        file_menu.insert_command(0, label='Save Plot', command=self._save_file_box)

        file_menu.insert_separator(1)

        # Add a Data menu
        data_menu = self._add_menu('Data', in_menu='main')

        data_menu.add_command(label='Lines / Points',
                              command=lambda: self._open_plot_options('Lines / Points'))

        data_menu.add_separator()

        data_menu.add_command(label='Error Bars',
                              command=lambda: self._open_plot_options('Error Bars'))

        # Add an Axes menu
        axes_menu = self._add_menu('Axes', in_menu='main')

        axes_menu.add_checkbutton(label='Tight Limits', onvalue='tight', offvalue='manual',
                                        variable=self._menu_options['axis_limits'])

        axes_menu.add_checkbutton(label='Auto Limits', onvalue='auto', offvalue='manual',
                                        variable=self._menu_options['axis_limits'])

        axes_menu.add_command(label='Manual Limits',
                              command=lambda: self._open_plot_options('Axes'))

        axes_menu.add_separator()

        axes_menu.add_checkbutton(label='Pan', onvalue=True, offvalue=False, variable=self._menu_options['pan'])
        axes_menu.add_checkbutton(label='Axis-Limits to Rectangle', onvalue=True, offvalue=False,
                                  variable=self._menu_options['axis_limits_to_rectangle'])

        axes_menu.add_separator()

        invert_options = OrderedDict([('X', 'x'), ('Y', 'y'), ('XY', 'both')])
        for axis, option in six.iteritems(invert_options):

            label = 'Invert {0}'.format(axis)

            axes_menu.add_checkbutton(label=label, onvalue=option, offvalue='none',
                                      variable=self._menu_options['invert_axis'])

        axes_menu.add_separator()

        # Add an Axis Scaling sub-menu to the Axes menu
        axis_scaling_menu = self._add_menu('Axis Scaling', in_menu='Axes')

        axis_scaling = OrderedDict([('Linear-Linear', 'linear-linear'), ('Log-Log', 'log-log'),
                                    ('SymLog-SymLog', 'symlog-symlog'),
                                    ('X-Log', 'log-linear'), ('Y-Log', 'linear-log'),
                                    ('X-SymLog', 'symlog-linear'), ('Y-SymLog', 'linear-symlog')])
        for label, scale in six.iteritems(axis_scaling):

            if 'X' in label:
                axis_scaling_menu.add_separator()

            axis_scaling_menu.add_checkbutton(label=label, onvalue=scale, offvalue=scale,
                                              variable=self._menu_options['axis_scaling'])

        # Add a Chart menu
        chart_menu = self._add_menu('Chart', in_menu='main')

        # grid_menu.add_separator()
        #
        # for color in ('white', 'gray', 'black'):
        #     grid_menu.add_checkbutton(label=color.upper(), onvalue=color, offvalue=color,
        #                               variable=self._menu_options['grid_color'])

        chart_menu.add_checkbutton(label='Show Plot Border', onvalue=True, offvalue=False,
                                   variable=self._menu_options['show_border'])

        chart_menu.add_separator()

        # Add a Grid sub-menu to the Chart menu
        grid_menu = self._add_menu('Grid', in_menu='Chart')

        grid_menu.add_checkbutton(label='Show Major Grid', onvalue=True, offvalue=False,
                                  variable=self._menu_options['show_major_grid'])

        grid_menu.add_checkbutton(label='Show Minor Grid', onvalue=True, offvalue=False,
                                  variable=self._menu_options['show_minor_grid'])

        grid_menu.add_separator()

        for grid_linestyle in ('dotted', 'dashed', 'dashdot', 'solid'):
            grid_menu.add_checkbutton(label=grid_linestyle.capitalize(), onvalue=grid_linestyle,
                                      offvalue=grid_linestyle, variable=self._menu_options['grid_linestyle'])

        chart_menu.add_separator()

        # Add a Ticks sub-menu to the Chart menu
        ticks_menu = self._add_menu('Ticks', in_menu='Chart')

        ticks_menu.add_checkbutton(label='Inward Facing Ticks', onvalue='in', offvalue='in',
                                   variable=self._menu_options['tick_direction'])
        ticks_menu.add_checkbutton(label='Outward Facing Ticks', onvalue='out', offvalue='out',
                                   variable=self._menu_options['tick_direction'])

        ticks_menu.add_separator()

        ticks_menu.add_checkbutton(label='Show Major Ticks', onvalue=True, offvalue=False,
                                   variable=self._menu_options['show_major_ticks'])
        ticks_menu.add_checkbutton(label='Show Minor Ticks', onvalue=True, offvalue=False,
                                   variable=self._menu_options['show_minor_ticks'])

        ticks_menu.add_separator()

        ticks_menu.add_checkbutton(label='Show Tick Labels', onvalue='both', offvalue='none',
                                   variable=self._menu_options['show_tick_labels'])

        chart_menu.add_separator()

        # Add a Legend sub-menu to the Chart menu
        # legend_menu = self._add_menu('Legend', in_menu='Chart')
        #
        # legend_menu.add_checkbutton(label='Show Legend', onvalue=True, offvalue=False,
        #                             variable=self._menu_options['show_legend'])
        #
        # legend_menu.add_command(label='Set Legend', command=
        #                         lambda: self._add_dependent_window(PlotOptionsWindow(self._viewer, self)))
        #
        # legend_menu.add_separator()
        #
        # for legend_position in ('upper right', 'upper left', 'lower right', 'lower left'):
        #     legend_menu.add_checkbutton(label=legend_position.title(), onvalue=legend_position,
        #                                 offvalue=legend_position, variable=self._menu_options['legend_position'])
        #
        # chart_menu.add_separator()

        chart_menu.add_command(label='Colors', command=
                                               lambda: self._open_plot_options(initial_display='Colors'))

        chart_menu.add_command(label='Invert Colors', command=self.invert_colors)

        # Add a Labels menu
        labels_menu = self._add_menu('Labels', in_menu='main')

        labels_menu.add_checkbutton(label='Show Title', onvalue=True, offvalue=False,
                                    variable=self._menu_options['show_title'])

        labels_menu.add_command(label='Set Title', command=lambda: self._open_plot_options('Labels'))

        labels_menu.add_separator()

        labels_menu.add_checkbutton(label='Show Axis Labels', onvalue=True, offvalue=False,
                                    variable=self._menu_options['show_labels'])

        labels_menu.add_command(label='Set Axis Labels', command=lambda: self._open_plot_options('Labels'))

        # Add a Size menu
        size_menu = self._add_menu('Size', in_menu='main')

        size_menu.add_command(label='Fit to Window Size', command=self.enlarge_to_fit)

        size_menu.add_separator()

        size_menu.add_command(label='Reset Original Size', command=lambda: self._enlarge(enlarge_level=1))

        size_menu.add_separator()

        size_menu.add_command(label='Enlarge Plot', command=lambda: self._enlarge('in'))
        size_menu.add_command(label='Shrink Plot', command=lambda: self._enlarge('out'))

        # Add a View Menu
        self._add_view_menu()

    # Adds a view menu
    def _add_view_menu(self):
        self._add_menu('View', in_menu='main', postcommand=self._update_view_menu)

    # Adds or updates menu options for the View menu
    def _update_view_menu(self):

        view_menu = self._menu('View')

        # Delete all items in the menu
        view_menu.delete(0, view_menu.index('last'))

        # Find unique structures
        structures = [series.structure for series in self.series]
        unique_structures = set(structures)

        # Add Labels sub-menu if necessary
        multi_label = len(unique_structures) > 1
        if multi_label:
            label_menu = self._add_menu('Labels', 'View')

        else:
            label_menu = view_menu

        # Add Label open button for each unique structure in plot
        for structure in unique_structures:

            labels = [structure.full_label, structure.label]
            label_text = 'Label - {}'.format(structure.id) if multi_label else 'Label'

            label_menu.add_command(label=label_text, command=lambda: label_view.open_label(
                                   self._viewer, *labels, initial_display='object label'))

        view_menu.add_separator()

        view_menu.add_command(label='Warnings',
                              command=lambda: MessageWindow(self._viewer, 'Warnings', self._warnings))

    # Draws the header box, which contains the pixel location that mouse pointer is over
    def _draw_header(self):

        header_box = Frame(self._header, bg=self.get_bg('gray'))
        header_box.pack(fill='x', expand=1)

        value_box_params = {'background': self.get_bg('gray'), 'borderwidth': 1, 'relief': 'groove'}
        line_box_params = {'background': self.get_bg('gray'), 'height': 25}

        entry_params = {'disabledbackground': self.get_bg('gray'), 'state': 'disabled',
                        'borderwidth': 0, 'highlightthickness': 0, 'disabledforeground': 'black'}

        # Add the header line containing X and Y value the mouse is hovering over
        pixel_line_box = Frame(header_box, **line_box_params)
        pixel_line_box.pack(side='top', anchor='w', pady=(2, 2))

        pixel_text_box = Frame(pixel_line_box, height=25, width=70, bg=self.get_bg('gray'))
        pixel_text_box.pack(side='left')

        w = Label(pixel_text_box, text='Pixel', bg=self.get_bg('gray'))
        w.pack(side='left')

        # X value
        w = Label(pixel_text_box, text='X', bg=self.get_bg('gray'))
        w.pack(side='right', padx=(0, 5))

        pixel_text_box.pack_propagate(False)

        x_pixel_box = Frame(pixel_line_box, height=25, **value_box_params)
        x_pixel_box.pack(side='left')

        x_pixel = StringVar()
        self._header_widgets['x'] = x_pixel
        e = Entry(x_pixel_box, textvariable=x_pixel, width=13, **entry_params)
        e.pack(side='left', padx=(10, 10))

        # Y value
        w = Label(pixel_line_box, text='Y', bg=self.get_bg('gray'))
        w.pack(side='left', padx=(10, 5))

        y_pixel_box = Frame(pixel_line_box, height=25, **value_box_params)
        y_pixel_box.pack(side='left')

        y_pixel = StringVar()
        self._header_widgets['y'] = y_pixel
        e = Entry(y_pixel_box, textvariable=y_pixel, width=13, **entry_params)
        e.pack(side='left', padx=(10, 10))

        divider = Frame(header_box, height=1, bg='#737373')
        divider.pack(side='bottom', fill='x', expand=1)

    # Initializes or updates the MPL Figure and draws a plot for the series on it. load_table() must have
    # been called for the table this series came from prior to this method being called.
    def _draw_series(self, series, lines=None, points=None, mask_special=None):

        # Freeze the plot display temporarily so it is not needlessly re-drawn multiple times
        self.freeze_display()

        # Create the figure if it does not exist
        if not self._data_open:

            # Determine figure display properties
            dpi = self._settings['dpi']
            smallest_dim = min(self._static_canvas.winfo_width(), self._static_canvas.winfo_height())
            fig_size = (smallest_dim / dpi, smallest_dim / dpi)

            # Store initial figure size
            self._settings['pixel_init_dimensions'] = (smallest_dim, smallest_dim)

            # Create the figure
            figure_kwargs = {'figsize': fig_size, 'dpi': self._settings['dpi'], 'facecolor': 'white'}

            try:
                figure = Figure(tight_layout=True, **figure_kwargs)

            # MPL versions earlier than 1.1 do not have tight layout
            except TypeError:
                figure = Figure(**figure_kwargs)

            # Create the FigureCanvas, which is a wrapper for FigureCanvasTkAgg()
            self._figure_canvas = FigureCanvas(figure, master=self._scrollable_canvas)
            self._figure_canvas.tk_widget.config(background='white')
            self._scrollable_canvas.create_window(0, 0, window=self._figure_canvas.tk_widget, anchor='nw')

            # Create the toolbar (hidden, used for its pan and axis-limits to rectangle options)
            self._toolbar = MPLCompat.NavigationToolbar2Tk(self._figure_canvas.mpl_canvas, self._display_frame)
            self._toolbar.update()
            self._toolbar.pack_forget()

            # Add the plot axes
            self._plot = figure.add_subplot(1, 1, 1)

        # Add the plot / series to the axes
        _series = self.series[series]
        plot_line, error_caps, error_lines = self._plot.errorbar(_series.data('x', masked=mask_special),
                                                                 _series.data('y', masked=mask_special),
                                                                 xerr=_series.data('x_err', masked=mask_special),
                                                                 yerr=_series.data('y_err', masked=mask_special),
                                                                 capsize=3,
                                                                 zorder=500)
        _series.add_plot(plot_line, error_caps, error_lines)

        # Set default Lines and Points options
        self.set_line_options(series, width=1, style='solid', color='#0000ff', show=lines)
        self.set_point_options(series, style='point', color='#0000ff', show=points)

        # Set default Error Bar options
        self.set_error_bar_options(series, style='dotted', color='#3535ff', width=1)

        # Set default Title, Axis Labels and Tick Labels options
        self.set_title('', fontsize='14', fontweight='normal', y=1.01)
        self.set_axis_label('x', _series.label('x'), fontsize='11', fontweight='bold')
        self.set_axis_label('y', _series.label('y'), fontsize='11', fontweight='bold')
        self.set_tick_label_options(axis='both', which='both', fontsize='12')

        # Update all settings to match current menu_options
        self._update_labels()
        self._update_invert_axis()
        self._update_axis_scaling()
        self._update_grid()
        self._update_border()
        self._update_enlarge_level()

        # Thaw the plot display since it was frozen above
        self.thaw_display()

    # Activates the Pan image option
    def _pan(self, *args):

        # Disable axis-limits to rectangle if it is enabled
        limits_option = self._menu_options['axis_limits_to_rectangle']
        pan_option = self._menu_options['pan']

        if pan_option.get() and limits_option.get():
            limits_option.set(False)

        # Disable auto limits if enabled and if enabling pan
        auto_limits = self.menu_option('axis_limits') != 'manual'

        if auto_limits and pan_option.get():
            self.set_axis_limits(auto='manual')

        # Enable pan
        self._toolbar.pan()

    # Activates the Axis-Limits to Rectangle option
    def _axis_limits_to_rectangle(self, *args):

        # Disable pan if it is enabled
        limits_option = self._menu_options['axis_limits_to_rectangle']
        pan_option = self._menu_options['pan']

        if pan_option.get() and limits_option.get():
            pan_option.set(False)

        # Disable auto limits if enabled and if enabling axis-limits to rectangle
        auto_limits = self.menu_option('axis_limits') != 'manual'

        if auto_limits and limits_option.get():
            self.set_axis_limits(auto='manual')

        # Enable axis-limits to rectangle (called zoom by MPL)
        self._toolbar.zoom()

    # Update menu_options to specified enlarge_level, then call `_update_enlarge` to enlarge to that level.
    # If no enlarge level is specified then an action may be specified, and the plot size in changed in or out
    # (depending on the action) by the enlarge_level variable
    def _enlarge(self, action='in', enlarge_level=None):

        # Determine zoom level if none if specified
        if enlarge_level is None:

            # Obtain the current enlarge level
            enlarge_level = self.get_enlarge_level()

            # Determine enlarge level when adjusted by enlarge factor
            enlarge_factor = 0.20

            if action == 'in':
                enlarge_level *= (1 + enlarge_factor)
            else:
                enlarge_level /= (1 + enlarge_factor)

        # Save the new enlarge level
        self.set_enlarge_level(enlarge_level)

    # Enlarge image to the level set by menu_options
    def _update_enlarge_level(self, *args):

        # Freeze the plot display temporarily so it is not needlessly re-drawn multiple times
        self.freeze_display()

        fig_size = self._settings['pixel_init_dimensions']

        # Change figure size by enlarge_level
        enlarge_level = self.get_enlarge_level()
        enlarged_size = [fig_size[0] * enlarge_level,
                         fig_size[1] * enlarge_level]

        # Ensure that the enlarged size is at least 1x1 pixel
        enlarged_size[0] = 1 if enlarged_size[0] < 1 else enlarged_size[0]
        enlarged_size[1] = 1 if enlarged_size[1] < 1 else enlarged_size[1]

        # Resize the figure to match the enlarge level
        self._figure_canvas.set_dimensions(enlarged_size, type='pixels')

        # Update ticks to set new tick lengths, and new number of ticks
        self._update_ticks(adjust_num_ticks=True)

        # The scrollable canvas dimensions change since plot dimensions change and need updating
        self._update_scrollable_canvas_dimensions()

        # Thaw the plot display since it was frozen above
        self.thaw_display()

    # Enlarge or shrink the plot to fit the current window
    def enlarge_to_fit(self):

        fig_size = self._settings['pixel_init_dimensions']

        # Retrieve width and height of static_canvas (the width and height that we need to fit)
        self._widget.update_idletasks()
        width = self._static_canvas.winfo_width()
        height = self._static_canvas.winfo_height()

        fig_size_div = (width / fig_size[0],
                        height / fig_size[1])

        enlarge_level = min(fig_size_div)
        self._enlarge(enlarge_level=enlarge_level)

    # Determine if either axis is a date. Valid options for axis are x|y|both|any.
    def _is_date_axis(self, axis):

        x_date = False
        y_date = False

        # Check if any serious has datetime data
        for _series in self.series:

            if (not x_date) and _series.meta_data('x').data_type().issubtype('datetime'):
                x_date = True

            if (not y_date) and _series.meta_data('y').data_type().issubtype('datetime'):
                y_date = True

        # Return result
        if axis == 'x':
            return x_date

        elif axis == 'y':
            return y_date

        elif axis == 'both':
            return x_date and y_date

        elif axis == 'any':
            return x_date or y_date

        else:
            raise ValueError('Unknown axis: {0}'.format(axis))

    # Update axis limits setting to match the current menu_options value
    def _update_axis_limits(self, *args):

        # Freeze the plot display temporarily so it is not needlessly re-drawn multiple times
        self.freeze_display()

        # Obtain the current axis limits settings
        axis_limits = self.menu_option('axis_limits')

        # Keep track of when to reset margins (needed when turning off tight limits)
        reset_margins = False

        # Set new axis limits
        ax = self._plot.axes

        # Disable pan and axis-limits to rectangle if they are enabled and we are not on manual axis limits
        if axis_limits != 'manual':

            limits_option = self._menu_options['axis_limits_to_rectangle']
            pan_option = self._menu_options['pan']

            if limits_option.get():
                limits_option.set(False)

            elif pan_option.get():
                pan_option.set(False)

        # Intelligent limits. If error bars are present or only points are on, equivalent to auto scaling. Otherwise
        # uses tight scaling for linear data, and uses auto scaling for all others.
        if axis_limits == 'intelligent':

            shows_error_bars = False
            shows_only_points = False

            for i in range(0, len(self.series)):

                if self.is_series_shown(i, which='points') and (not self.is_series_shown(i, which='line')):
                    shows_only_points = True
                    break

                elif self.is_series_shown(i) and self.is_error_bar_shown(i):
                    shows_error_bars = True
                    break

            if (ax.get_xscale() == 'linear') and (ax.get_yscale() == 'linear') and \
                    (not shows_error_bars) and (not shows_only_points):

                ax.autoscale(axis='both', enable=True, tight=True)

            else:
                reset_margins = True
                ax.autoscale(axis='both', enable=True, tight=False)

        # Automatic limits. Usually uses axis limits which are somewhat bigger than data limits.
        elif axis_limits == 'auto':
            reset_margins = True
            ax.autoscale(axis='both', enable=True, tight=False)

        # Tight limits. Constrains axis limits to exactly data limits.
        elif axis_limits == 'tight':
            ax.autoscale(axis='both', enable=True, tight=True)

        elif axis_limits != 'manual':
            ax.autoscale(axis='both', enable=False)

            self._menu_options['axis_limits'].set('intelligent')
            raise ValueError('Unknown axis limits: {0}'.format(axis_limits))

        # Set default margins for MPL 2+. Otherwise setting autoscale to tight permanently sets these to 0,
        # which means that auto and intelligent limits will not work in the 'data' autolimit mode.
        if reset_margins and (mpl.rcParams.get('axes.autolimit_mode') == 'data'):
            ax.margins(x=0.05, y=0.05)

        # Update ticks to set new number of ticks
        self._update_ticks(adjust_num_ticks=True)

        # Thaw the plot display since it was frozen above
        self.thaw_display()

    # Update scaling of the axes to match the current menu_options values
    def _update_axis_scaling(self, *args):

        # Obtain the current axis scaling setting
        axis_scaling = self.menu_option('axis_scaling')

        # Find new axis scaling for axes
        ax = self._plot.axes
        x_scale, y_scale = axis_scaling.split('-')

        if (x_scale not in ('linear', 'log', 'symlog')) or (y_scale not in ('linear', 'log', 'symlog')):

            self._menu_options['axis_scaling'].set('linear-linear')
            raise ValueError('Unknown scale type: {0}'.format(axis_scaling))

        else:

            # Freeze the plot display temporarily so it is not needlessly re-drawn multiple times
            self.freeze_display()

            # Set new scaling of the axes
            if not self._is_date_axis('x'):
                ax.set_xscale(x_scale)

            if not self._is_date_axis('y'):
                ax.set_yscale(y_scale)

            # For intelligent axis limits we need to update the axis limits based on current scale type.
            # Inside this method it also updates ticks, which is necessary because setting new scaling above
            # automatically adjusts some tick options (e.g. minor tick visibility).
            self._update_axis_limits()

            # Thaw the plot display since it was frozen above
            self.thaw_display()

    def _update_labels(self, *args):

        # Freeze the plot display temporarily so it is not needlessly re-drawn multiple times
        self.freeze_display()

        # Obtain current axis label settings
        show_title = self.menu_option('show_title')
        show_labels = self.menu_option('show_labels')

        # Show / Hide labels
        show_both_labels = show_labels and (not self.is_label_shown('any'))
        hide_both_labels = (not show_labels) and self.is_label_shown('any')

        if show_both_labels or hide_both_labels:

            self.set_axis_label('x', show=show_labels)
            self.set_axis_label('y', show=show_labels)

        # Show / Hide title
        self.set_title(show=show_title)

        # Thaw the plot display since it was frozen above
        self.thaw_display()

    # Update tick options (show / hide ticks and labels, and tick direction) to match
    # current menu_options values
    def _update_ticks(self, adjust_num_ticks=False, *args):

        # Obtain current tic settings
        show_major_ticks = self.menu_option('show_major_ticks')
        show_minor_ticks = self.menu_option('show_minor_ticks')
        show_tick_labels = self.menu_option('show_tick_labels')
        tick_direction = self.menu_option('tick_direction')

        ax = self._plot.axes

        # Validate tick labels setting
        if show_tick_labels not in ('x', 'y', 'both', 'none'):
            self._menu_options['show_tick_labels'].set('both')
            raise ValueError('Unknown tick labels axis to display: {0}'.format(show_tick_labels))

        # Validate tick direction setting
        if tick_direction not in ('in', 'out'):
            self._menu_options['tick_direction'].set('in')
            raise ValueError('Unknown tick direction selected: {0}'.format(tick_direction))

        # Determine a good tick length for the current plot size
        width, height = self._figure_canvas.get_dimensions(type='pixels')
        major_tick_length = max(4, 4 * min(width, height) / 400)
        minor_tick_length = major_tick_length / 2

        # Set new major tick settings (show / hide, direction, labels and size)
        ax.tick_params(axis='both', which='major', direction=tick_direction,
                       bottom=show_major_ticks, top=show_major_ticks,
                       left=show_major_ticks, right=show_major_ticks,
                       labelbottom=show_tick_labels in ('x', 'both'),
                       labelleft=show_tick_labels in ('y', 'both'),
                       length=major_tick_length, width=0.5)

        # Set number of major tick labels for X-axis (in small plots, these are prone to overlapping)
        # This is intended to work with the default tick label fonts and font sizes only.
        if adjust_num_ticks and ax.get_xscale() == 'linear':

            # Initially we reset to default number of major ticks
            # (ensures that when enlarging plot from a small plot, we go back to proper number of ticks;
            #  we distinguish for date axes because AutoDateLocator does not support locator_params)
            if self._is_date_axis('x'):
                ax.xaxis.set_major_locator(mpl.dates.AutoDateLocator())
            else:
                self._plot.locator_params(axis='x', nbins=9, prune='both')

            # The correct tick labels are not given by MPL's ``Axis.get_ticklabels`` until they are drawn
            # (it will return empty text objects instead). To avoid the ugly redrawing of the plot to
            # obtain the correct tick labels (needed below), we use the draw method of the Axes instead.
            # This does not seem to actually draw anything on the screen, but afterward we can obtain the
            # correct tick labels as expected.
            renderer = self._figure_canvas.mpl_canvas.get_renderer()
            ax.draw(renderer)

            plot_size = self._figure_canvas.get_dimensions(type='pixels')

            num_iterations = 0
            num_ticks = len(ax.xaxis.get_ticklabels())

            while True:

                # Get tick labels (note that this only works if plot has been redrawn
                # once the parameters that determine the tick labels were set)
                tick_labels = [label.get_text() for label in ax.xaxis.get_ticklabels()]

                # Remove mathtext, as we do cannot actually estimate its length easily
                tick_labels = [re.sub(r'\$.+\$', '', label) for label in tick_labels]

                num_label_chars = len(''.join(tick_labels))
                num_tick_labels = len(tick_labels)
                num_bins = num_ticks - num_iterations

                if num_tick_labels <= 2 or num_label_chars <= 1 or num_bins <= 0:
                    break

                # Adjust maximum number of ticks so that the below equation is satisfied
                # (the specific number is chosen based on experimentation of what looks good;
                #  we distinguish for date axes because AutoDateLocator does not support locator_params)
                avg_label_len = sum(map(len, tick_labels)) / num_tick_labels
                max_density = min(20 - avg_label_len, 15)

                if plot_size[0] / num_label_chars < max_density:

                    if self._is_date_axis('x'):
                        ax.xaxis.set_major_locator(mpl.dates.AutoDateLocator(maxticks=num_bins))
                    else:
                        self._plot.locator_params(axis='x', nbins=num_bins, prune='both')

                else:
                    break

                num_iterations += 1

        # Set new minor tick settings (show / hide, direction and size)
        if show_minor_ticks:

            # Enable minor ticks
            ax.minorticks_on()

            ax.tick_params(axis='both', which='minor', direction=tick_direction,
                           bottom=True, top=True, left=True, right=True,
                           length=minor_tick_length, width=0.5)

            # Turning off major ticks makes them completely disappear. Instead we show them, but shorter,
            # so they look the same as minor ticks.
            if not show_major_ticks:
                ax.tick_params(axis='both', which='major', direction=tick_direction,
                               bottom=True, top=True, left=True, right=True,
                               length=minor_tick_length, width=0.5)

        else:

            # Instead of `axis.minorticks_off` we set length to 0. The former method has the disadvantage that
            # minor grid lines will not appear when minor ticks are off.
            ax.tick_params(axis='both', which='minor', length=0, width=0)

        # Remove offset and scientific notation when tick labels are not shown
        for axis_name, axis_select in six.iteritems({'x': ax.xaxis, 'y': ax.yaxis}):

            if isinstance(axis_select.get_major_formatter(), mpl.ticker.ScalarFormatter):

                use_offset = show_tick_labels in (axis_name, 'both')
                style = 'sci' if use_offset else 'plain'

                ax.ticklabel_format(useOffset=use_offset, style=style, axis=axis_name)

        self._figure_canvas.draw()

    # Update the plot border visibility to match current menu_options value
    def _update_border(self, *args):

        # Obtain current border setting
        show_border = self.menu_option('show_border')
        ax = self._plot.axes

        for spine in ['top', 'bottom', 'left', 'right']:
            ax.spines[spine].set_visible(show_border)

        self._figure_canvas.draw()

    # Update grid options (show/hide and linestyle) to match current menu_options values
    def _update_grid(self, *args):

        # Obtain current grid settings
        show_major_grid = self.menu_option('show_major_grid')
        show_minor_grid = self.menu_option('show_minor_grid')
        grid_linestyle = self.menu_option('grid_linestyle')

        ax = self._plot.axes

        if grid_linestyle not in ('solid', 'dashed', 'dashdot', 'dotted'):

            self._menu_options['grid_linestyle'].set('dotted')
            raise ValueError('Unknown grid linestyle: {0}'.format(grid_linestyle))

        # Set major grid line settings
        if show_major_grid:
            ax.grid(which='major', linestyle=grid_linestyle, linewidth=1)
        else:
            MPLCompat.axis_set_grid(ax, which='major', visible=False)

        # Set minor grid line settings
        if show_minor_grid:

            ax.grid(which='minor', linestyle=grid_linestyle, linewidth=0.5)

            # Show major grid line with same thickness as minor grid lines if it is not enabled. Otherwise
            # there will simply be missing grid lines in those spots.
            if not show_major_grid:
                ax.grid(which='major', linestyle=grid_linestyle, linewidth=0.5)

        else:
            MPLCompat.axis_set_grid(ax, which='minor', visible=False)

        self._figure_canvas.draw()

    # Update axis inversion to match current menu_options value
    def _update_invert_axis(self, *args):

        invert_axis = self.menu_option('invert_axis')
        ax = self._plot.axes

        # Reset any axis inversion
        if ax.yaxis_inverted():
            ax.invert_yaxis()

        if ax.xaxis_inverted():
            ax.invert_xaxis()

        # Invert X, Y or both axes based on current menu settings
        if invert_axis == 'x':
            ax.invert_xaxis()

        elif invert_axis == 'y':
            ax.invert_yaxis()

        elif invert_axis == 'both':
            ax.invert_xaxis()
            ax.invert_yaxis()

        elif invert_axis != 'none':
            self._menu_options['invert_axis'].set('none')
            raise ValueError('Unknown axis to invert: {0}'.format(invert_axis))

        self._figure_canvas.draw()

    # Sets the X and Y in the header based on current mouse pointer location
    def _update_mouse_pixel_value(self, event):

        event_outside_bounds = True

        # If the event is an MPL MouseEvent then we may have scrolled mouse on the image
        if isinstance(event, mpl.backend_bases.MouseEvent):

            event_has_position = (event.xdata is not None) and (event.ydata is not None)
            is_on_plot = event.inaxes == self._plot.axes

            if event_has_position and is_on_plot:

                self._header_widgets['x'].set(round(event.xdata, 5))
                self._header_widgets['y'].set(round(event.ydata, 5))

                event_outside_bounds = False

        # Remove values from X and Y if the mouse pointer is not on the image
        if event_outside_bounds:
            self._header_widgets['x'].set('')
            self._header_widgets['y'].set('')

    # Opens a PlotOptionsWindow
    def _open_plot_options(self, initial_display=None):

        window = PlotOptionsWindow(self._viewer, self._widget, self, initial_display=initial_display)
        self._add_dependent_window(window)

    # Called when the window has been resized, this method updates the dimensions of the various things that
    # need resizing together with a window resize
    def _window_resize(self, event):

        self._update_window_dimensions()
        self._update_scrollable_canvas_dimensions()

    # Updates scrollable canvas size and scroll region, needed any time the contents of scrollable canvas
    # have changed size
    def _update_scrollable_canvas_dimensions(self):

        self._widget.update_idletasks()

        # Retrieve width and height of the image
        dimensions = self._figure_canvas.get_dimensions()
        scroll_width = dimensions[0]
        scroll_height = dimensions[1]

        # Adjust width and height of the _scrollable_canvas, while ensuring that it is not larger than the
        # window dimensions (or more specifically the static_canvas dimensions, because both header and
        # scrollbars take up some space)
        width = scroll_width
        if width > self._static_canvas.winfo_width():
            width = self._static_canvas.winfo_width()

        height = scroll_height
        if height > self._static_canvas.winfo_height():
            height = self._static_canvas.winfo_height()

        self._scrollable_canvas.configure(width=width, height=height)
        self._scrollable_canvas.configure(scrollregion=(0, 0, scroll_width, scroll_height))

    # Called on mouse wheel scroll action, zooms image in or out
    def _mousewheel_scroll(self, event):

        # A forced update seems to be required on Mac in order to not break scrollbars during
        # quick changes, e.g. on quick zoom changes via mousewheel.
        if platform.system() == 'Darwin':
            self._widget.update()

        # Zoom in
        if event.delta > 0:
            self._enlarge('in')

        # Zoom out
        else:
            self._enlarge('out')

    # Dialog window to save the plot as currently displayed
    def _save_file_box(self):

        mpl_canvas = self._figure_canvas.mpl_canvas
        filetypes = mpl_canvas.get_supported_filetypes().copy()
        default_filetype = mpl_canvas.get_default_filetype()

        default_filetype_name = filetypes[default_filetype]
        del filetypes[default_filetype]

        sorted_filetypes = list(six.iteritems(filetypes))
        sorted_filetypes.sort()
        sorted_filetypes.insert(0, (default_filetype, default_filetype_name))

        tk_filetypes = [(name, '*.%s' % ext) for (ext, name) in sorted_filetypes]

        initial_dir = cache.get_last_open_dir(if_exists=True)
        initial_file = mpl_canvas.get_default_filename()

        # We add an empty defaultextension because otherwise changing to any extension does not work properly
        filename = asksaveasfilename(title='Save the figure',
                                     parent=self._widget,
                                     filetypes=tk_filetypes,
                                     initialdir=initial_dir,
                                     initialfile=initial_file,
                                     defaultextension='')

        if filename == '' or filename == ():
            return

        cache.write_last_open_dir(os.path.dirname(filename))

        # Save the plot image
        self.save_image(filename)

    def close(self):

        self.series = None

        if self._toolbar is not None:
            self._toolbar = None

        if self._figure_canvas is not None:
            self._figure_canvas.destroy()

        super(PlotViewWindow, self).close()


class PlotOptionsWindow(Window):
    """ Window used to show and set numerous options for the plot in PlotViewWindow

    Allows control over Labels, Lines and Points, Error Bars, Colors and Axes Limits and Scaling.
    """

    def __init__(self, viewer, master, plot_view_window, initial_display=None):

        # Set initial necessary variables and do other required initialization procedures
        super(PlotOptionsWindow, self).__init__(viewer, withdrawn=True)

        # Set the title
        self.set_window_title('{0} - Plot Options'.format(self.get_window_title()))

        # Set PlotOptionsWindow to be transient, meaning it does not show up in the task bar and it stays
        # on top of its master window. This encourages the user to close this window when they are done
        # with it, otherwise it is easy to spawn many identical windows because numerous menu options of
        # PlotViewWindow lead to this PlotOptionsWindow.
        self._widget.transient(master)

        # Set the PlotViewWindow as an instance variable
        self._structure_window = plot_view_window

        # Initialize necessary instance variables used to store values in all tabs
        self._line_options = []
        self._point_options = []
        self._error_bar_options = []
        self._labels_options = {'x_label': None, 'y_label': None, 'title': None}
        self._color_options = {'plot_background': None, 'axes_background': None,
                               'border': None, 'ticks': None, 'grid': None}
        self._axes_options = {'axis_limits': None, 'axis_scale_x': None, 'axis_scale_y': None,
                              'min_x': None, 'max_x': None, 'min_y': None, 'max_y': None}

        # Box which will contain the Tabs
        self._tab_box = Frame(self._widget)
        self._tab_box.pack(side='top', fill='both', expand=1, padx=10, pady=10)

        # Add a tab bar, which allows switching of tabs
        self._tab_menu = TabBar(self._tab_box, init_name=initial_display)

        # Create and add all the tabs, each of which allows user to modify the plot
        self._add_labels_tab()
        self._add_lines_points_tab()
        self._add_error_bars_tab()
        self._add_colors_tab()
        self._add_axes_tab()

        self._tab_menu.show()

        # Add Apply and Close buttons for the whole window
        buttons_box = Frame(self._widget)
        buttons_box.pack(side='top', pady=(0, 10))
        bottom_buttons_params = {'bd': 1, 'width': 5, 'font': self.get_font(size=10)}

        plot = Button(buttons_box, text='Apply', command=self._apply, **bottom_buttons_params)
        plot.grid(row=0, column=0, padx=5)

        close = Button(buttons_box, text='Close', command=self.close, **bottom_buttons_params)
        close.grid(row=0, column=2, padx=5)

        # Set window size (maximum size of any tab for each dimension, the Apply/Close buttons, and padding)
        width, height = self._tab_menu.dimensions()
        width += 20
        height += buttons_box.winfo_reqheight() + 35
        self.set_window_geometry(width=width, height=height)
        self._center_window()

        # Update window to ensure it has taken its final form, then show it
        self._widget.update_idletasks()
        self.show_window()

    # Add tab and contents that control Labels options (text, visibility, font, size, style, color, )
    def _add_labels_tab(self):

        tab = Tab(self._tab_box, 'Labels')

        content_box = Frame(tab)
        content_box.pack(anchor='nw', pady=10)

        # Header
        label = Label(content_box, text='Show', font=self.get_font(10))
        label.grid(row=0, column=2, padx=2)

        label = Label(content_box, text='Font Family', font=self.get_font(10))
        label.grid(row=0, column=3)

        label = Label(content_box, text='Size (pt)', font=self.get_font(10))
        label.grid(row=0, column=4)

        label = Label(content_box, text='Style', font=self.get_font(10))
        label.grid(row=0, column=5, padx=(0, 5))

        label = Label(content_box, text='Color', font=self.get_font(10))
        label.grid(row=0, column=6)

        # Add buttons and menus to control settings
        for i, name in enumerate(['Title', 'X Label', 'Y Label', 'Tick Labels']):

            if name == 'Title':

                plot_label_mpl = self._structure_window.get_title(mpl_text=True)
                plot_label = self._structure_window.get_title(mpl_text=False)
                show_label = self._structure_window.is_title_shown()

            elif name in ('X Label', 'Y Label'):

                axis = name.split(' ')[0].lower()

                plot_label_mpl = self._structure_window.get_axis_label(axis, mpl_text=True)
                plot_label = self._structure_window.get_axis_label(axis, mpl_text=False)
                show_label = self._structure_window.is_label_shown(axis)

            else:

                plot_label_mpl = self._structure_window.get_tick_labels(axis='x', which='major', mpl_text=True)[0]
                plot_label = self._structure_window.get_tick_labels(axis='x', mpl_text=False)[0]
                show_label = self._structure_window.is_tick_labels_shown('both')

            option_menu_params = {'highlightthickness': 1, 'takefocus': 1}

            # Label text
            label = Label(content_box, text=name, font=self.get_font(10))
            label.grid(row=i+1, column=0, padx=5)

            if name != 'Tick Labels':
                entry_width = 30 if platform.system() == 'Windows' else 20
                entry = Entry(content_box, width=entry_width, bg='white')
                entry.insert(0, plot_label)
                entry.grid(row=i+1, column=1, ipady=3, padx=(0, 5))

            # Label visibility
            show = BooleanVar()
            show.set(show_label)

            show_button = Checkbutton(content_box, variable=show)
            show_button.grid(row=i+1, column=2)

            # Label font name
            fonts = sorted(set([font.name for font in mpl.font_manager.fontManager.ttflist]))
            font_name = StringVar()
            font_name.set(plot_label_mpl.get_name())

            font_name_params = ({'width': 20} if platform.system() == 'Windows' else
                                {'width': 15, 'font': self.get_font(9)})
            font_name_params.update(option_menu_params)

            option_menu = OptionMenu(content_box, font_name, *fonts)
            option_menu.config(**font_name_params)
            option_menu.grid(row=i+1, column=3, padx=(0, 5))

            # Label font size
            font_size = IntVar()
            font_size.set(int(plot_label_mpl.get_size()))

            option_menu = OptionMenu(content_box, font_size, *range(6, 30))
            option_menu.config(width=5, **option_menu_params)
            option_menu.grid(row=i+1, column=4, padx=(0, 5))

            # Bold font
            style_options = Frame(content_box)
            style_options.grid(row=i+1, column=5, padx=(0, 5))

            weight = plot_label_mpl.get_weight()
            current_bold = (weight == 'bold') or (isinstance(weight, int) and weight >= 700)
            bold = BooleanVar()
            bold.set(current_bold)

            bold_button = Checkbutton(style_options, text='Bold', variable=bold)
            bold_button.pack(side='left', padx=(0, 2))

            # Italic font
            italic = BooleanVar()
            italic.set(plot_label_mpl.get_style() == 'italic')

            italic_button = Checkbutton(style_options, text='Italic', variable=italic)
            italic_button.pack(side='left')

            # Label color
            current_colors = self._structure_window.get_colors()
            type_name = name.lower().replace(' ', '_')
            font_color = StringVar()
            font_color.set(current_colors[type_name])

            color_width = 10 if platform.system() == 'Windows' else 8
            color_picker = functools.partial(self._choose_color, type=type_name)
            color_button = Button(content_box, textvariable=font_color, width=color_width,
                                  font=self.get_font(size=9), command=color_picker)
            color_button.grid(row=i+1, column=6, padx=(0, 5))

            self._labels_options[type_name] = {'value': entry,
                                               'show': show,
                                               'font': font_name,
                                               'size': font_size,
                                               'bold': bold,
                                               'italic': italic,
                                               'color': font_color}

        self._tab_menu.add(tab)

    # Add tab and contents that control Lines and Points options for each data series (visibility, font, size,
    # style, color, frequency)
    def _add_lines_points_tab(self):

        tab = Tab(self._tab_box, 'Lines / Points')

        series_box = Frame(tab)
        series_box.pack(side='top', anchor='nw', padx=5, pady=15)

        option_menu_params = {'highlightthickness': 1, 'takefocus': 1}

        # Selected Data Series for which all the below options apply
        # (only one series can currently be plotted at a time)
        label = Label(series_box, text='Series: ', font=self.get_font(10))
        label.pack(side='left')

        series = IntVar()
        series.set(0)

        option_menu = OptionMenu(series_box, series, *range(0, len(self._structure_window.series)))
        option_menu.config(width=5, **option_menu_params)
        option_menu.pack(side='left')

        caption_box = Frame(tab)
        caption_box.pack(side='top', anchor='nw', padx=5, pady=(0, 10))

        # Frame that stores the contents for the Lines and Points options
        options_box = Frame(tab)
        options_box.pack(anchor='nw', padx=10, pady=(0, 15))

        # Header for Line Options
        label = Label(options_box, text='Show', font=self.get_font(10))
        label.grid(row=0, column=0)

        label = Label(options_box, text='Line Style', font=self.get_font(10))
        label.grid(row=0, column=1)

        label = Label(options_box, text='Line Width', font=self.get_font(10))
        label.grid(row=0, column=2)

        label = Label(options_box, text='Line Color', font=self.get_font(10))
        label.grid(row=0, column=3)

        # For each data series, show Line Options (currently this does not really work, as only one data
        # series can be plotted at a time. In the future, the contents of each iteration could be put into a
        # single frame and which frame is displayed controlled based on the selected series)
        for i in range(0, len(self._structure_window.series)):

            current_opts = self._structure_window.get_line_options(series.get())

            # Visibility
            current_show_line = self._structure_window.is_series_shown(series.get(), which='line')
            show_line = BooleanVar()
            show_line.set(current_show_line)

            show_button = Checkbutton(options_box, text='Line', variable=show_line)
            show_button.grid(row=1, column=0, padx=(0, 5))

            # Line style
            current_line_style = current_opts['style'] if current_show_line else 'solid'
            line_style = StringVar()
            line_style.set(current_line_style)

            option_menu = OptionMenu(options_box, line_style, *get_mpl_linestyles(include_none=False).values())
            option_menu.config(width=15, **option_menu_params)
            option_menu.grid(row=1, column=1, padx=(0, 5))

            # Line width
            line_width = IntVar()
            line_width.set(int(current_opts['width']))

            option_menu = OptionMenu(options_box, line_width, *range(1, 10))
            option_menu.config(width=5, **option_menu_params)
            option_menu.grid(row=1, column=2, padx=(0, 5))

            # Line color
            line_color = StringVar()
            line_color.set(current_opts['color'])

            color_picker = functools.partial(self._choose_color, type='line', index=i)
            color_button = Button(options_box, textvariable=line_color, width=10,
                                  font=self.get_font(size=9), command=color_picker)
            color_button.grid(row=1, column=3, padx=(0, 5))

            self._line_options.append({'show':  show_line,
                                       'style': line_style,
                                       'width': line_width,
                                       'color': line_color})

        # Header for Point Options
        label = Label(options_box, text='Show', font=self.get_font(10))
        label.grid(row=2, column=0, pady=(10, 0))

        label = Label(options_box, text='Point Style', font=self.get_font(10))
        label.grid(row=2, column=1, pady=(10, 0))

        label = Label(options_box, text='Point Width', font=self.get_font(10))
        label.grid(row=2, column=2, pady=(10, 0))

        label = Label(options_box, text='Point Color', font=self.get_font(10))
        label.grid(row=2, column=3, pady=(10, 0))

        label = Label(options_box, text='Frequency', font=self.get_font(10))
        label.grid(row=2, column=4, pady=(10, 0), padx=(0, 10))

        # For each data series, show Point Options (currently this does not really work, as only one data
        # series can be plotted at a time. In the future, the contents of each iteration could be put into a
        # single frame and which frame is displayed controlled based on the selected series)
        for i in range(0, len(self._structure_window.series)):

            current_opts = self._structure_window.get_point_options(series.get())

            # Visibility
            current_show_points = self._structure_window.is_series_shown(i, which='points')
            show_points = BooleanVar()
            show_points.set(current_show_points)

            show_button = Checkbutton(options_box, text='Points', variable=show_points)
            show_button.grid(row=3, column=0, padx=(0, 5))

            # Point style
            current_points_style = current_opts['style'] if current_show_points else 'point'
            points_style = StringVar()
            points_style.set(current_points_style)

            option_menu = OptionMenu(options_box, points_style, *get_mpl_markerstyles(include_none=False).values())
            option_menu.config(width=15, **option_menu_params)
            option_menu.grid(row=3, column=1, padx=(0, 5))

            # Point width
            point_widths = itertools.chain(range(1, 10), range(10, 22, 2))
            points_width = IntVar()
            points_width.set(int(current_opts['width']))

            option_menu = OptionMenu(options_box, points_width, *point_widths)
            option_menu.config(width=5, **option_menu_params)
            option_menu.grid(row=3, column=2, padx=(0, 5))

            # Point color
            points_color = StringVar()
            points_color.set(current_opts['color'])

            color_picker = functools.partial(self._choose_color, type='points', index=i)
            color_button = Button(options_box, textvariable=points_color, width=10,
                                  font=self.get_font(size=9), command=color_picker)
            color_button.grid(row=3, column=3, padx=(0, 5))

            if current_opts['frequency']:
                current_point_frequency = '1/{0}'.format(current_opts['frequency'])

            else:
                current_point_frequency = '1/1'

            # Point frequency
            point_periods = itertools.chain(range(1, 10), range(10, 50, 5), range(50, 525, 50))
            point_frequencies = ['1/{0}'.format(period) for period in point_periods]
            points_frequency = StringVar()
            points_frequency.set(current_point_frequency)

            option_menu = OptionMenu(options_box, points_frequency, *point_frequencies)
            option_menu.config(width=15, **option_menu_params)
            option_menu.grid(row=3, column=4, padx=(0, 5))

            self._point_options.append({'show':  show_points,
                                        'style': points_style,
                                        'width': points_width,
                                        'color': points_color,
                                        'frequency': points_frequency})

        self._tab_menu.add(tab)

    # Add tab and contents that control Error Bar options for each data series (visibility, size, style
    # and color)
    def _add_error_bars_tab(self):

        tab = Tab(self._tab_box, 'Error Bars')

        series_box = Frame(tab)
        series_box.pack(side='top', anchor='nw', padx=5, pady=15)

        # Selected Data Series for which all the below options apply
        # (only one series can currently be plotted at a time)
        label = Label(series_box, text='Series: ', font=self.get_font(10))
        label.pack(side='left')

        series = IntVar()
        series.set(0)

        option_menu_params = {'highlightthickness': 1, 'takefocus': 1}

        option_menu = OptionMenu(series_box, series, *range(0, len(self._structure_window.series)))
        option_menu.config(width=5, **option_menu_params)
        option_menu.pack(side='left')

        caption_box = Frame(tab)
        caption_box.pack(side='top', anchor='nw', padx=5, pady=(0, 10))

        # Frame that stores the contents for the Error Bar vertical and horizontal options
        options_box = Frame(tab)
        options_box.pack(anchor='nw', padx=10, pady=(0, 15))

        # Options for each error bar direction
        for i, which in enumerate(('vertical', 'horizontal')):

            current_opts = self._structure_window.get_error_bar_options(series.get(), which=which)
            no_error_bar = False

            # Set options to show if error bar does not exist
            if current_opts is None:

                no_error_bar = True
                current_opts = {'style': 'dotted',
                                'width': 1,
                                'color': '#000000'}

            # Header for Error Bar Options
            label = Label(options_box, text='Show', font=self.get_font(10))
            label.grid(row=i*2, column=0)

            label = Label(options_box, text='Line Style', font=self.get_font(10))
            label.grid(row=i*2, column=1)

            label = Label(options_box, text='Line Width', font=self.get_font(10))
            label.grid(row=i*2, column=2)

            label = Label(options_box, text='Line Color', font=self.get_font(10))
            label.grid(row=i*2, column=3)

            # For each data series, show Error Bar Options (currently this does not really work, as only one
            # data series can be plotted at a time. In the future, the contents of each iteration could be
            # put into a single frame and which frame is displayed controlled based on the selected series)
            for j in range(0, len(self._structure_window.series)):

                # Visibility
                current_show_error_bar = self._structure_window.is_error_bar_shown(series.get(), which=which)
                show_error_bar = BooleanVar()
                show_error_bar.set(current_show_error_bar)

                disabled_error_bar = {'state': 'disabled'} if no_error_bar else {}
                show_button = Checkbutton(options_box, text=which.capitalize(), variable=show_error_bar,
                                          **disabled_error_bar)
                show_button.grid(row=i*2+j+1, column=0, padx=(0, 5), pady=(0, 10))

                # Line style
                current_line_style = current_opts['style'] if current_show_error_bar else 'dotted'
                line_style = StringVar()
                line_style.set(current_line_style)

                option_menu = OptionMenu(options_box, line_style, *get_mpl_linestyles(include_none=False).values())
                option_menu.config(width=15, **option_menu_params)
                option_menu.grid(row=i*2+j+1, column=1, padx=(0, 5), pady=(0, 10))

                # Line width
                line_width = IntVar()
                line_width.set(int(current_opts['width']))

                option_menu = OptionMenu(options_box, line_width, *range(1, 10))
                option_menu.config(width=5, **option_menu_params)
                option_menu.grid(row=i*2+j+1, column=2, padx=(0, 5), pady=(0, 10))

                # Line color
                line_color = StringVar()
                line_color.set(current_opts['color'])

                color_picker = functools.partial(self._choose_color, type='error_bar_{0}'.format(which), index=j)
                color_button = Button(options_box, textvariable=line_color, width=10,
                                      font=self.get_font(size=9), command=color_picker)
                color_button.grid(row=i*2+j+1, column=3, padx=(0, 5), pady=(0, 10))

                self._error_bar_options.append({'vertical': {},
                                                'horizontal': {}})

                self._error_bar_options[j][which] = {'show':  show_error_bar,
                                                     'style': line_style,
                                                     'width': line_width,
                                                     'color': line_color}

        self._tab_menu.add(tab)

    # Add tab and contents that control Colors of plot elements, including plot and axis backgrounds,
    # as well as border, tick and grid line colors
    def _add_colors_tab(self):

        tab = Tab(self._tab_box, 'Colors')
        current_colors = self._structure_window.get_colors()

        content_box = Frame(tab)
        content_box.pack(anchor='nw', padx=5, pady=10)

        pady = 1 if platform.system() == 'Linux' else 2

        # Plot Background color
        label = Label(content_box, text='Plot Background:', font=self.get_font(10))
        label.grid(row=0, column=0, sticky='w', padx=(0, 10), pady=pady)

        plot_background_color = StringVar()
        plot_background_color.set(current_colors['plot_background'])

        color_picker = functools.partial(self._choose_color, type='plot_background')
        color_button = Button(content_box, textvariable=plot_background_color, width=10,
                              font=self.get_font(size=9), command=color_picker)
        color_button.grid(row=0, column=1, sticky='w', pady=pady)

        # Axes Background color
        label = Label(content_box, text='Axes Background:', font=self.get_font(10))
        label.grid(row=1, column=0, sticky='w', pady=pady)

        axes_background_color = StringVar()
        axes_background_color.set(current_colors['axes_background'])

        color_picker = functools.partial(self._choose_color, type='axes_background')
        color_button = Button(content_box, textvariable=axes_background_color, width=10,
                              font=self.get_font(size=9), command=color_picker)
        color_button.grid(row=1, column=1, sticky='w', pady=pady)

        # Plot Border color
        label = Label(content_box, text='Border:', font=self.get_font(10))
        label.grid(row=2, column=0, sticky='w', pady=pady)

        border_color = StringVar()
        border_color.set(current_colors['border'])

        color_picker = functools.partial(self._choose_color, type='border')
        color_button = Button(content_box, textvariable=border_color, width=10,
                              font=self.get_font(size=9), command=color_picker)
        color_button.grid(row=2, column=1, sticky='w', pady=pady)

        # Tick color
        label = Label(content_box, text='Ticks:', font=self.get_font(10))
        label.grid(row=3, column=0, sticky='w', pady=pady)

        tick_color = StringVar()
        tick_color.set(current_colors['ticks'])

        color_picker = functools.partial(self._choose_color, type='ticks')
        color_button = Button(content_box, textvariable=tick_color, width=10,
                              font=self.get_font(size=9), command=color_picker)
        color_button.grid(row=3, column=1, sticky='w', pady=pady)

        # Grid Line color
        label = Label(content_box, text='Grid Lines:', font=self.get_font(10))
        label.grid(row=4, column=0, sticky='w', pady=pady)

        grid_color = StringVar()
        grid_color.set(self._structure_window.get_grid_options('major')['color'])

        color_picker = functools.partial(self._choose_color, type='grid')
        color_button = Button(content_box, textvariable=grid_color, width=10,
                              font=self.get_font(size=9), command=color_picker)
        color_button.grid(row=4, column=1, sticky='w', pady=pady)

        # Label colors (directing to other tabs)
        label = Label(content_box, text='Labels:', font=self.get_font(10))
        label.grid(row=5, column=0, sticky='w', pady=pady)

        label = Label(content_box, text='See appropriate tab above.', font=self.get_font(10))
        label.grid(row=5, column=1, sticky='w', pady=pady)

        # Lines and Points colors (directing to other tabs)
        label = Label(content_box, text='Lines / Points:', font=self.get_font(10))
        label.grid(row=6, column=0, sticky='w', pady=(pady, 0))

        label = Label(content_box, text='See appropriate tab above.', font=self.get_font(10))
        label.grid(row=6, column=1, sticky='w', pady=(pady, 0))

        self._color_options = {'plot_background': plot_background_color,
                               'axes_background': axes_background_color,
                               'border': border_color,
                               'ticks': tick_color,
                               'grid': grid_color}

        self._tab_menu.add(tab)

    # Add tab and contents that control Axes limits and scaling.
    def _add_axes_tab(self):

        tab = Tab(self._tab_box, 'Axes')

        content_box = Frame(tab)
        content_box.pack(anchor='nw', padx=5, pady=10)

        text_params = {'font': self.get_font(10)}

        option_menus_box = Frame(content_box)
        option_menus_box.pack(side='top', anchor='nw')

        option_menu_params = {'highlightthickness': 1, 'takefocus': 1}

        # Automatic Axis Limits
        w = Label(option_menus_box, text='Axis Limits:', **text_params)
        w.grid(row=0, column=0, sticky='w')

        current_axis_limits = self._structure_window.menu_option('axis_limits')
        axis_limits = self._axes_options['axis_limits'] = StringVar()
        self._add_trace(axis_limits, 'w', self._update_limits_setting, default=current_axis_limits.capitalize())

        menu = OptionMenu(option_menus_box, axis_limits, *('Intelligent', 'Tight', 'Auto', 'Manual'))
        menu.config(width=15, **option_menu_params)
        menu.grid(row=0, column=1)

        # Manual Axis Limits
        manual_limits_box = Frame(content_box)
        manual_limits_box.pack(side='top', anchor='nw', pady=10)

        manual_limits = BooleanVar()
        self._add_trace(manual_limits, 'w', self._update_limits_setting, default=(current_axis_limits == 'manual'))

        b = Checkbutton(manual_limits_box, text='Manual Limits', variable=axis_limits,
                        onvalue='Manual', offvalue='Intelligent', **text_params)
        b.grid(row=0, column=0, pady=(0, 5))

        # Add Entries containing limits for each axis
        for i, axis in enumerate(('x', 'y')):

            w = Label(manual_limits_box, text='{0} Limits:'.format(axis.upper()), **text_params)
            w.grid(row=i+1, column=0)

            w = Label(manual_limits_box, text='Low', **text_params)
            w.grid(row=i+1, column=1, padx=(0, 5))

            x_lim, y_lim = self._structure_window.get_axis_limits()

            current_min = x_lim[0] if axis == 'x' else y_lim[0]
            current_max = x_lim[1] if axis == 'x' else y_lim[1]

            min_entry = Entry(manual_limits_box, width=15, bg='white')
            min_entry.grid(row=i+1, column=2, ipady=3, pady=3)
            min_entry.insert(0, current_min)
            self._axes_options['min_{0}'.format(axis)] = min_entry

            w = Label(manual_limits_box, text='High', **text_params)
            w.grid(row=i+1, column=3, padx=(10, 5))

            max_entry = Entry(manual_limits_box, width=15, bg='white')
            max_entry.grid(row=i+1, column=4, ipady=3, pady=3)
            max_entry.insert(0, current_max)
            self._axes_options['max_{0}'.format(axis)] = max_entry

        # Axis Scaling
        axis_scaling_box = Frame(content_box)
        axis_scaling_box.pack(side='top', anchor='nw')

        w = Label(axis_scaling_box, text='Axis Scaling ', **text_params)
        w.pack(side='top', anchor='w')

        axis_scales = ('Linear', 'Log', 'SymLog')
        x_scale, y_scale = self._structure_window.menu_option('axis_scaling').split('-')
        x_scale_idx = [item.lower() for item in axis_scales].index(x_scale)
        y_scale_idx = [item.lower() for item in axis_scales].index(y_scale)

        axis_scale_x = StringVar()
        axis_scale_x.set(axis_scales[x_scale_idx])

        axis_scale_y = StringVar()
        axis_scale_y.set(axis_scales[y_scale_idx])

        # X-axis scaling
        w = Label(axis_scaling_box, text='X', **text_params)
        w.pack(side='left', padx=(20, 3))

        m = OptionMenu(axis_scaling_box, axis_scale_x, *axis_scales)
        m.config(width=15, **option_menu_params)
        m.pack(side='left')

        # Y-axis scaling
        w = Label(axis_scaling_box, text='Y', **text_params)
        w.pack(side='left', padx=(10, 3))

        m = OptionMenu(axis_scaling_box, axis_scale_y, *axis_scales)
        m.config(width=15, **option_menu_params)
        m.pack(side='left')

        # Enable / disable entries for manual axis limits
        self._update_limits_setting()

        self._axes_options = {'axis_limits': axis_limits,
                              'min_x': self._axes_options['min_x'], 'max_x': self._axes_options['max_x'],
                              'min_y': self._axes_options['min_y'], 'max_y': self._axes_options['max_y'],
                              'axis_scale_x': axis_scale_x,
                              'axis_scale_y': axis_scale_y}

        self._tab_menu.add(tab)

    # Color selection for any color in this window.
    def _choose_color(self, type, index=None):

        if type in ('title', 'x_label', 'y_label', 'tick_labels'):

            label_option = self._labels_options[type]
            color = label_option['color']

        elif type == 'line':

            line_option = self._line_options[index]
            color = line_option['color']

        elif type == 'points':

            point_option = self._point_options[index]
            color = point_option['color']

        elif type in ('plot_background', 'axes_background', 'ticks', 'border', 'grid'):

            color = self._color_options[type]

        elif type in ('error_bar_vertical', 'error_bar_horizontal'):

            axis = type.split('_')[2]
            color = self._error_bar_options[index][axis]['color']

        else:
            raise ValueError('Unknown type for color choice: {0}'.format(type))

        # Get new label color
        rgb, hex = tkinter_colorchooser.askcolor(parent=self._widget, initialcolor=color.get())

        # Set new color
        if hex is not None:
            color.set(hex)

    # Applies all options in all tabs to the plot
    def _apply(self):

        # Freeze the plot display temporarily so it is not needlessly re-drawn multiple times
        self._structure_window.freeze_display()

        # Update / show / hide title and labels
        for label_name in ('title', 'x_label', 'y_label', 'tick_labels'):

            label_opts = self._labels_options[label_name]

            label_value = label_opts['value'].get()
            label_show = label_opts['show'].get()

            kwargs = {'fontname':   label_opts['font'].get(),
                      'fontweight': 'bold' if label_opts['bold'].get() else 'normal',
                      'fontstyle':  'italic' if label_opts['italic'].get() else 'normal',
                      'fontsize': label_opts['size'].get(),
                      'color':    label_opts['color'].get()}

            if label_name == 'title':
                self._structure_window.set_title(label_value, show=label_show, **kwargs)

            elif label_name in ('x_label', 'y_label'):
                axis = label_name.split('_')[0]
                self._structure_window.set_axis_label(axis, label_value, show=label_show, **kwargs)

            else:
                label_show = 'both' if label_show else 'none'
                self._structure_window.set_tick_label_options(axis='both', which='major',
                                                              show=label_show, **kwargs)

        # Update Lines and Points
        for series in range(0, len(self._line_options)):

            line_opts = self._line_options[series]
            point_opts = self._point_options[series]
            error_opts = self._error_bar_options[series]

            # Update Lines
            self._structure_window.set_line_options(series,
                                                    style=line_opts['style'].get(),
                                                    width=line_opts['width'].get(),
                                                    color=line_opts['color'].get(),
                                                    show=line_opts['show'].get())
            # Update Points
            self._structure_window.set_point_options(series,
                                                     style=point_opts['style'].get(),
                                                     width=point_opts['width'].get(),
                                                     color=point_opts['color'].get(),
                                                     frequency=Fraction(point_opts['frequency'].get()).denominator,
                                                     show=point_opts['show'].get())

            # Update Error Bars
            for which in 'vertical', 'horizontal':

                error_opts_axis = error_opts[which]
                self._structure_window.set_error_bar_options(series,
                                                             which=which,
                                                             style=error_opts_axis['style'].get(),
                                                             width=error_opts_axis['width'].get(),
                                                             color=error_opts_axis['color'].get(),
                                                             show=error_opts_axis['show'].get())

        # Update colors for Foreground, Background, Border and Ticks
        color_opts = self._color_options
        self._structure_window.set_colors(plot_background=color_opts['plot_background'].get(),
                                          axes_background=color_opts['axes_background'].get(),
                                          border=color_opts['border'].get(),
                                          ticks=color_opts['ticks'].get())

        # Update colors of Grid lines
        self._structure_window.set_grid_options(which='both', color=color_opts['grid'].get())

        # Update axis limits
        axes_opts = self._axes_options
        axis_limits = axes_opts['axis_limits'].get().lower()

        if axis_limits == 'manual':

            self._structure_window.set_axis_limits(x=(float(axes_opts['min_x'].get()), float(axes_opts['max_x'].get())),
                                                   y=(float(axes_opts['min_y'].get()), float(axes_opts['max_y'].get())))

        else:

            self._structure_window.set_axis_limits(auto=axis_limits)

        # Update axis scaling
        self._structure_window.set_axis_scaling(x=axes_opts['axis_scale_x'].get().lower(),
                                                y=axes_opts['axis_scale_y'].get().lower())

        # Thaw the plot display since it was frozen above
        self._structure_window.thaw_display()

    # Updates whether manual axis limits options are enabled or disabled in the Axes tab based on user
    # selection changes in that tab.
    def _update_limits_setting(self, *args):

        opts = self._axes_options

        # Determine necessary state
        if opts['axis_limits'].get().lower() == 'manual':
            state = 'normal'

        else:
            state = 'disabled'

        # Set necessary state
        for axis in ('x', 'y'):

            opts['min_{0}'.format(axis)].config(state=state)
            opts['max_{0}'.format(axis)].config(state=state)

    def close(self):

        self._structure_window = None
        super(PlotOptionsWindow, self).close()


class PlotColumnsWindow(Window):
    """ Window allowing a user to choose which table columns to plot."""

    def __init__(self, viewer, table_structure):

        # Set initial necessary variables and do other required initialization procedures
        super(PlotColumnsWindow, self).__init__(viewer, withdrawn=True)

        # Set the title
        self.set_window_title("{0} - Select Plot Columns from Table '{1}'".
                              format(self.get_window_title(), table_structure.id))

        # Initialize plot columns window variables
        self._structure = table_structure

        # Will lists RowNumber, followed by the names of all fields in the table
        self._field_listbox = None

        # Will contain an Entry for each axis (X, Y, X_Err, Y_Err in that order), where the entry contains
        # the name of the selected field
        self._axis_entries = [None, None, None, None]

        # Contains the index for the selected field (the index in field_listbox) for each axis. This index
        # is 1 bigger than the field's index in table_structure.data, because of RowNumber.
        self._axis_selections = [None, None, None, None]

        # Contains field indexes that are disabled in the field listbox (because said fields
        # cannot be plotted, i.e, they are not numeric or not 1 dimensional)
        self._disabled_indexes = []

        # Controls whether lines and points checkbuttons are checked (and subsequently which type will be
        # drawn for the plot), and whether special constants are ignored on the plot
        self._lines = BooleanVar()
        self._points = BooleanVar()
        self._mask_special = BooleanVar()

        # Draw the main window content
        self.draw_content()

        # Update window to ensure it has taken its final form, then show it
        self._widget.update_idletasks()
        self.show_window()

    # Draws the main content of the window
    def draw_content(self):

        left_side_box = Frame(self._widget)
        left_side_box.pack(side='left', fill='both', expand=1)

        # Listbox containing RowNumber and all the field names
        field_name_width = 30 if platform.system() == 'Windows' else 22
        self._field_listbox = Listbox(left_side_box, width=field_name_width, activestyle='none', bg='white',
                                      highlightthickness=0, bd=0)
        self._field_listbox.pack(side='left', fill='both', expand=1)

        field_scrollbar = Scrollbar(left_side_box, orient='vertical', command=self._field_listbox.yview)
        self._field_listbox.config(yscrollcommand=field_scrollbar.set)
        field_scrollbar.pack(side='right', fill='y')

        # Add RowNumber to listbox
        self._field_listbox.insert('end', ' ' + 'RowNumber')

        # Add field names to listbox
        for i, field in enumerate(self._structure.fields):
            self._field_listbox.insert('end', ' ' + field.meta_data.full_name(skip_parents=True).upper())

            # Disable non-numeric fields, fields with more than one dimension and fields with only one value
            is_flat_array = (len(field.shape) == 1) and (field.size > 1)
            is_numeric_array = np.issubdtype(field.dtype, np.floating) or is_pds_integer_data(data=field)
            is_date_array = field.meta_data.data_type().issubtype('datetime')

            if (not is_flat_array) or (not is_numeric_array and not is_date_array):
                self._disabled_indexes.append(i+1)
                self._field_listbox.itemconfig(i + 1, {'fg': '#999999', 'selectforeground': '#999999',
                                               'selectbackground': self._field_listbox.cget('background')})

        right_side_box = Frame(self._widget, bg=self.get_bg('gray'))
        right_side_box.pack(side='right', fill='both')

        instructions = Label(right_side_box, wraplength=250, bd=2, relief='groove', bg=self.get_bg('gray'),
              text="Click on a column name then select the corresponding plot axis or error bar")
        instructions.pack(side='top', padx=20, pady=10, ipadx=20, ipady=5)

        middle_box = Frame(right_side_box, bg=self.get_bg('gray'))
        middle_box.pack(side='top', padx=5)

        axis_options_box = Frame(middle_box, bg=self.get_bg('gray'))
        axis_options_box.pack(side='top')

        axis = Label(axis_options_box, bg=self.get_bg('gray'), text='Axis')
        axis.grid(row=0, column=0)

        column = Label(axis_options_box, bg=self.get_bg('gray'), text='Column name to plot')
        column.grid(row=0, column=1)

        # Entry and button that allows user to select a field as the data for each axis
        for i, axis_type in enumerate(['X', 'Y', 'X Error', 'Y Error']):

            choose_field = functools.partial(self._choose_field, i)

            button = Button(axis_options_box, text=axis_type, width=6, font=self.get_font(size=9),
                            bg=self.get_bg('gray'), highlightbackground=self.get_bg('gray'),
                            command=choose_field)
            button.grid(row=i+1, column=0)

            entry = Entry(axis_options_box, width=field_name_width, state='readonly', relief='sunken', bd=1,
                          readonlybackground='white', highlightthickness=0, takefocus=0)
            entry.grid(row=i+1, column=1, padx=(5, 0), ipady=3)

            self._axis_entries[i] = entry

        # Determine whether structure contains masked data. For such data, scatter plots are usually
        # better than line plots.
        has_masked = any([np.ma.is_masked(field) for field in self._structure.as_masked().fields])
        self._lines.set(not has_masked)
        self._points.set(has_masked)
        self._mask_special.set(True)

        # Lines and Points checkbuttons
        checkbutton_box = Frame(middle_box)
        checkbutton_box.pack(side='top', pady=(10, 0))

        line_plot = Checkbutton(checkbutton_box, text='Lines', bg=self.get_bg('gray'),
                                variable=self._lines, onvalue=True, offvalue=False)
        line_plot.pack(side='left')

        point_plot = Checkbutton(checkbutton_box, text='Points', bg=self.get_bg('gray'),
                                 variable=self._points, onvalue=True, offvalue=False)
        point_plot.pack(side='left')

        if has_masked:
            mask_special = Checkbutton(middle_box, text='Ignore special constants and nulls',
                                       bg=self.get_bg('gray'), variable=self._mask_special,
                                       onvalue=True, offvalue=False)
            mask_special.pack(side='top')

        # add_plot = Checkbutton(middle_box, text='Add curve to the current graph', bg=self.get_bg('gray'))
        # add_plot.pack(side='top')

        # Plot, Clear and Close buttons
        bottom_box = Frame(right_side_box, relief='groove', bd=2, bg=self.get_bg('gray'))
        bottom_box.pack(side='bottom', fill='x', padx=10, pady=(5, 2))

        buttons_box = Frame(bottom_box, bg=self.get_bg('gray'))
        buttons_box.pack()
        bottom_buttons_params = {'width': 5, 'font': self.get_font(size=10),
                                 'bg': self.get_bg('gray'), 'highlightbackground': self.get_bg('gray')}

        plot = Button(buttons_box, text='Plot', command=self._plot, **bottom_buttons_params)
        plot.grid(row=0, column=0, padx=5)

        clear = Button(buttons_box, text='Clear', command=self._clear, **bottom_buttons_params)
        clear.grid(row=0, column=1, padx=5)

        close = Button(buttons_box, text='Close', command=self.close, **bottom_buttons_params)
        close.grid(row=0, column=2, padx=5)

    # Plot the selected data, and close this window
    def _plot(self):

        # Do nothing if no axes to plot are selected
        if None in self._axis_selections[0:2]:
            return

        # Ensure at least one of Lines or Points is checked, otherwise default to Lines
        line_plot = self._lines.get()
        point_plot = self._points.get()
        mask_special = self._mask_special.get()

        if (not line_plot) and (not point_plot):
            line_plot = True

        # Plot selected data
        plot_window = PlotViewWindow(self._viewer)
        plot_window.load_table(self._structure,
                               self._axis_selections,
                               lines=line_plot,
                               points=point_plot,
                               mask_special=mask_special)

        self.close()

    # Choose a field for a given axis (X, Y, X_Err, Y_err), where the axis is specified as an index
    def _choose_field(self, axis_index):

        # Do nothing if no field name is selected
        if len(self._field_listbox.curselection()) == 0:
            return

        # Do nothing for disabled fields
        listbox_index = self._field_listbox.index('active')

        if listbox_index in self._disabled_indexes:
            return

        # Add field name to axis' entry for display
        axis_entry = self._axis_entries[axis_index]

        axis_entry.config(state='normal')
        axis_entry.delete(0, 'end')
        axis_entry.insert(0, self._field_listbox.get('active').strip())
        axis_entry.config(state='readonly')

        # Adjust index to account for RowNumber not actually existing as a field
        if listbox_index == 0:
            listbox_index = 'row'

        else:
            listbox_index -= 1

        # Select field for the given axis
        self._axis_selections[axis_index] = listbox_index

    # Clears all field selections
    def _clear(self):

        self._axis_selections = [None, None, None, None]

        for axis_entry in self._axis_entries:

            axis_entry.config(state='normal')
            axis_entry.delete(0, 'end')
            axis_entry.config(state='readonly')

    def close(self):

        self._structure = None
        super(PlotColumnsWindow, self).close()


class _Series(object):
    """ Helper class containing data about the series being displayed """

    def __init__(self, table_structure, axis_selections):

        self.structure = table_structure
        self.axis_selections = axis_selections

        self.plot_line = None
        self.error_caps = None
        self.error_lines = None

    def add_plot(self, plot_line, error_caps, error_lines):

        # MPL Line2D that is shown on the plot as line and/or points
        self.plot_line = plot_line

        # List of MPL Line2Ds that are the caps of error bars
        self.error_caps = {
                           'vertical': [cap for cap in error_caps if cap.get_marker() == '_'],
                           'horizontal': [cap for cap in error_caps if cap.get_marker() == '|']
                          }

        # MPL LineCollection that are the lines of error bars. (This is currently MPL implementation dependent
        # in that it relies on the order error lines are added in MPL's `errorbar` call. There is likely
        # a more complicated method of using error_lines[0].get_paths().vertices to produce an implementation
        # independent result; however care would need to be taken for cases where the error bars are extremely
        # small.)
        self.error_lines = {
                            'vertical': error_lines[-1] if (self.axis_selections[3] is not None) else None,
                            'horizontal': error_lines[0] if (self.axis_selections[2] is not None) else None
                           }

        # 'vertical': next((col for col in error_lines
        #                   if col.get_paths()[0].vertices[0][0] == col.get_paths()[0].vertices[1][0]), None),
        # 'horizontal': next((col for col in error_lines
        #                     if col.get_paths()[0].vertices[0][1] == col.get_paths()[0].vertices[1][1]), None),

    # Obtains the data for the series and the given axis. Valid options for axis are x|y|x_err|y_err.
    def data(self, axis, masked=None):

        axis_selection = self._axis_to_axis_selection(axis)

        # Select nothing if there is no axis specified
        if axis_selection is None:
            data = None

        # Select the RowNumber axis
        elif axis_selection == 'row':

            num_rows = len(self.structure.fields[0])
            data = np.arange(num_rows)

        # Select an axis from the fields in the table
        else:

            data = self.structure.fields[axis_selection]

            if data.meta_data.data_type().issubtype('datetime'):
                data = data_type_convert_dates(data)

        # "Mask" data if requested
        if masked and (data is not None):

            mask = self._get_normalized_mask()
            if mask is not np.ma.nomask:
                data = data[np.invert(mask)]

        return data

    # Obtains the data for the series and the given axis. Valid options for axis are x|y|x_err|y_err.
    def meta_data(self, axis):

        axis_selection = self._axis_to_axis_selection(axis)

        if axis_selection is None:
            meta_data = None

        elif axis_selection == 'row':
            meta_data = Meta_Field({'name': 'Row Number',
                                    'data_type': 'object'})

        else:

            meta_data = self.data(axis, masked=False).meta_data

        return meta_data

    # Obtains a label for the series and the given axis. Valid options for axis are x|y|x_err|y_err.
    def label(self, axis):

        name = self.meta_data(axis)['name']
        unit = self.meta_data(axis).get('unit', None)

        label = name

        if unit is not None:
            label = '{0} ({1})'.format(label, unit)

        return label

    # Transforms axis from x|y|x_err|y_err to an axis selection
    # (either index of a table field, the string 'row' or None)
    def _axis_to_axis_selection(self, axis):

        axis_idx = {'x': 0,
                    'y': 1,
                    'x_err': 2,
                    'y_err': 3,
                    }[axis]

        axis_selection = self.axis_selections[axis_idx]

        return axis_selection

    # Obtains a mask which is set to True in any place where any of the axis selections are masked out
    def _get_normalized_mask(self):

        all_fields = self.structure.as_masked().fields
        fields = [all_fields[axis] for axis in self.axis_selections
                  if isinstance(axis, int)]

        mask = np.ma.nomask

        for field in fields:
            mask = np.ma.mask_or(field.mask, mask, copy=False, shrink=True)

        return mask


def open_plot(viewer, table_structure, axis_selections, lines=True, points=False, mask_special=False):
    """ Open a plot view for fields from a TableStructure.

    Parameters
    ----------
    viewer : PDS4Viewer
        An instance of PDS4Viewer.
    table_structure : TableStructure
        Table structure from which the fields to plot are taken.
    axis_selections : list[int str, unicode or None]
        A four valued list, which specifies the table fields to use for x,y,x_err,y_err by indicating their
        field index in *table_structure*. To plot against row number, the string 'row' may be used instead
        of an index. x_err and/or y_err may use None to skip error bars.
    lines : bool, optional
        When True, lines will connect individual data points. Defaults to True.
    points : bool, optional
        When True, markers will be shown on individual data points. Defaults to False.
    mask_special : bool, optional
        When True, special constants and null values are removed from the data to be plotted.
        Defaults to False.

    Returns
    -------
    PlotViewWindow
        The window instance for plot view.
    """

    plot_window = PlotViewWindow(viewer)
    plot_window.load_table(table_structure, axis_selections,
                           lines=lines, points=points, mask_special=mask_special)

    return plot_window


def open_plot_column_select(viewer, table_structure):
    """ Open a window that allows selection of fields to plot from a TableStructure.

    Parameters
    ----------
    viewer : PDS4Viewer
        An instance of PDS4Viewer.
    table_structure : TableStructure
        Table structure from which the fields available to plot are taken.

    Returns
    -------
    PlotColumnsWindow
        The window instance for the plot column selection window.
    """

    plot_columns_window = PlotColumnsWindow(viewer, table_structure)

    return plot_columns_window
