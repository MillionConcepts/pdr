from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import math
import os
import weakref
import platform
import warnings
from fractions import Fraction

import numpy as np
import matplotlib as mpl
from matplotlib.figure import Figure

from . import cache
from .core import Window, DataViewWindow
from .mpl import FigureCanvas, MPLCompat

from ..utils.compat import OrderedDict
from ..utils.helpers import finite_min_max, is_array_like
from ..utils.exceptions import PDS4StandardsException
from ..utils.logging import logger_init

from ..extern.zscale import zscale
from ..extern import six
from ..extern.six.moves.tkinter import (Frame, Scrollbar, Label, Entry, Scale, Button,
                                        Radiobutton, StringVar, BooleanVar, DoubleVar, IntVar)
from ..extern.six.moves.tkinter_tkfiledialog import asksaveasfilename

# Initialize the logger
logger = logger_init()

#################################


class ImageViewWindow(DataViewWindow):
    """ Window that displays Array_2D and Array_3D PDS4 data structures as an image.

    This window will display image data. After creating it, you should use the load_array() method to load
    the array that it needs to display.
    """

    def __init__(self, viewer):

        # Create basic data view window
        super(ImageViewWindow, self).__init__(viewer)

        # Pack the display frame, which contains the scrollbars and the scrollable canvas
        self._display_frame.pack(side='left', anchor='nw', expand=1, fill='both')

        # Create the frame which can/will contain the colorbar
        self._colorbar_frame = Frame(self._static_canvas)

        # Control variable for `freeze_display` and `thaw_display`. Image will not be updated on screen
        # when counter is greater than 1.
        self._freeze_display_counter = 0

        # Will be set to an instance of FigureCanvas (containing the main image/slice being displayed)
        self._figure_canvas = None

        # Will be set to an instance of MPL's AxesImage
        self._image = None

        # Will be set to an instance of Colorbar
        self._colorbar = None

        # Will be set to an instance of MPL's toolbar for TK
        self._toolbar = None

        # Will be set to the masked data array for the structure if it has masked values
        # (used to minimize operations)
        self._masked_data = None

        # Will be set to the data for the current slice/image being shown
        self._slice_data = None

        # Contains sub-widgets of the header
        self._header_widgets = {'x': None, 'y': None, 'value': None, 'frame': None}

        # Menu option variables. These are TKinter type wrappers around standard Python variables. The
        # advantage is that you can use trace(func) on them, to automatically call func whenever one of
        # these variables is changed
        draw_slice = lambda * args: self._draw_slice()
        update_colorbar = lambda *args: self._update_colorbar(full_redraw=True)
        update_invert_axis = lambda *args: self._update_invert_axis(has_default_orientation=False)
        update_tick_labels = lambda *args: self._update_tick_labels(for_save=False)

        menu_options = [
            {'name': 'show_colorbar',    'type': BooleanVar(), 'default': True,         'trace': self.toggle_colorbar},
            {'name': 'colorbar_orient',  'type': StringVar(),  'default': 'horizontal', 'trace': update_colorbar},
            {'name': 'colormap',         'type': StringVar(),  'default': 'gray',       'trace': self._update_colormap},
            {'name': 'invert_colormap',  'type': BooleanVar(), 'default': False,        'trace': self._update_colormap},
            {'name': 'show_border',      'type': BooleanVar(), 'default': False,        'trace': update_tick_labels},
            {'name': 'show_axis_ticks',  'type': StringVar(),  'default': 'none',       'trace': update_tick_labels},
            {'name': 'scale',            'type': StringVar(),  'default': 'linear',     'trace': self._update_scale},
            {'name': 'scale_limits',     'type': StringVar(),  'default': 'min max',    'trace': self._update_scale},
            {'name': 'mask_special',     'type': BooleanVar(), 'default': True,         'trace': draw_slice},
            {'name': 'zoom_level',       'type': StringVar(),  'default': '1,1',        'trace': self._update_zoom},
            {'name': 'mode',             'type': StringVar(),  'default': 'image',      'trace': self._update_mode},
            {'name': 'invert_axis',      'type': StringVar(),  'default': 'none',       'trace': update_invert_axis},
            {'name': 'rotation_angle',   'type': DoubleVar(),  'default': 0,            'trace': self._update_rotation},
            {'name': 'orientation',      'type': StringVar(),  'default': 'display',    'trace': self._update_orientation},
            {'name': 'pan',              'type': BooleanVar(), 'default': False,        'trace': self._pan},
            {'name': 'axis_limits_to_rectangle', 'type': BooleanVar(), 'default': False, 'trace': self._axis_limits_to_rectangle}
        ]

        for option in menu_options:

            var = option['type']
            self._menu_options[option['name']] = var

            self._add_trace(var, 'w', option['trace'], option['default'])

    @property
    def settings(self):

        settings = super(ImageViewWindow, self).settings
        settings['axes'] = settings['axes'].copy()

        return settings

    @property
    def data(self):

        has_special = 'Special_Constants' in self.meta_data
        mask_special = self.menu_option('mask_special')
        not_rgb = not self.settings['is_rgb']

        if has_special and mask_special and not_rgb:

            if self._masked_data is None:
                self._masked_data = self.structure.as_masked().data

            data = self._masked_data

        else:
            data = self.structure.data

        return data

    # Loads the image array structure into this window and displays it for the user
    def load_array(self, array_structure):

        # Set a title for the window
        self.set_window_title("{0} - Image '{1}'".format(self.get_window_title(), array_structure.id))

        # Set necessary instance variables for this DataViewWindow
        self.structure = array_structure
        self.meta_data = array_structure.meta_data
        self._settings = {'dpi': 80., 'axes': _AxesProperties(), 'selected_axis': 0,
                          'is_rgb': False, 'rgb_bands': (None, None, None)}

        # Create the header
        self._draw_header()

        # Add vertical scrollbar for the image
        self._vert_scrollbar = Scrollbar(self._display_frame, orient='vertical', command=self._vertical_scroll)
        self._vert_scrollbar.set(0, 1)
        self._vert_scrollbar.pack(side='right', fill='y')

        # Add horizontal scrollbar for the image
        self._horz_scrollbar = Scrollbar(self._display_frame, orient='horizontal', command=self._horizontal_scroll)
        self._horz_scrollbar.set(0, 1)
        self._horz_scrollbar.pack(side='bottom', fill='x')

        # Pack the static canvas, which contains the scrollable canvas and the colorbar
        self._static_canvas.config(background='white')
        self._static_canvas.pack(expand=1, fill='both')

        # Pack the scrollable canvas, which contains the image itself
        self._scrollable_canvas.config(background='white')
        self._scrollable_canvas.pack(side='top', expand=1, fill='both')

        # Update idletasks such that the window takes on its real size (initial draw looks smoother this way)
        self._widget.update_idletasks()

        # Set horizontal and vertical axes for each slice
        self.set_slice_axes()

        # Special settings initialization for RGB images
        color_axis = self._settings['axes'].find('type', 'color')
        if color_axis is not None:

            self._settings['is_rgb'] = True

            # Set RGB bands for color images
            self.set_rgb_bands()

            # Disable default showing of colorbar for RGB images (since works only for monochrome images)
            self._menu_options['show_colorbar'].set(False)

            # Set colormap to RGB by default
            self.set_colormap('RGB')

        # Set the default selected axis and slice
        self.select_slice()

        # Draw the slice/image on the screen
        self._draw_slice()

        # Default to array-mode for extreme aspect ratios (i.e. do not respect image aspect ratio)
        self.set_mode()

        # Add notify event for window resizing
        self._display_frame.bind('<Configure>', self._window_resize)

        # Add notify event for scroll wheel (used to zoom via scroll wheel)
        self._bind_scroll_event(self._mousewheel_scroll)

        # Add notify event for mouse pointer exiting _scrollable_canvas (used to display pixel values
        # under the mouse pointer)
        self._figure_canvas.tk_widget.bind('<Leave>', self._update_mouse_pixel_value)

        # Add notify event for mouse motion (used to display pixel values under pointer)
        self._figure_canvas.mpl_canvas.mpl_connect('motion_notify_event', self._update_mouse_pixel_value)

        self._add_menus()
        self._data_open = True

    # Get zoom level, as (zoom_width, zoom_height)
    def get_zoom_level(self):

        zoom = self.menu_option('zoom_level')

        fractions = map(Fraction, zoom.split(','))
        zoom_level = map(float, fractions)

        return list(zoom_level)

    # Sets colormap on currently displayed image
    def set_colormap(self, colormap):
        self._menu_options['colormap'].set(colormap)

    # Sets the RGB bands for the color axis, if image has one (e.g. if color axis has 5 bands, this
    # determines which 3 bands will be used for the RGB image). Each color parameter must be set an integer
    # indice of the color axis (1-based indexing, as per the display dictionary) or None. None will default
    # to display settings values.
    def set_rgb_bands(self, red=None, green=None, blue=None):

        # Raise error if image is not RGB (i.e., has no color axis)
        if not self._settings['is_rgb']:
            raise TypeError('Unable to set RGB bands for an image without a color axis.')

        display_settings = self.meta_data.display_settings
        color_settings = display_settings['Color_Display_Settings']

        if red is None:
            red = color_settings['red_channel_band']

        if green is None:
            green = color_settings['green_channel_band']

        if blue is None:
            blue = color_settings['blue_channel_band']

        # Attempt to correct zero-based (or less) indexing
        min_index = min(red, green, blue)
        if min_index < 0:
            adjust_index = 1 - min_index
            red += adjust_index
            green += adjust_index
            blue += adjust_index
            self._issue_warning('Found non-compliant (non-1) based indexing in Color Settings. '
                                'Displayed image may not be correct.', show=False)

        # Save the newly input values
        self._settings['rgb_bands'] = (red, green, blue)

        # Reload the slice to reflect the changes
        if self._data_open:
            self._draw_slice()

    # Controls scaling for the currently displayed slice. scale can have values linear|log|squared|square root,
    # and limits can have values min max|zscale, or a tuple (min, max). To keep existing values use None.
    def set_scale(self, scale=None, limits=None):

        # Freeze the display temporarily so image is not needlessly re-drawn multiple times
        self.freeze_display()

        if scale is not None:
            self._menu_options['scale'].set(scale)

        if limits is not None:

            # Convert to storable input (which has format 'limit_low,limit_high' as a string)
            if is_array_like(limits):
                limits = ','.join([str(level) for level in limits])

            self._menu_options['scale_limits'].set(limits)

        # Thaw the display
        self.thaw_display()

    # Zooms in on the initial image dimensions by zoom_level. Can be tuple (zoom_width, zoom_height) to
    # specify an aspect ratio. (e.g. a zoom_level of 2 will double the dimensions of the original image).
    def set_zoom(self, zoom_level, mode=None):

        # Accept single-value zoom-levels (i.e. aspect ratio of 1)
        if isinstance(zoom_level, (int, float)):
            zoom_level = [zoom_level] * 2

        # Ensure *zoom_level* and mode are compatible
        new_mode = self.menu_option('mode') if (mode is None) else mode
        if (new_mode == 'image') and (zoom_level[0] != zoom_level[1]):
            raise ValueError('Zoom conflict: mode is set to image, but zoom aspect ratio is not 1.')

        # Freeze the display temporarily so image is not needlessly re-drawn multiple times
        self.freeze_display()

        # Update mode (if requested)
        if mode is not None:
            self.set_mode(mode)

        # Convert to storable input (which has format 'zoom_width,zoom_height' as a string)
        zoom_level = '{0},{1}'.format(*zoom_level)

        # Set zoom
        self._menu_options['zoom_level'].set(zoom_level)

        # Thaw the display, since it was frozen above
        self.thaw_display()

    # Rotates currently displayed slice to rotation_angle from initial orientation, in degrees. Note that
    # rotation angle must be evenly divisible by 90.
    def set_rotation(self, rotation_angle):
        self._menu_options['rotation_angle'].set(rotation_angle)

    # Sets the default orientation, from which the rotation angle and axis inversions begin. Valid options
    # are display|storage, indicating either according to display dictionary or according to the storage
    # order
    def set_orientation(self, orientation):
        self._menu_options['orientation'].set(orientation)

    # Set the current mode, one of image|array|manual. In image mode, we update aspect ratio to match the original
    # image (by zooming to level 1) if it does not already match. In array mode, we simply fit the image to screen
    # without preserving the aspect ratio. In manual mode, the set zoom level and aspect ratio are preserved except
    # when explicitly changed.
    def set_mode(self, mode=None):

        # Default to array-mode for extreme aspect ratios (i.e. do not respect image aspect ratio)
        is_generic_array = not any(item in self.structure.type for item in ('Image', 'Map', 'Movie'))
        if is_generic_array and (mode is None):

            axes = self._settings['axes']
            vertical_shape = axes.find('type', 'vertical')['length']
            horizontal_shape = axes.find('type', 'horizontal')['length']
            aspect_ratio = horizontal_shape / vertical_shape

            if (aspect_ratio > 20) or (aspect_ratio < 1 / 20):
                mode = 'array'

        # When mode is not explicitly set, or aspect ratio is not extreme, default to image mode
        if mode is None:
            mode = 'image'

        # Update whether aspect is constrained to match original image's
        self._menu_options['mode'].set(mode)

    # Controls axes display for current image. show_axis and invert_axis can have values x|y|both|none.
    # show_border is a boolean that controls whether a border is displayed around image. To keep existing
    # values use None.
    def set_axes_display(self, show_axis=None, invert_axis=None, show_border=None):

        if show_axis is not None:
            self._menu_options['show_axis_ticks'].set(show_axis)

        if invert_axis is not None:
            self._menu_options['invert_axis'].set(invert_axis)

        if show_border is not None:
            self._menu_options['show_border'].set(show_border)

    # Zooms the image, via resampling, to fit the current window
    def zoom_to_fit(self):

        # Having correct figure dimensions is needed to determine the area to fit into
        self._update_figure_dimensions()

        # Available viewing area for image
        display_width, display_height = self._display_dimensions()

        # Unzoomed size of the image
        image_width, image_height = self._image_dimensions(zoom_level=1)

        # Obtain the mode and old aspect ratio
        mode = self.menu_option('mode')
        old_zoom = self.get_zoom_level()
        old_aspect = min(old_zoom) / max(old_zoom)

        # Determine the maximum zoom level possible before image will not fit in frame
        # (we run this twice to determine an accurate margin dimension, which is dependent on being
        #  close to the right zoom level)
        zoom_level = 1

        for i in range(0, 2):
            image_dimensions = self._image_dimensions(zoom_level=zoom_level)
            margin_width, margin_height = self._margin_dimensions(image_dimensions=image_dimensions)

            fig_size_div = ((display_width - margin_width) / image_width,
                            (display_height - margin_height) / image_height)

            # Maintain aspect ratio identical to original image in image-mode
            if mode == 'image':
                zoom_level = min(fig_size_div)

            # Ignore aspect ratio of original image in array-mode
            elif mode == 'array':
                zoom_level = fig_size_div

            # Keep current aspect ratio for manual-mode
            else:

                if old_zoom[0] < old_zoom[1]:
                    zoom_level = [max(fig_size_div)*old_aspect, max(fig_size_div)]
                else:
                    zoom_level = [min(fig_size_div), min(fig_size_div)*old_aspect]

        self._zoom(zoom_level=zoom_level)

    # Sets the axes to be used for each slice. The values must be the integer sequence_number of the Axis_Array, or
    # None, which defaults to the display settings values. For color and time axis, 'none' is also acceptable and
    # forces that axis to be treated as a non-specified.
    def set_slice_axes(self, horizontal_axis=None, vertical_axis=None, color_axis=None, time_axis=None):

        meta_data = self.meta_data
        display_settings = meta_data.display_settings
        invalid_display_settings = (not display_settings) or (not display_settings.valid)
        axis_arrays = meta_data.get_axis_arrays(sort=True)

        # In case of non-existent or invalid DisplaySettings
        if invalid_display_settings and (horizontal_axis is None or vertical_axis is None):

            # For 4D+ arrays we can do nothing other than show an error, as we do not know and
            # cannot even guess which axes are X and Y
            if len(axis_arrays) > 3:
                raise PDS4StandardsException('No valid/supported Display Settings found. Unable to show '
                                             'images with more than 3 axes.')

            self._issue_warning('No valid/supported Display Settings found. Displayed image may '
                                'not be correct.', show=True)

            self._menu_options['orientation'].set('storage')

            # For a 3D array, we try to guess that the correct axes are, ([frame], vertical, horizontal)
            three_d_adjust = 0
            if len(axis_arrays) == 3:
                three_d_adjust = 1

            # The default to [vertical, horizontal] is done due to row-major order specification of the
            # PDS4 standard. This way, a table and an image (displayed in storage order) viewed together
            # line up.
            if vertical_axis is None:
                vertical_axis = 1 + three_d_adjust

            if horizontal_axis is None:
                horizontal_axis = 2 + three_d_adjust

        # Determine horizontal and vertical axes from Display Dictionary if necessary
        elif display_settings.valid:

            # Find names of all present axes in Display Dictionary
            display_direction = display_settings['Display_Direction']
            color_settings = display_settings.get('Color_Display_Settings')
            movie_settings = display_settings.get('Movie_Display_Settings')

            if horizontal_axis is None:
                horizontal_name = display_direction['horizontal_display_axis']
                horizontal_axis = meta_data.get_axis_array(axis_name=horizontal_name)['sequence_number']

            if vertical_axis is None:
                vertical_name = display_direction['vertical_display_axis']
                vertical_axis = meta_data.get_axis_array(axis_name=vertical_name)['sequence_number']

            if (color_axis is None) and (color_settings is not None):
                color_name = color_settings['color_display_axis']
                color_axis = meta_data.get_axis_array(axis_name=color_name)['sequence_number']

            if (time_axis is None) and (movie_settings is not None):
                time_name = movie_settings['time_display_axis']
                time_axis = meta_data.get_axis_array(axis_name=time_name)['sequence_number']

            # For 2D arrays, if storage orientation is selected, then we ensure that those axes are in
            # storage order [vertical, horizontal]. See above row-major order specification note for
            # explanation. For 3D arrays we do nothing because doing so is effectively not possible
            # while also displaying the correct image.
            if (self.menu_option('orientation') == 'storage') and (len(axis_arrays) == 2):
                saved_axes = (vertical_axis, horizontal_axis)
                vertical_axis = min(saved_axes)
                horizontal_axis = max(saved_axes)

        # Force color and/or time axis to none if requested
        if color_axis == 'none':
            color_axis = None

        if time_axis == 'none':
            time_axis = None

        # Obtain sequence number corresponding to each axis
        type_to_number = {
            'horizontal': horizontal_axis,
            'vertical': vertical_axis,
            'color': color_axis,
            'time': time_axis
        }

        # Add axes to the settings['axes'] helper object (_AxesProperties). Consists of essentially a list
        # with a dictionary for each axis present in the array, indicating the name, type, sequence number,
        # selected slice and length of the axis
        axes = _AxesProperties()

        for axis in axis_arrays:

            name = axis['axis_name']
            length = axis['elements']
            sequence = axis['sequence_number']

            type_ = None
            slice_ = 0

            for type, seq_number in six.iteritems(type_to_number):

                if seq_number == sequence:
                    type_ = type
                    if type != 'time':
                        slice_ = slice(None)

            axes.add_axis(name, type_, sequence, slice_, length)

        # Ensure that valid axes were found
        error = "Unable to set slice axes, an Axis_Array with sequence_number '{0}' does not exist."

        if axes.find('type', 'horizontal') is None:
            raise IndexError(error.format(horizontal_axis))

        elif axes.find('type', 'vertical') is None:
            raise IndexError(error.format(vertical_axis))

        # Save the new slice axes
        self._settings['axes'] = axes

        # Reload the slice to reflect the changes
        if self._data_open:
            self._draw_slice()

    # Selects a new slice to display and updates the currently displayed slice/image. To adjust the
    # shown slice for a 3D image, having axes (x, y, z), you need to specify both which axis (for
    # example x, which could correspond to time) and which slice of x (for example 2) you want to
    # display. The axis variable is an integer specifying the sequence_number of the Axis_Array,
    # in other words it specifies for which axis the index variable is used; None defaults to the
    # currently selected axis. The index variable is either an integer specifying which slice will
    # be shown for the axis, or the string 'next' or 'previous'; None defaults to the currently
    # selected slice. When save_index is True, the selected axis will be updated to default to
    # the specified axis.
    def select_slice(self, axis=None, index=None, save_axis=True):

        settings = self._settings
        cmap = self.menu_option('colormap')
        axes = settings['axes']

        # Skip any action if there are only two axes (horizontal and vertical), or if
        # there are only three axes in RGB colormap mode
        if len(axes) == 2 or (len(axes) == 3 and cmap == 'RGB'):
            return

        # Deafault to a valid selected axis
        if axis is None:

            # Try the currently selected axis
            axis = settings['selected_axis']

            # Try the first extra axis if currently selected axis is invalid
            if axes.find('sequence_number', axis) is None:
                excluded_axes = ('color', 'vertical', 'horizontal')
                axis = next((axis['sequence_number']
                             for axis in axes if axis['type'] not in excluded_axes), 0)

        # Raise error if axis sequence_number does not exist
        axis_properties = axes.find('sequence_number', axis)

        if axis_properties is None:
            raise IndexError('Invalid axis sequence_number specified: {0}'.format(axis))

        # Select the currently selected slice for the axis by default
        if index is None:
            index = axis_properties['slice']

        previous_slice = axis_properties['slice']
        num_slices = axis_properties['length'] - 1

        if isinstance(index, six.text_type):

            if index == 'next':
                new_slice = previous_slice + 1

            elif index == 'previous':
                new_slice = previous_slice - 1

            else:
                raise IndexError('Invalid slice requested: {0}'.format(index))

            # Roll over to zero if reached the end
            if new_slice > num_slices:
                new_slice = 0

            # Roll over to end if reached the beginning
            if new_slice < 0:
                new_slice = num_slices

        else:

            if (not isinstance(index, six.integer_types)) or (index > num_slices) or (index < 0):
                raise IndexError('Invalid slice selection specified: {0}'.format(index))

            new_slice = index

        # Save new selected axis
        if save_axis:
            self._settings['selected_axis'] = axis_properties['sequence_number']

        # Display a new slice if needed (changing only the selected axis, while keeping the slice index
        # the same, does not require a re-display of the data since it does not change)
        if new_slice != previous_slice:

            axis_index = axes.find_index('sequence_number', axis)
            axes.set(axis_index, 'slice', new_slice)
            self._header_widgets['frame'].set(new_slice)

            self._draw_slice()

    # Toggles whether colorbar is displayed for current image
    def toggle_colorbar(self, *args):

        if self.menu_option('show_colorbar'):
            self._add_colorbar()

        else:
            self._remove_colorbar()

    # Save the slice image to disk (as currently displayed). The extension in filename controls the image
    # format unless *format* is set; likely supported formats are support png, pdf, ps, eps and svg.
    def save_image(self, filename, format=None):

        # MPL seems only to be able to save an image as it is displayed. To ensure that the entire image
        # is saved, we resize the image temporarily to be its full size, and update all necessary parameters
        # to essentially equal the case where the full image would fit on the screen. Then we save the image,
        # and following that revert it back to the necessary size and parameters to view it correctly
        # (as before) in the display area.

        # Obtain the current image and margin dimensions
        image_width, image_height = self._image_dimensions()

        # Unpack scrollable canvas to hide plot redraw (a redraw will be called despite the display being
        # frozen because we have to force ``FigureCanvas.set_dimensions`` in order to resize the plot for
        # saving)
        self._scrollable_canvas.pack_forget()

        # Freeze the display, preventing unnecessary draw calls (significant time savings for large images)
        self.freeze_display()

        # Obtain margin (needed if tick labels are enabled)
        margin = max(self._margin_dimensions(display_dimensions=(image_width, image_height),
                                             image_dimensions=(image_width, image_height),
                                             for_save=True))

        # Save the original scrollbar positions, to restore at the end
        vert_scrollbar_pos = self._vert_scrollbar.get()
        horz_scrollbar_pos = self._horz_scrollbar.get()

        # Save the original dimensions of the figure, to restore at the end
        original_width, original_height = self._figure_canvas.get_dimensions(type='pixels')

        # Obtain and set figure to have dimensions such that the image + twice the margins (i.e. margin
        # on left side and margin on right side of image) fit exactly on it
        new_width = image_width + margin * 2
        new_height = image_height + margin * 2

        self._figure_canvas.set_dimensions((new_width, new_height), type='pixels', force=True)

        # Set image bounding box such that the display size includes the margin, and the image has its
        # real dimensions
        self._update_image_bbox(display_dimensions=(new_width, new_height),
                                image_dimensions=(image_width, image_height),
                                margin_dimensions=(0, 0))

        # Update the x and y axis limits to be the full size of the image. Further, update the ticks and
        # labels to account for the new size of the image.
        self._update_scroll_image_display()
        self._update_tick_labels(for_save=True)

        # Save figure, ensure facecolor is not ignored
        mpl_canvas = self._figure_canvas.mpl_canvas
        mpl_canvas.print_figure(filename,
                                dpi=self._settings['dpi'],
                                facecolor=self._figure_canvas.mpl_figure.get_facecolor(),
                                format=format)

        # Update figure dimensions, image bounding box and tick labels (each adjusted above) back to
        # proper level for display
        self._figure_canvas.set_dimensions((original_width, original_height), type='pixels')
        self._update_image_bbox()
        self._update_tick_labels()

        # Update scrollbar positions back to originals, and update displayed image accordingly if it's zoomed
        # (scrollbars will have been perturbed when the figure was resized such that the image fits entirely
        # on it. On resizing back down for display, the scrollbars would go back the centered positions by
        # default as opposed to the original positions.)
        self._vert_scrollbar.set(*vert_scrollbar_pos)
        self._horz_scrollbar.set(*horz_scrollbar_pos)
        self._update_scroll_image_display()

        # Pack the scrollable canvas back after it was unpacked above
        self._scrollable_canvas.pack(side='top', expand=1, fill='both')

        # Thaw the display, since it was frozen above
        self.thaw_display()

    # Resets the current view of the image, including all axis-limits, pan, zoom, rotations and inversions,
    # to the original view
    def reset_view(self):

        # Freeze the display temporarily so image is not needlessly re-drawn multiple times
        self.freeze_display()

        self._zoom(zoom_level=1)
        self.set_mode()
        self.set_axes_display(invert_axis='none')
        self.set_rotation(0)

        # Thaw the display, since it was frozen above
        self.thaw_display()

    # Freezes redrawing of image/slice on the screen, such that any updates to the image are not reflected
    # until it is thawed via `thaw_display`. This can be helpful, both for performance reasons and to hide
    # ugly redrawing, if the image would otherwise be redrawn a number of intermediate times.
    def freeze_display(self):

        # Increment counter that stores number of times freeze_display/thaw_display has been called
        self._freeze_display_counter += 1

        # Freeze the image if necessary
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

    # Adds menu options used for manipulating the data display
    def _add_menus(self):

        # Add options to the File menu
        file_menu = self._menu('File')
        file_menu.insert_command(0, label='Save Image', command=self._save_file_box)
        file_menu.insert_separator(1)

        # Add a Frame menu
        frame_menu = self._add_menu('Frame', in_menu='main')

        frame_menu.add_command(label='Data Cube', command=
                               lambda: self._add_dependent_window(DataCubeWindow(self._viewer, self)))

        frame_menu.add_separator()

        frame_menu.add_command(label='Next Frame', command=lambda: self.select_slice(index='next'))
        frame_menu.add_command(label='Previous Frame', command=lambda: self.select_slice(index='previous'))

        # Add a Zoom menu
        zoom_menu = self._add_menu('Zoom', in_menu='main', postcommand=self._update_zoom_menu)

        # Add a Scale menu
        scale_menu = self._add_menu('Scale', in_menu='main')

        scale_types = ('linear', 'log', 'squared', 'square root')

        for scale in scale_types:

            # PowerNorm is an MPL feature available in MPL v1.4+ only
            disable_powernorm = {}

            if (MPLCompat.PowerNorm is None) and (scale in ('squared', 'square root')):
                disable_powernorm = {'state': 'disabled'}

            scale_menu.add_checkbutton(label=scale.title(), onvalue=scale, offvalue=scale,
                                       variable=self._menu_options['scale'], **disable_powernorm)

        scale_menu.add_separator()

        scale_limits = ('min max', 'zscale')

        for limit in scale_limits:
            scale_menu.add_checkbutton(label=limit.title(), onvalue=limit, offvalue=limit,
                                       variable=self._menu_options['scale_limits'])

        scale_menu.add_separator()

        disable_mask_sp = {'onvalue': True}
        if not np.ma.is_masked(self.data):
            disable_mask_sp = {'onvalue': False, 'state': 'disabled'}

        scale_menu.add_checkbutton(label='Mask Special Constants', offvalue=False,
                                   variable=self._menu_options['mask_special'], **disable_mask_sp)

        scale_menu.add_separator()

        scale_menu.add_command(label='Scale Parameters...', command=lambda: self._add_dependent_window(
                ScaleParametersWindow(self._viewer, self, self._image)))

        # Add a Color menu
        color_menu = self._add_menu('Color', in_menu='main')

        colormaps = ('gray', 'Reds', 'Greens', 'Blues', 'hot', 'afmhot', 'gist_heat', 'cool', 'coolwarm',
                     'jet', 'rainbow', 'hsv')

        for color in colormaps:
            color_menu.add_checkbutton(label=color, onvalue=color, offvalue=color,
                                       variable=self._menu_options['colormap'])

        color_menu.add_separator()

        color_menu.add_checkbutton(label='RGB', onvalue='RGB', offvalue='RGB',
                                   variable=self._menu_options['colormap'])

        if not self._settings['is_rgb']:
            color_menu.entryconfig(color_menu.index('last'), state='disabled')

        color_menu.add_separator()

        # Add an All Colors sub-menu to the Color menu
        all_colors_menu = self._add_menu('All Colors', in_menu='Color')

        all_colormaps = [m for m in mpl.cm.datad if not m.endswith('_r')]

        for color in all_colormaps:
            all_colors_menu.add_checkbutton(label=color, onvalue=color, offvalue=color,
                                            variable=self._menu_options['colormap'])

        color_menu.add_separator()

        color_menu.add_checkbutton(label='Invert Colormap', onvalue=True, offvalue=False,
                                   variable=self._menu_options['invert_colormap'])

        color_menu.add_separator()

        # Add a Colorbar sub-menu to the Color menu
        colorbar_menu = self._add_menu('Colorbar', in_menu='Color')

        colorbar_menu.add_checkbutton(label='Show', onvalue=True, offvalue=False,
                                      variable=self._menu_options['show_colorbar'])

        # Add a Colorbar orientation sub-menu to the Colorbar menu
        colorbar_orient_menu = self._add_menu('Orientation', in_menu=('Color', 'Colorbar'))

        orientations = ('vertical', 'horizontal')

        for orientation in orientations:
            colorbar_orient_menu.add_checkbutton(label=orientation.capitalize(), onvalue=orientation,
                                                 offvalue=orientation,
                                                 variable=self._menu_options['colorbar_orient'])

        # Add a View menu
        self._add_view_menu()
        view_menu = self._menu('View')
        view_menu.add_separator()

        view_menu.add_checkbutton(label='Show Image Border', onvalue=True, offvalue=False,
                                  variable=self._menu_options['show_border'])

        # Add a Ticks sub-menu to the View Menu
        ticks_menu = self._add_menu('Ticks', in_menu='View')

        show_ticks = OrderedDict([('X', 'x'), ('Y', 'y'), ('XY', 'both')])
        for label, option in six.iteritems(show_ticks):
            ticks_menu.add_checkbutton(label='Show {0} Ticks'.format(label), onvalue=option,
                                       offvalue='none', variable=self._menu_options['show_axis_ticks'])

        # Add a Colorbar sub-menu to the View menu
        self._add_menu('Colorbar', in_menu='View', existing_menu=colorbar_menu)

    # Adds or updates menu options for the Zoom menu
    def _update_zoom_menu(self):

        zoom_menu = self._menu('Zoom')

        # Delete all items in the menu
        zoom_menu.delete(0, zoom_menu.index('last'))

        # Re-add all items in the menu
        zoom_menu.add_command(label='Reset Original View', command=self.reset_view)

        zoom_menu.add_separator()

        zoom_menu.add_command(label='Zoom to Fit', command=self.zoom_to_fit)

        zoom_menu.add_separator()

        zoom_menu.add_checkbutton(label='Pan', onvalue=True, offvalue=False, variable=self._menu_options['pan'])
        zoom_menu.add_checkbutton(label='Axis-Limits to Rectangle', onvalue=True, offvalue=False,
                                  variable=self._menu_options['axis_limits_to_rectangle'])

        zoom_menu.add_separator()

        zoom_menu.add_command(label='Zoom In', command=lambda: self._zoom('in'))
        zoom_menu.add_command(label='Zoom Out', command=lambda: self._zoom('out'))

        zoom_menu.add_separator()

        # Zoom options
        zoom_opts = {} if self.menu_option('mode') == 'image' else {'state': 'disabled'}
        zoom_levels = ('1/32', '1/16', '1/8', '1/4', '1/2', '1', '2', '4', '8', '16', '32')

        for level in zoom_levels:
            label = 'Zoom {0}'.format(level)
            level = '{0},{0}'.format(level)

            zoom_menu.add_checkbutton(label=label, onvalue=level, offvalue=level,
                                            variable=self._menu_options['zoom_level'], **zoom_opts)

        zoom_menu.add_separator()

        # Aspect Ratio options
        zoom_menu.add_checkbutton(label='Image Mode', onvalue='image', offvalue='image',
                                  variable=self._menu_options['mode'])

        zoom_menu.add_checkbutton(label='Array Mode', onvalue='array', offvalue='array',
                                  variable=self._menu_options['mode'])

        zoom_menu.add_command(label='Manual Aspect Ratio', command=lambda: self._add_dependent_window(
                                                                    ZoomPropertiesWindow(self._viewer, self)))

        zoom_menu.add_separator()

        # Image Invert options
        invert_options = OrderedDict([('None', 'none'), ('Invert X', 'x'),
                                      ('Invert Y', 'y'), ('Invert XY', 'both')])
        for label, option in six.iteritems(invert_options):

            zoom_menu.add_checkbutton(label=label, onvalue=option, offvalue=option,
                                            variable=self._menu_options['invert_axis'])

        zoom_menu.add_separator()

        # Image Rotation options
        rotation_angles = (0, 90, 180, 270)

        for angle in rotation_angles:
            label = '{0} Degrees'.format(angle)
            zoom_menu.add_checkbutton(label=label, onvalue=angle, offvalue=angle,
                                            variable=self._menu_options['rotation_angle'])

        zoom_menu.add_separator()

        # Orientation Options (i.e. whether to use Display_Settings)
        valid_display_settings = self.meta_data.display_settings and self.meta_data.display_settings.valid
        has_2_axes = self.meta_data.num_axes() == 2
        display_opts = {} if valid_display_settings else {'state': 'disabled'}
        storage_opts = {} if (has_2_axes or not valid_display_settings) else {'state': 'disabled'}

        zoom_menu.add_checkbutton(label='Display Orientation', onvalue='display', offvalue='display',
                                        variable=self._menu_options['orientation'], **display_opts)
        zoom_menu.add_checkbutton(label='Storage Orientation', onvalue='storage', offvalue='storage',
                                        variable=self._menu_options['orientation'], **storage_opts)

    # Draws the header box, which contains the name of the structure, the current frame, the pixel location
    # that the mouse pointer is over and that pixel's value
    def _draw_header(self):

        header_box = Frame(self._header, height=82, bg=self.get_bg('gray'))
        header_box.pack(fill='x', expand=1)

        value_box_params = {'background': self.get_bg('gray'), 'borderwidth': 1, 'relief': 'groove'}
        line_box_params = {'background': self.get_bg('gray'), 'height': 25}

        entry_params = {'disabledbackground': self.get_bg('gray'), 'state': 'disabled',
                        'borderwidth': 0, 'highlightthickness': 0, 'disabledforeground': 'black'}

        # Add the header line containing the structure name
        structure_line_box = Frame(header_box, **line_box_params)
        structure_line_box.pack(side='top', anchor='w', pady=(4, 4))

        structure_text_box = Frame(structure_line_box, height=20, width=70, bg=self.get_bg('gray'))
        structure_text_box.pack(side='left')

        w = Label(structure_text_box, text='Structure', bg=self.get_bg('gray'))
        w.pack(side='left')

        structure_name_box = Frame(structure_line_box, height=20, width=330, **value_box_params)
        structure_name_box.pack(side='left')

        w = Label(structure_name_box, text=self.structure.id, bg=self.get_bg('gray'))
        w.pack(side='left', padx=(10, 10))

        structure_text_box.pack_propagate(False)
        structure_name_box.pack_propagate(False)

        # Add the header line containing the current frame number
        frame_line_box = Frame(header_box, **line_box_params)
        frame_line_box.pack(side='top', anchor='w', pady=(0, 4))

        frame_text_box = Frame(frame_line_box, height=20, width=70, bg=self.get_bg('gray'))
        frame_text_box.pack(side='left')

        w = Label(frame_text_box, text='Frame', bg=self.get_bg('gray'))
        w.pack(side='left')

        frame_num_box = Frame(frame_line_box, height=20, width=330, **value_box_params)
        frame_num_box.pack(side='left')

        frame_text_box.pack_propagate(False)
        frame_num_box.pack_propagate(False)

        frame_num = StringVar()
        frame_num.set('0')
        self._header_widgets['frame'] = frame_num
        e = Entry(frame_num_box, textvariable=frame_num, **entry_params)
        e.pack(side='left', padx=(10, 10))

        # Add the header line containing X, Y and pixel value
        pixel_line_box = Frame(header_box, **line_box_params)
        pixel_line_box.pack(side='top', anchor='w', pady=(0, 4))

        pixel_text_box = Frame(pixel_line_box, height=25, width=70, bg=self.get_bg('gray'))
        pixel_text_box.pack(side='left')

        w = Label(pixel_text_box, text='Pixel', bg=self.get_bg('gray'))
        w.pack(side='left')

        w = Label(pixel_text_box, text='X', bg=self.get_bg('gray'))
        w.pack(side='right', padx=(0, 5))

        pixel_text_box.pack_propagate(False)

        x_pixel_box = Frame(pixel_line_box, height=25, **value_box_params)
        x_pixel_box.pack(side='left')

        x_pixel = StringVar()
        self._header_widgets['x'] = x_pixel
        e = Entry(x_pixel_box, textvariable=x_pixel, width=8, **entry_params)
        e.pack(side='left', padx=(10, 10))

        w = Label(pixel_line_box, text='Y', bg=self.get_bg('gray'))
        w.pack(side='left', padx=(10, 5))

        y_pixel_box = Frame(pixel_line_box, height=25, **value_box_params)
        y_pixel_box.pack(side='left')

        y_pixel = StringVar()
        self._header_widgets['y'] = y_pixel
        e = Entry(y_pixel_box, textvariable=y_pixel, width=8, **entry_params)
        e.pack(side='left', padx=(10, 10))

        w = Label(pixel_line_box, text='Value', bg=self.get_bg('gray'))
        w.pack(side='left', padx=(10, 5))

        value_box = Frame(pixel_line_box, height=25, **value_box_params)
        value_box.pack(side='left')

        pixel_value = StringVar()
        self._header_widgets['value'] = pixel_value
        e = Entry(value_box, textvariable=pixel_value, width=14, **entry_params)
        e.pack(side='left', padx=(10, 10))

        divider = Frame(header_box, height=1, bg='#737373')
        divider.pack(side='bottom', fill='x', expand=1)

    # Initializes or updates the MPL Figure and draws slice_data on it. This must be called any time the
    # dimensions of slice_data change, to reflect the changes in figure dimensions. load_array() must have
    # been called for the array this slice_data came from at least once prior to this method being called.
    def _draw_slice(self):

        # Freeze the display temporarily so image is not needlessly re-drawn multiple times
        self.freeze_display()

        # Get the new slice data to show
        self._slice_data = self._get_slice_data(update=True)

        # We typically use weakref to pass data into MPL because it reduces memory leaks. However, for
        # masked data, weakref breaks the actual masking out by imshow (at least through MPL 3.0).
        slice_data = self._slice_data if np.ma.is_masked(self._slice_data) else weakref.proxy(self._slice_data)

        # Create the figure if it does not exist
        if not self._data_open:
            figure = Figure(dpi=self._settings['dpi'], facecolor='white')

            # Create the FigureCanvas, which is a wrapper for FigureCanvasTkAgg()
            self._figure_canvas = FigureCanvas(figure, master=self._scrollable_canvas)
            self._figure_canvas.tk_widget.config(background='white')
            self._scrollable_canvas.create_window(0, 0, window=self._figure_canvas.tk_widget, anchor='nw')

            # Create the toolbar (hidden, used for its pan and axis-limits to rectangle options)
            self._toolbar = MPLCompat.NavigationToolbar2Tk(self._figure_canvas.mpl_canvas, self._display_frame)
            self._toolbar.update()
            self._toolbar.pack_forget()

            # Create an axis for the new image
            ax = self._figure_canvas.mpl_figure.add_axes([0, 0, 1, 1], axisbelow=True, frame_on=False,
                                                         clip_on=False)

            # Draw the image
            self._image = ax.imshow(slice_data, origin='lower', interpolation='none',
                                    norm=mpl.colors.Normalize(), aspect='auto')

            # Disable X and Y tick labels
            ax.get_xaxis().set_visible(False)
            ax.get_yaxis().set_visible(False)

        # Update figure data if it already exists
        else:
            self._image.set_data(slice_data)

        # Set image extent to correspond to from 0 to image dimensions. By default MPL goes from -0.5 to
        # dimensions+0.5, this does not look good when tick labels are enabled. Note that extent has an
        # effect on orientation and axis inversion; therefore if this line is ever changed the display
        # dictionary orientation code and/or image origin likely has to be modified.
        image_width, image_height = self._image_dimensions(zoom_level=1)
        self._image.set_extent([0, image_width, 0, image_height])

        # Update scale to match current menu_options
        # (zoom, axis inversion, rotation, colormap and tick labels are implicitly updated by calls to
        # other methods)
        self._update_scale()

        # Update mode to match current menu_options
        self._update_mode()

        # Add colorbar to image
        if self._colorbar is None:
            self._add_colorbar()

        # Set figure dimensions to match viewing area
        self._update_figure_dimensions()

        # Thaw the display, since it was frozen above
        self.thaw_display()

    # Returns the 2D (in case of grayscale) or 3D (in case of color) array containing the data for the
    # currently shown slice. If `update` is set, the returned array will be updated to reflect the currently
    # selected menu and slice options. The returned array will always have axes in the proper storage
    # order for display (vertical axis, horizontal axis, [color axis]).
    def _get_slice_data(self, update=False):

        # If we are not updating the array to reflect currently selected settings then we just
        # return the previously stored values.
        if not update:
            return self._slice_data

        axes = self._settings['axes']
        axes_slice = tuple([axes[i]['slice'] for i in range(0, len(self._settings['axes']))])

        # Obtain 2D (in case of grayscale data) or 3D (in case of color data) image data for current
        # subframe selections
        array_data = self.data[axes_slice]

        # Obtain sequence numbers for vertical, horizontal and color axes
        vertical_seq = axes.find('type', 'vertical')['sequence_number']
        horizontal_seq = axes.find('type', 'horizontal')['sequence_number']
        color_seq = None

        color_axis = axes.find('type', 'color')
        if color_axis:
            color_seq = color_axis['sequence_number']

        # Our data is now 2D or 3D, and we need to obtain order of axes for this data. For example,
        # we want (2, 8, 4) to become (0, 2, 1)
        if color_seq is None:
            seq_list = (vertical_seq, horizontal_seq)
        else:
            seq_list = (vertical_seq, horizontal_seq, color_seq)

        indicies = [i for i, x in sorted(enumerate(seq_list), key=lambda tup: tup[1])]

        vertical_seq = indicies[0]
        horizontal_seq = indicies[1]
        color_seq = None if color_seq is None else indicies[2]

        # Roll the color axis to the last position if present
        color_axis_adjust = 0

        if color_axis is not None:

            array_data = np.rollaxis(array_data, color_seq, 3)
            color_axis_adjust = 1

            # Adjust sequence numbers of other axes (the ones that could be in front)
            if horizontal_seq > color_seq:
                horizontal_seq -= 1

            if vertical_seq > color_seq:
                vertical_seq -= 1

        # Roll the horizontal axis to second position
        array_data = np.rollaxis(array_data, horizontal_seq, 2 + color_axis_adjust)

        # Adjust sequence numbers of other axes (the ones that could be in front)
        if vertical_seq > horizontal_seq:
            vertical_seq -= 1

        # Roll the vertical axis to the first position
        array_data = np.rollaxis(array_data, vertical_seq, 1 + color_axis_adjust)

        # Adjust color axis in ways necessary for MPL to acceptably plot color images
        if color_axis is not None:

            # Adjust color axis to have 3-bands (in case it had had more), one for each color in RGB.
            rgb_bands = self._settings['rgb_bands']
            color_indicies = [rgb_bands[0] - 1, rgb_bands[1] - 1, rgb_bands[2] - 1]

            # Try to avoid using fancy indexing if possible (avoiding making a copy)
            is_consecutive = sorted(color_indicies) == list(range(min(color_indicies), max(color_indicies)+1))
            if is_consecutive:
                array_data = array_data[:, :, min(color_indicies):max(color_indicies)+1]
            else:
                array_data = array_data[:, :, color_indicies]

            colormap = self.menu_option('colormap')

            # For RGB colormap we show an RGB image
            if colormap == 'RGB':

                # Calculate the finite (non-NaN and non-Inf) maximum and minimum values in the array
                array_min, array_max = finite_min_max(array_data)

                # Copy data from original array if it hasn't been copied; otherwise it'll be overwritten
                # below
                if is_consecutive:
                    array_data = array_data.copy()

                # Adjust array of integers to fit in uint8 range of 0-255 as MPL's imshow() expects
                array_dtype = array_data.dtype
                if np.issubdtype(array_dtype, np.integer):

                    np.divide(255.0 * (array_data - array_min), (array_max - array_min), out=array_data, casting='unsafe')

                    try:
                        array_data = array_data.astype('uint8', copy=False)
                    except TypeError:
                        array_data = array_data.astype('uint8')

                # Adjust array of floats to be normalized in 0-1 range as MPL's imshow() expects
                elif np.issubdtype(array_dtype, np.floating):
                    np.divide((array_data - array_min), (array_max - array_min), out=array_data, casting='unsafe')

            # For grayscale colormaps we convert the data to monochrome
            else:
                array_data = np.dot(array_data[..., :3], [0.299, 0.587, 0.144])

        # Rotate slice if requested
        rotation_angle = self.menu_option('rotation_angle')
        array_data = np.rot90(array_data, int(rotation_angle // 90))

        return array_data

    # Adds a colorbar to the GUI if menu_options are set to show one
    def _add_colorbar(self):

        # Skip adding a colorbar if none is suppose to be shown
        if not self.menu_option('show_colorbar'):
            return

        # Pack the colorbar frame, which will contain the colorbar
        orientation = self.menu_option('colorbar_orient')

        if orientation == 'vertical':
            self._colorbar_frame.pack(side='right', fill='y', before=self._scrollable_canvas)
        else:
            self._colorbar_frame.pack(side='bottom', fill='x', before=self._scrollable_canvas)

        # Add new colorbar
        self._colorbar = Colorbar(self._colorbar_frame, self._image, orientation)

        # Creating a new scroll event binding because calling FigureCanvasTkAgg() in Colorbar() rebinds it
        self._bind_scroll_event(self._mousewheel_scroll)

        # The figure dimensions change due to colorbar taking up space and need updating
        self._update_figure_dimensions()

    # Removes the colorbar from the GUI if one is being shown
    def _remove_colorbar(self):

        # Skip removing the colorbar if none exists
        if self._colorbar is None:
            return

        # Remove the callback to destroy the colorbar on window close
        self._remove_callbacks('close', self._colorbar.destroy, ignore_args=True)

        self._colorbar.destroy()
        self._colorbar = None
        self._colorbar_frame.pack_forget()

        # The figure dimensions change due to colorbar taking up space and need updating
        self._update_figure_dimensions()

    # Update menu_options to specified zoom_level, and then call _update_zoom() to zoom to that level. If
    # no zoom level is specified then an action may be specified, and the image is zoomed in or out
    # (depending on the action) by the zoom_factor variable
    def _zoom(self, action='in', zoom_level=None):

        # Determine zoom level if none if specified
        if zoom_level is None:

            # Obtain the current zoom level
            zoom_level = self.get_zoom_level()

            # Determine zoom level when adjusted by zoom factor
            zoom_factor = 0.20

            if action == 'in':
                zoom_level[0] *= (1 + zoom_factor)
                zoom_level[1] *= (1 + zoom_factor)

            else:
                zoom_level[0] /= (1 + zoom_factor)
                zoom_level[1] /= (1 + zoom_factor)

        # Save the new zoom level
        self.set_zoom(zoom_level)

    # Activates the Pan image option
    def _pan(self, *args):

        # Disable axis-limits to rectangle if it is enabled
        limits_option = self._menu_options['axis_limits_to_rectangle']
        pan_option = self._menu_options['pan']

        if pan_option.get() and limits_option.get():
            limits_option.set(False)

        # Enable pan
        self._toolbar.pan()

    # Activates the Axis-Limits to Rectangle option
    def _axis_limits_to_rectangle(self, *args):

        # Disable pan if it is enabled
        limits_option = self._menu_options['axis_limits_to_rectangle']
        pan_option = self._menu_options['pan']

        if pan_option.get() and limits_option.get():
            pan_option.set(False)

        # Enable axis-limits to rectangle (called zoom by MPL)
        self._toolbar.zoom()

    # Inverts the axis limits for an axis. Valid options for *axis* are x|y|both. This is a helper method,
    # to permanently invert axes use `set_axes_display`.
    def _invert_axis(self, axis):

        ax = self._image.axes

        if axis in ('x', 'both'):

            image_width = self._image_dimensions(zoom_level=1)[0]

            x_min, x_max = ax.get_xlim()
            x_min = image_width - x_min
            x_max = image_width - x_max

            ax.set_xlim(x_min, x_max)

        if axis in ('y', 'both'):

            image_height = self._image_dimensions(zoom_level=1)[1]

            y_min, y_max = ax.get_ylim()
            y_min = image_height - y_min
            y_max = image_height - y_max

            ax.set_ylim(y_min, y_max)

    # Update the image scaling law to match the current menu_options value
    def _update_scale(self, *args):

        scale = self.menu_option('scale')

        # Get only the finite slice data (NaNs and infs will be masked and thus ignored)
        slice_data = self._image.get_array()

        if scale == 'linear':
            norm = mpl.colors.Normalize()

        elif scale == 'log':
            norm = mpl.colors.LogNorm()

        elif scale == 'squared':
            norm = MPLCompat.PowerNorm(gamma=2.)

        elif scale == 'square root':
            norm = MPLCompat.PowerNorm(gamma=0.5)

        else:
            self._menu_options['scale'].set('linear')
            raise ValueError('Unknown scale: {0}'.format(scale))

        scale_limits = self.menu_option('scale_limits')

        if scale_limits == 'min max':

            norm.vmin = np.ma.min(slice_data)
            norm.vmax = np.ma.max(slice_data)

            if isinstance(norm.vmin, np.ma.MaskedArray):
                norm.vmin = norm.vmin.compressed()[0]

            if isinstance(norm.vmax, np.ma.MaskedArray):
                norm.vmax = norm.vmax.compressed()[0]

        elif scale_limits == 'zscale':

            zscale_lim = zscale(slice_data)

            norm.vmin = zscale_lim[0]
            norm.vmax = zscale_lim[1]

        else:

            custom_scale = scale_limits.split(',')
            unknown_scale = False

            if len(custom_scale) == 2:

                try:
                    norm.vmin = float(custom_scale[0])
                    norm.vmax = float(custom_scale[1])

                except ValueError:
                    unknown_scale = True

            else:
                unknown_scale = True

            if unknown_scale:
                self._menu_options['scale_limits'].set('min max')
                raise ValueError('Unknown scale limits: {0}'.format(scale_limits))

        # If scaling minimum and maximum are the same value, scale to just less and just greater
        # (having equal values causes MPL errors)
        if norm.vmin == norm.vmax:
            norm.vmin -= 0.1
            norm.vmax += 0.1

        # Clamp down to zero for scaling minimum of LogNorm and PowerNorm
        # (otherwise MPL will raise an error for LogNorm or break the colorbar for PowerNorm)
        if (norm.vmin < 0) and (('log' in scale) or ('square' in scale)):
            slice_data = slice_data.compressed()

            if np.ma.max(slice_data) > 0:
                norm.vmin = 0
            else:
                norm.vmin = 0
                norm.vmax = 1E-11

        # Use close to zero instead of exactly zero to avoid division by zero in MPL's `LogNorm.inverse`
        if (norm.vmin == 0) and ('log' in scale):
            norm.vmin = 1E-10

        # Ensure scaling minimum is less than maximum once other adjustments finished, reverse if necessary
        if norm.vmin > norm.vmax:
            _norm_max = norm.vmax
            norm.vmax = norm.vmin
            norm.vmin = _norm_max

        # Freeze the display temporarily so image is not needlessly re-drawn multiple times
        self.freeze_display()

        # Update the norm. Calling set_norm() will cause issues when switching norms, because colorbar
        # still has the previous norm, and set_norm() will try to update its min/max without updating
        # the norm scale. Therefore we set the norm manually, then update the colormap, then call changed()
        # ourselves on the AxisImage to update it
        self._image.norm = norm
        self._update_colormap()
        self._image.changed()

        # Thaw the display, since it was frozen above
        self.thaw_display()

    # Update the image rotation to match current menu_options value
    def _update_rotation(self, *args):

        menu_option = self._menu_options['rotation_angle']
        rotation_angle = menu_option.get()

        if rotation_angle % 90 != 0:
            menu_option.set(0)
            raise ValueError("Rotation angle '{0}'must be evenly divisible by 90".format(rotation_angle))

        # Update the slice data to reflect the new rotation
        self._draw_slice()

    # Updates the image orientation setting (orient via display dictionary or via storage order) to match
    # current menu_options value
    def _update_orientation(self, *args):

        menu_option = self._menu_options['orientation']
        orientation = menu_option.get()

        # Set orientation
        if orientation in ('display', 'storage'):

            # Do nothing if the only valid orientation is 'storage' as there are no valid display settings
            if (self.meta_data.display_settings is None) or (not self.meta_data.display_settings.valid):
                return

            # Adjust slice axes to use proper axes for X and Y, which also redraws the image thus
            # adjusting the axis inversion to proper level
            self.set_slice_axes()

        else:
            menu_option.set('display')
            raise ValueError('Unknown orientation setting selected: {0}'.format(orientation))

    # Updates the zoom level to match the current mode menu_options value
    def _update_mode(self, *args):

        mode = self.menu_option('mode')

        if mode == 'image':

            zoom = self.get_zoom_level()
            if zoom[0] != zoom[1]:
                self._zoom(zoom_level=1)

        elif mode == 'array':
            self.zoom_to_fit()

        elif mode != 'manual':
            self.set_mode()
            raise ValueError('Unknown mode: {0}'.format(mode))

    # Update the axis inversion to match current menu_options value
    def _update_invert_axis(self, has_default_orientation=False, *args):

        invert_axis = self.menu_option('invert_axis')

        # Reset any axis inversions (which will also call this method again)
        if not has_default_orientation:
            self._update_scroll_image_display()
            return

        # Set axes inversion to proper orientation based on Display Settings
        display_settings = self.meta_data.display_settings
        use_display_orientation = self.menu_option('orientation') == 'display'

        if (display_settings is not None) and display_settings.valid and use_display_orientation:
            display_direction = display_settings['Display_Direction']

            if 'Top to Bottom' in display_direction['vertical_display_direction']:
                self._invert_axis('y')

            if 'Right to Left' in display_direction['horizontal_display_direction']:
                self._invert_axis('x')

        # For storage orientation, we invert the y-axis such that it defaults to Y=0 at the top
        elif not use_display_orientation:
            self._invert_axis('y')

        # Invert X, Y or both axes based on current menu settings
        if invert_axis in ('x', 'y', 'both'):
            self._invert_axis(invert_axis)

        elif invert_axis != 'none':
            self._menu_options['invert_axis'].set('none')
            raise ValueError('Unknown axis to invert: {0}'.format(invert_axis))

        self._figure_canvas.draw()

    # Update the colormap to match the current menu_options value
    def _update_colormap(self, *args):

        axes = self._settings['axes']
        cmap = self.menu_option('colormap')

        # Special handling for RGB images
        if self._settings['is_rgb']:

            if not self._data_open:
                return

            # Enable (when using RGB scaling) or disable (when using grayscale) the color axis
            has_color_axis = False if axes.find('type', 'color') is None else True

            if cmap == 'RGB' and (not has_color_axis):
                self.set_slice_axes()

            elif cmap != 'RGB' and has_color_axis:
                self.set_slice_axes(color_axis='none')

            # Do not update actual colormap for RGB images
            if cmap == 'RGB':
                return

        if self.menu_option('invert_colormap'):
            cmap += '_r'

        # Freeze the display temporarily so image is not needlessly re-drawn multiple times
        self.freeze_display()

        # Update the cmap. Calling set_cmap() will cause issues when also switching norms, because colorbar
        # still has the previous norm, and set_cmap() will try to update its min/max without updating the norm
        # type. Therefore we set the cmap manually, then update the colormap, then call changed() ourselves on
        # the AxisImage to update it
        self._image.cmap = mpl.cm.get_cmap(cmap)
        self._update_colorbar()
        self._image.changed()

        # Thaw the display, since it was frozen above
        self.thaw_display()

    # Update the colorbar (e.g. if it's been changed from horizontal to vertical, the slice being viewed has
    # changed, or the image's colormap, scaling law, dimensions have been changed)
    def _update_colorbar(self, full_redraw=False, *args):

        if self.menu_option('show_colorbar') and (self._colorbar is not None):

            # Remove and re-draw if requested (e.g. on change of vertical/horizontal)
            if full_redraw:

                self._remove_colorbar()
                self._add_colorbar()

            # Update only colors, scaling and ticks otherwise
            else:

                self._colorbar.update(self._image)

    # Shows or hides axis ticks, tick labels and border around image, as configured by current menu_options.
    # The *for_save* parameter should be used if tick labels are being set for saving the image, not for
    # displaying it on the screen.
    def _update_tick_labels(self, for_save=False, *args):

        ax = self._image.axes

        # Retrieve and set the size for the tick labels and padding, as well as tick mark lengths and widths
        # (bigger for bigger images and display sizes)
        tick_params = self.__get_tick_parameters(for_save=for_save)

        ax.tick_params(axis='both', which='major', direction='in',
                       labelsize=tick_params['label_size'], pad=tick_params['label_pad'],
                       length=tick_params['tick_length'], width=tick_params['tick_width'])

        # Retrieve the sizes of the display, the image and the margin
        display_width, display_height = self._display_dimensions()
        image_width, image_height = self._image_dimensions()
        margin_width, margin_height = self._margin_dimensions(for_save=for_save)

        # Determine whether image + margin fits into display size
        width_does_not_fit = image_width + margin_width > display_width
        height_does_not_fit = image_height + margin_height > display_height

        # Hide currently shown X and Y ticks
        ax.get_xaxis().set_visible(False)
        ax.get_yaxis().set_visible(False)

        # Validate tick labels setting
        show_axis_ticks = self.menu_option('show_axis_ticks')

        if show_axis_ticks not in ('x', 'y', 'both', 'none'):
            self._menu_options['show_axis_ticks'].set('none')
            raise ValueError('Unknown tick labels enabled: {0}'.format(show_axis_ticks))

        # Show X and Y axis tick labels if requested
        if show_axis_ticks in ('x', 'both'):

            x_axis = ax.get_xaxis()
            x_axis.set_visible(True)
            x_axis.set_ticks_position('bottom' if height_does_not_fit else 'both')

        if show_axis_ticks in ('y', 'both'):

            y_axis = ax.get_yaxis()
            y_axis.set_visible(True)
            y_axis.set_ticks_position('left' if width_does_not_fit else 'both')

        # Show / hide image border if requested
        if self.menu_option('show_border'):

            ax.set_frame_on(True)

            # Hide border on right and top if the image does not fit into the display area for those
            # dimensions; otherwise show it
            ax.spines['right'].set_visible(not width_does_not_fit)
            ax.spines['top'].set_visible(not height_does_not_fit)

            # Hide border on left and bottom if the image does not fit into the display area for those
            # dimensions and if simultaneously the tick labels are not enabled for those axes; otherwise show
            ax.spines['left'].set_visible(not width_does_not_fit or show_axis_ticks in ('x', 'both'))
            ax.spines['bottom'].set_visible(not height_does_not_fit or show_axis_ticks in ('y', 'both'))

        else:
            ax.set_frame_on(False)

        # Update bounding box for the image to take into account the margins
        # (e.g. if the image is larger than the display area, then the bounding box of the image has
        #  to be made smaller such that there is still room on the figure to fit the tick labels)
        self._update_image_bbox()

        # Update the length of the scrollbar to take into account the margins
        # (e.g. if the image is now smaller than display area then no need for scrollbar; if the image is
        #  bigger than the display area then the scrollbar should be smaller the bigger the image is, since
        # less of it fits with-in the available viewing area.)
        self._update_scrollbar_length()

    # Zoom image to the level set by menu_options
    def _update_zoom(self, *args):

        # Freeze the display temporarily so image is not needlessly re-drawn multiple times
        self.freeze_display()

        # Update image bounding box to reflect the new zoom level.
        # (e.g. if the image is smaller than the display area then bounding box does not stretch to
        #  fill the entire figure, but rather has the right proportions to exactly display the image.
        #  If the image is larger than the display area then the bounding box essentially fills the entire
        #  figure, minus the margins necessary for the tick labels if those are enabled).
        self._update_image_bbox()

        # Update the length of the scrollbar to reflect the new zoom level.
        # (e.g. if the image is now smaller than display area then no need for scrollbar; if the image is
        #  bigger than the display area then the scrollbar should be smaller the bigger the image is, since
        # less of it fits with-in the available viewing area.)
        self._update_scrollbar_length()

        # Update tick labels (tick label size depends on the zoom level)
        self._update_tick_labels()

        # Thaw the display, since it was frozen above
        self.thaw_display()

    # Sets the X, Y and pixel value in the header based on current mouse pointer location
    def _update_mouse_pixel_value(self, event):

        event_outside_bounds = True

        # If the event is an MPL MouseEvent then we may have scrolled mouse on the image
        if isinstance(event, mpl.backend_bases.MouseEvent):

            slice_data = self._get_slice_data()
            image_width, image_height = self._image_dimensions(zoom_level=1)

            event_has_position = (event.xdata is not None) and (event.ydata is not None)
            is_on_image = event.inaxes == self._image.axes

            if event_has_position and is_on_image:

                is_in_x_bounds = (event.xdata >= 0) and (image_width > event.xdata)
                is_in_y_bounds = (event.ydata >= 0) and (image_height > event.ydata)

                if is_in_x_bounds and is_in_y_bounds:

                    x_position = event.xdata
                    y_position = event.ydata
                    pixel_value = slice_data[int(y_position), int(x_position)]

                    self._header_widgets['x'].set('{0:.01f}'.format(x_position))
                    self._header_widgets['y'].set('{0:.01f}'.format(y_position))

                    # Format pixel value for an RGB array
                    if is_array_like(pixel_value):

                        # For RGB arrays we only need to format floats, integers are formatted fine as-is
                        if np.issubdtype(pixel_value.dtype, np.floating):
                            pixel_value = ('[' +
                                           ', '.join(["{0:0.3f}".format(i).lstrip('0') for i in pixel_value])
                                           + ']')

                    # Format scalar pixel value
                    elif not isinstance(pixel_value, np.ma.core.MaskedConstant):
                        pixel_value = '{0:10}'.format(pixel_value).lstrip()

                    self._header_widgets['value'].set(pixel_value)

                    event_outside_bounds = False

        # Remove values from X, Y and pixel value if the mouse pointer is not on the image
        if event_outside_bounds:
            self._header_widgets['x'].set('')
            self._header_widgets['y'].set('')
            self._header_widgets['value'].set('')

    # Returns the dimensions (width, height) of the area available to display the figure in pixels
    # (including the image and the margins)
    def _display_dimensions(self):

        display_width, display_height = self._figure_canvas.get_dimensions(type='pixels')

        return display_width, display_height

    # Returns the dimensions (width, height) of the image in pixels (this includes adjustments to
    # the image's size by zoom)
    def _image_dimensions(self, zoom_level=None):

        if zoom_level is None:
            zoom_level = self.get_zoom_level()

        elif isinstance(zoom_level, (int, float)):
            zoom_level = [zoom_level] * 2

        image_width = self._get_slice_data().shape[1] * zoom_level[0]
        image_height = self._get_slice_data().shape[0] * zoom_level[1]

        return image_width, image_height

    # Returns the dimensions of the margins (width, height) in pixels. By default, the margins necessary
    # to display the image at current menu_options and display size are returned. The margins are part of the
    # figure but not part of the image; they are necessary to allow tick labels to be displayed when
    # the image is bigger than the display area size.
    def _margin_dimensions(self, display_dimensions=None, image_dimensions=None, for_save=False):

        show_axis_ticks = self.menu_option('show_axis_ticks')

        label_size = self.__get_tick_parameters(display_dimensions=display_dimensions,
                                                image_dimensions=image_dimensions,
                                                for_save=for_save)['label_size']
        margin_width = 0
        margin_height = 0

        if show_axis_ticks in ('y', 'both'):
            margin_width = label_size * len(str(max(self._image_dimensions(zoom_level=1))))

        if show_axis_ticks in ('x', 'both'):
            margin_height = label_size * 2

        return margin_width, margin_height

    # Returns a bbox rectangle [left, bottom, width, height], which specifies the bounding box for the image
    # on the MPL figure, in 0-1 relative coordinates. For example, if ''left'' were 0.5, the image would
    # start at x = 0.5 * figure_width. By default the bounding box returned is the one needed to display the
    # image correctly on the current display size and with other options as currently set via menu_options.
    def _image_bbox(self, display_dimensions=None, image_dimensions=None, margin_dimensions=None):

        # Set current display, image and margin dimensions if none given
        if display_dimensions is None:
            display_dimensions = self._display_dimensions()

        if image_dimensions is None:
            image_dimensions = self._image_dimensions()

        if margin_dimensions is None:
            margin_dimensions = self._margin_dimensions()

        # Obtain display, image and margin dimensions needed to calculate the image bounding box
        display_width, display_height = display_dimensions
        image_width, image_height = image_dimensions
        margin_width, margin_height = margin_dimensions

        # Adjust image width and height to a maximum of the display width and height
        image_width = display_width if image_width > display_width else image_width
        image_height = display_height if image_height > display_height else image_height

        # Calculate left and bottom such that image is centered on the screen
        left = (display_width // 2 - image_width // 2) / display_width
        bottom = (display_height // 2 - image_height // 2) / display_height

        # Calculate width and height such that as much of the image as possible fits on the screen
        # (no less, but also no more)
        width = image_width / display_width
        height = image_height / display_height

        # Calculate when image + 2x margins does not fit into display
        # (it is twice the margins because when the display is being shrunk, there are margins on both
        # sides of the image since the image is centered on the figure/display; if we checked only one side
        # then this would kick in when half of the tick labels are invisible.)
        width_does_not_fit = image_width + margin_width * 2 > display_width
        height_does_not_fit = image_height + margin_height * 2 > display_height

        # Ensure that there is room to show tick labels when the image is bigger than the size of the window
        if width_does_not_fit or height_does_not_fit:

            # Calculate margin (in bbox units) necessary
            left_adjust = margin_width / display_width
            bottom_adjust = margin_height / display_height

            # Takes care of situation where bottom + height < 1, but bottom is smaller than requested margin
            if bottom_adjust > bottom:
                bottom = bottom_adjust

            # If margins and image do not fit vertically into the display/figure, then adjust image
            # bounding box to give space for the margins by showing only part of the image
            if bottom + height >= 1:
                # bottom = bottom_adjust
                height_adjusted = 1.0 - bottom

            else:
                height_adjusted = height

            # Takes care of situation where left + width < 1, but left is smaller than requested margin
            if left_adjust > left:
                left = left_adjust

            # If margins and image do not fit horizontally into the display/figure, then adjust image
            # bounding box to give space for the margins by showing only part of the image
            if left + width >= 1:
                # left = left_adjust
                width_adjusted = 1.0 - left_adjust

            else:
                width_adjusted = width

            height = height_adjusted
            width = width_adjusted

        bbox = [left, bottom, width, height]

        return bbox

    # Called when the window has been resized, this method updates the dimensions of the various things that
    # need resizing together with a window resize
    def _window_resize(self, event):

        self._update_window_dimensions()
        self._update_figure_dimensions()

        if self._colorbar is not None:
            self._update_colorbar()

    # Updates the bounding box for the image (which dictates how much of the figure is given to the image);
    # necessary whenever the image size or orientation changes, or when the margins change, or when the
    # display size changes. By default the bounding box returned is the one needed to display the
    # image correctly on the current display size and with other options as currently set via menu_options.
    def _update_image_bbox(self, display_dimensions=None, image_dimensions=None, margin_dimensions=None):

        bbox = self._image_bbox(display_dimensions, image_dimensions, margin_dimensions)

        ax = self._image.axes
        ax.set_position(bbox)

    # Adjusts the length of the scrollbars based on the image size vs the window size. Called any time
    # the window is resized or the image size changes.
    def _update_scrollbar_length(self):

        # Retrieve the sizes of the display, the image and the margin
        display_width, display_height = self._display_dimensions()
        image_width, image_height = self._image_dimensions()
        margin_width, margin_height = self._margin_dimensions()

        scrollbars = [{'vertical': self._vert_scrollbar}, {'horizontal': self._horz_scrollbar}]

        # For each scrollbar, update length such that it corresponds to the amount of viewing
        # area available vs. the full size of the image
        for scrollbar in scrollbars:

            scrollbar_type = list(scrollbar.keys())[0]
            position = scrollbar[scrollbar_type].get()

            # Prior to initialization, position of scrollbars is measured differently.
            # Here we set it to a no-scrollbar default such that the measurement is consistent.
            if len(position) > 2:
                position = [0, 1]

            # Calculate new length of the scrollbar
            if scrollbar_type == 'vertical':
                new_length = (display_height - margin_height) / image_height
            else:
                new_length = (display_width - margin_width) / image_width

            if new_length > 1:
                new_length = 1

            # Calculate old scrollbar position sum
            old_position_sum = position[0] + position[1]

            # Find new position of scrollbar, such that zoom is centered on previous image center
            start_offset = old_position_sum / 2 - new_length / 2
            end_offset = start_offset + new_length

            # Protect cases where range ends up not being between 0 and 1.
            # (the difference between the start and end offsets should never be bigger than 1 as returned
            # by the above formulas, but it may not be in the normalized range between 0 and 1)
            if start_offset < 0:
                end_offset += abs(start_offset)
                start_offset = 0

            elif end_offset > 1:
                start_offset -= end_offset - 1
                end_offset = 1

            scrollbar[scrollbar_type].set(start_offset, end_offset)

        # Now that scrollbar size has been adjusted, update displayed image to show the portion
        # corresponding to the new scrollbar size and position
        self._update_scroll_image_display()

    # Called whenever a scrollbar is moved or modified, this method updates axis limits of the image in such
    # a way that the correct portion of the image is displayed for the current scrollbar position
    # (taking into account image orientation, zoom, etc).
    def _update_scroll_image_display(self):

        scrollbars = [{'vertical': self._vert_scrollbar}, {'horizontal': self._horz_scrollbar}]
        ax = self._image.axes

        image_width, image_height = self._image_dimensions(zoom_level=1)

        # For each scrollbar (vertical and horizontal) set axis limits such that the same proportion
        # of the image is displayed as the scrollbar size indicates can fit in the window
        for scrollbar in scrollbars:

            scrollbar_type = list(scrollbar.keys())[0]
            position = scrollbar[scrollbar_type].get()

            if scrollbar_type == 'vertical':

                y_min = image_height - (image_height * position[1])
                y_max = image_height - (image_height * position[0])

                ax.set_ylim(y_min, y_max)

            else:

                x_min = image_width * position[0]
                x_max = image_width * position[1]

                ax.set_xlim(x_min, x_max)

        # Invert X or Y limits to match either display settings or current menu_options values
        self._update_invert_axis(has_default_orientation=True)

    # Updates dimensions of the figure to match the available area to show it, needed any time the window
    # has changed size
    def _update_figure_dimensions(self):

        self._widget.update_idletasks()

        # Freeze the display temporarily so image is not needlessly re-drawn multiple times
        self.freeze_display()

        # Retrieve width and height of the available room to show the image
        width = self._scrollable_canvas.winfo_width()
        height = self._scrollable_canvas.winfo_height()

        # Adjust width or height to account for colorbar
        # (when colorbar should be shown and thus should take up space, but has not been created yet)
        show_colorbar = self.menu_option('show_colorbar')
        colorbar_orient = self.menu_option('colorbar_orient')

        if show_colorbar and (self._colorbar is None):

            if colorbar_orient == 'horizontal':
                height -= Colorbar.HORIZONTAL_HEIGHT
            else:
                width -= Colorbar.VERTICAL_WIDTH

        # Set dimensions for the figure to match available window size for it
        self._figure_canvas.set_dimensions((width, height), type='pixels')

        # Set position/dimension of the image inside the figure to match current display options
        # (taking into account the image's size and the size of the figure in which to show it)
        self._update_zoom()

        # Thaw the display, since it was frozen above
        self.thaw_display()

    # Called when the vertical scrollbar is used, this method calls _scroll() to adjust the scrollbar's
    # position and also calls _update_scroll_image_display()
    def _vertical_scroll(self, action, first_cmd, second_cmd=''):

        self._scroll(self._vert_scrollbar, first_cmd, second_cmd)
        self._update_scroll_image_display()

    # Called when the horizontal scrollbar is used, this method calls _scroll() to adjust the scrollbar's
    # position and also calls _update_scroll_image_display()
    def _horizontal_scroll(self, action, first_cmd, second_cmd=''):

        self._scroll(self._horz_scrollbar, first_cmd, second_cmd)
        self._update_scroll_image_display()

    # Called by _vertical_scroll() and _horizontal_scroll() when any scrollbar is moved, this method
    # adjusts the scrollbar's position to the new position
    @classmethod
    def _scroll(cls, scrollbar, first_cmd, second_cmd):

        # Retrieve scrollbar position
        position = scrollbar.get()
        scrollbar_length = position[1] - position[0]

        # This means scrollbar was dragged; first_cmd = offset
        if second_cmd == '':
            start_pos = float(first_cmd)
            stop_pos = float(first_cmd) + scrollbar_length

            # Prevent scroll beyond upper or left edge
            if start_pos < 0:
                start_pos = 0
                stop_pos = 0 + scrollbar_length

            # Prevent scroll beyond lower or right edge
            if stop_pos > 1:
                start_pos = 1 - scrollbar_length
                stop_pos = 1

            scrollbar.set(start_pos, stop_pos)

        # This means either scrollbar scroll button was clicked, the empty area in the scrollbar was clicked,
        # or the mouse scrollwheel was used; in all cases first_cmd = +n or -n, where n is an integer
        # representing scroll speed; second_cmd = 'pages|units', where pages means scroll entire pages at a
        # time and units is the normal scroll
        else:

            # Empty area in scrollbar was clicked
            if second_cmd == 'pages':

                num_total_steps = 1 / scrollbar_length

                # Clicking in scrollbar empty area generally implies you want a pretty fast scroll,
                # therefore we ensure that the entire area can be scrolled in no more than 100 steps
                if num_total_steps > 100:
                    step = 0.01 * abs(int(first_cmd))

                else:
                    step = scrollbar_length * abs(int(first_cmd))

            # Scrollbar scroll button was clicked or mouse scrollwheel was used
            else:
                step = scrollbar_length / 5 * abs(int(first_cmd))

            if int(first_cmd) > 0:
                # Scroll down or right

                if (position[1] + step) > 1:
                    scrollbar.set(1 - scrollbar_length, 1)
                else:
                    scrollbar.set(position[0] + step, position[1] + step)

            else:
                # Scroll up or left

                if (position[0] - step) < 0:
                    scrollbar.set(0, scrollbar_length)
                else:
                    scrollbar.set(position[0] - step, position[1] - step)

    # Called on mouse wheel scroll action, zooms image in or out
    def _mousewheel_scroll(self, event):

        # A forced update seems to be required on Mac in order to not break scrollbars during
        # quick changes, e.g. on quick zoom changes via mousewheel.
        if platform.system() == 'Darwin':
            self._widget.update()

        # Zoom in
        if event.delta > 0:
            self._zoom('in')

        # Zoom out
        else:
            self._zoom('out')

    # Dialog window to save the image. Saves the full image (adjusted by zoom), and reflects any options
    # set or changed by menu_options.
    def _save_file_box(self):

        # Obtain the current image and margin dimensions
        image_width, image_height = self._image_dimensions()

        # Raise a warning due to Agg limitation, see also:
        # https://github.com/matplotlib/matplotlib/pull/3451.
        # Note that in all of MPL 1.x, even saving as SVG, EPS and PS seems to result in incomplete
        # images. This appears fixed in MPL 2.0+.
        if (image_width > 32767) or (image_height > 32767):
            message = ('Detected attempt to save image that has a dimension exceeding 32767 pixels. \n\n'
                       'Saving such images as PNG or PDF is likely to result in an incomplete image. '
                       'Formats such as SVG, EPS and PS are more likely to produce a correct image. \n\n'
                       'Another alternative is to zoom the image such that its zoomed (and thus saved) size '
                       'is below 32767 pixels.')
            self._issue_warning(message, title='Save Warning', show=True)

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

        # Save the image
        self.save_image(filename)

    # Obtains tick and tick label parameters, which includes the label size, label space/padding between
    # axis and the label, the tick length and tick width. Essentially these all get bigger as the image and
    # display gets bigger. By default the tick parameters given are for the current display size. The
    # `for_save` option is provided when saving the image, because sizes needed for saving are somewhat
    # different than for display.
    def __get_tick_parameters(self, display_dimensions=None, image_dimensions=None, for_save=False):

        # Set display and image dimensions to match current menu_options if none given
        if display_dimensions is None:
            display_dimensions = self._display_dimensions()

        if image_dimensions is None:
            image_dimensions = self._image_dimensions()

        # Obtain display and image dimensions
        display_width, display_height = display_dimensions
        image_width, image_height = image_dimensions

        # Find the minimum dimension, on which all tick parameters will be based.
        # (If image fits on the screen, this is the minimum image dimension. If image does not fit on screen,
        #  then this is the minimum of the display size and the image size.)
        if (image_width > display_width) or (image_height > display_height):
            min_dimension = min(display_width, display_height, min(image_width, image_height))

        else:
            min_dimension = min(image_width, image_height)

        # When saving the image we use a different scaling than when displaying. Otherwise labels come out
        # a little too big when displaying or too small when saving
        if for_save:

            # Label size formula optimized for pixel sizes 200 to 20000 pixels
            label_size = (8 + 0.01282552 * min_dimension + 0.000002798307 * min_dimension ** 2 -
                          0.00000000006412853 * min_dimension ** 3)

        else:

            # Label size formula optimized for normal screen resolutions, and not to take too much
            # of screen space with the label
            label_size = int(math.log(min_dimension / 11.) * 4)

        # Set tick length, width and label padding based on image size
        # (at larger image sizes the ticks become essentially invisible if these parameters use defaults.)
        tick_length = label_size / 2.75
        tick_width = 0.5
        label_pad = 4

        if min_dimension > 800:
            label_pad += min_dimension / 400
            tick_width += min_dimension / 1600

        tick_parameters = {'label_size': label_size, 'label_pad': label_pad,
                           'tick_length': tick_length, 'tick_width': tick_width,}

        return tick_parameters

    def close(self):

        self._slice_data = None
        self._masked_data = None

        if self._image is not None:
            self._image.remove()

        if self._toolbar is not None:
            self._toolbar = None

        if self._figure_canvas is not None:
            self._figure_canvas.destroy()

        if self._colorbar is not None:
            self._colorbar.destroy()

        super(ImageViewWindow, self).close()


class Colorbar(object):
    """ Colorbar class; creates a FigureCanvas for the Colorbar and controls its content """

    VERTICAL_WIDTH = 120
    HORIZONTAL_HEIGHT = 56

    def __init__(self, scrollbar_frame, image, orientation):

        # Instance variables
        self._image = image
        self._orientation = orientation

        self._frame = scrollbar_frame
        self._figure_canvas = None
        self._mpl_colorbar = None
        self._dimensions = None

        # Create the MPL Figure for the colorbar
        colorbar_figure = Figure(facecolor='#F0F0F0')

        # Setup a new axis for the external colorbar (must be sized to allow tick labels in the margins)
        if orientation == 'vertical':
            cax = colorbar_figure.add_axes([0.1, 0.05, 0.2, 0.9])
            direction = 'in'
            pad = 3

        else:
            cax = colorbar_figure.add_axes([0.04, 0.40, 0.92, 0.4])
            direction = 'out'
            pad = 2

        # Create a new FigureCanvas for the Figure
        self._orientation = orientation
        self._format = '%4.2e'

        self._figure_canvas = FigureCanvas(colorbar_figure, master=self._frame)
        self._mpl_colorbar = colorbar_figure.colorbar(image, orientation=orientation, cax=cax, format=self._format)
        self._mpl_colorbar.ax.tick_params(pad=pad, direction=direction)

        # Update colorbar dimensions (in this case setting the colorbar's initial size)
        self._update_dimensions()

        # Pack and draw the figure canvas
        self._figure_canvas.pack()
        self._figure_canvas.draw()

    @property
    def orientation(self):
        return self._orientation

    @property
    def dimensions(self):
        return self._dimensions

    def destroy(self):

        # Remove the colorbar (MPL v1.3 and less do not have .remove method for it)
        try:
            self._mpl_colorbar.remove()
        except AttributeError:
            self._image.colorbar = None

        self._figure_canvas.destroy()

    def update(self, image):

        self._figure_canvas.freeze()
        self._image = image

        # Update norm and colormap of colorbar to match *image* (necessary prior to MPL v3.1)
        try:

            with warnings.catch_warnings():
                warnings.simplefilter('ignore', MPLCompat.DeprecationWarning)
                self._mpl_colorbar.set_norm(image.norm)
                self._mpl_colorbar.set_cmap(image.cmap)

        except AttributeError:
            pass

        # Redraw the colorbar to reflect new image norm and colormap
        self._mpl_colorbar.update_normal(image)
        self._mpl_colorbar.formatter = mpl.ticker.FormatStrFormatter(self._format)

        # Turn off minorticks (necessary after MPL v3.1 for LogNorm)
        try:
            self._mpl_colorbar.minorticks_off()
        except AttributeError:
            pass

        self._update_dimensions()
        self._figure_canvas.thaw()

    def _update_dimensions(self):

        self._frame.update_idletasks()

        if self._orientation == 'vertical':

            scrollable_height = self._frame.winfo_height()
            colorbar_size = (Colorbar.VERTICAL_WIDTH, scrollable_height)

        else:

            scrollable_width = self._frame.winfo_width()
            colorbar_size = (scrollable_width, Colorbar.HORIZONTAL_HEIGHT)

        # Update colorbar dimensions
        self._figure_canvas.set_dimensions(colorbar_size, type='pixels')
        self._dimensions = colorbar_size

        # Update tick number to account for new dimensions
        self._mpl_colorbar.set_ticks(self._get_ticks())

        self._figure_canvas.draw()

    # Returns ticks for colorbar such that spacing between tick marks is equal and the ticks are able to fit
    # in the current window dimensions
    def _get_ticks(self):

        # Obtain the data for which to get the ticks
        array = self._image.get_array()

        norm = self._image.norm
        norm.autoscale_None(array)

        colorbar_size_inches = np.asarray(self.dimensions) / self._figure_canvas.dpi

        # Determine how many tick marks to have (double valued function)
        if self._orientation == 'vertical':
            num_ticks = int(1.5 * colorbar_size_inches[1])

            if num_ticks > 8:
                num_ticks = int(math.log(colorbar_size_inches[1], 1.2))

        else:
            num_ticks = int(0.8 * colorbar_size_inches[0])

            if num_ticks > 8:
                num_ticks = int(math.log(colorbar_size_inches[0], 1.35))

        # Make ticks at even spacial intervals
        edge_remove = 0.12
        ticks = []

        if num_ticks == 1:
            ticks.append(norm.inverse(0.5))

        elif num_ticks > 1:

            increment = (1. / (num_ticks - 1)) * (1. - edge_remove)

            for i in range(0, num_ticks):
                tick_point = ((edge_remove / 2.) + (increment * i))
                ticks.append(norm.inverse(tick_point))

        return ticks


class DataCubeWindow(Window):
    """ Window used to show the data cube for an ImageViewWindow """

    def __init__(self, viewer, image_structure_window):

        # Set initial necessary variables and do other required initialization procedures
        super(DataCubeWindow, self).__init__(viewer)

        # Set the title
        self.set_window_title('{0} - Data Cube'.format(self.get_window_title()))

        # Set the ImageViewWindow for this DataCube as an instance variable
        self._structure_window = image_structure_window

        self._selected_axis = IntVar()
        self._selected_axis.set(self._structure_window.settings['selected_axis'])
        self._add_trace(self._selected_axis, 'w',
                        lambda *args: self._structure_window.select_slice(axis=self._selected_axis.get()))

        self._sliders = []

        # Get the header (containing title of structure)
        structure_name = self._structure_window.structure.id

        header_box = Frame(self._widget, bg=self.get_bg('gray'))
        header_box.pack(anchor='nw', expand=1, fill='x')

        w = Label(header_box, text=structure_name, bg=self.get_bg('gray'))
        w.pack(anchor='center', pady=(5, 0))

        # Create a row for each axes above 2D of ImageViewWindow
        self._sliders_box = Frame(self._widget, bg=self.get_bg('gray'))
        self._sliders_box.pack(anchor='nw', expand=1, fill='x')

        settings = self._structure_window.settings
        axes = settings['axes']

        # In case of a 2D array (e.g. horizontal and vertical axes), create an immovable slider
        num_axes = len(axes)
        has_color = False if axes.find('type', 'color') is None else True

        if (num_axes == 2) or (has_color and num_axes == 3):
            self._create_axis_row(0, '', 0, 0, 0, False)

        # Create sliders for many-dimensional arrays
        else:

            excluded_axes = ('color', 'vertical', 'horizontal')
            slider_axes = [axis for axis in axes if axis['type'] not in excluded_axes]

            # Determine if we need selectors for axes (necessary for cases when there are multiple sliders)
            add_selectors = False
            if len(slider_axes) > 1:
                add_selectors = True

            for i, axis in enumerate(slider_axes):
                self._create_axis_row(i, axis['name'], axis['sequence_number'],
                                      axis['slice'], axis['length'] - 1, add_selectors)

        # Update window to ensure it has taken its final form, then show it
        self._widget.update_idletasks()
        self.show_window()

    # Creates a row to allow changing of slice index for a single axis. Contains a slider for each axis,
    # and if add_selectors is True then a radio button to select the axis
    def _create_axis_row(self, slider_index, axis_name, axis_sequence, axis_slice, max_slice, add_selectors):

            slider_var = IntVar()
            slider_var.set(axis_slice)
            self._add_trace(slider_var, 'w', lambda *args: self._slider_moved(slider_index, axis_sequence))

            slider_row_box = Frame(self._sliders_box, bg=self.get_bg('gray'))
            slider_row_box.pack(pady=(20, 10), expand=1, fill='x')

            # Add axis name and entry for slice index number
            w = Label(slider_row_box, text=axis_name, bg=self.get_bg('gray'))
            w.grid(row=slider_index, column=2, sticky='nw')

            w = Entry(slider_row_box, width=5, justify='center', highlightthickness=0, bd=0, bg='white',
                      textvariable=slider_var)
            w.grid(row=slider_index, column=2)

            # Add selection for the axis
            if add_selectors:
                radiobutton = Radiobutton(slider_row_box, variable=self._selected_axis, value=axis_sequence)
                radiobutton.grid(row=slider_index+1, column=0)

            # Add minimum, maximum and slider to control selected slice index
            w = Label(slider_row_box, text=0, bg=self.get_bg('gray'))
            w.grid(row=slider_index+1, column=1, padx=(10, 5))

            slider = Scale(slider_row_box, from_=0, to=max_slice, length=300, width=15,
                           bg=self.get_bg('gray'), orient='horizontal', showvalue=0, variable=slider_var)

            # Have slider expand/contract on window expansion/contraction
            slider_row_box.grid_columnconfigure(2, weight=1)
            slider.grid(row=slider_index+1, column=2, sticky='nswe')

            w = Label(slider_row_box, text=max_slice, bg=self.get_bg('gray'))
            w.grid(row=slider_index+1, column=3, padx=(5, 10))

            self._sliders.append(slider)

    # Calls the ImageViewWindow to update which frame is displayed
    def _slider_moved(self, slider_index, axis_sequence):

        index = self._sliders[slider_index].get()
        self._structure_window.select_slice(axis=axis_sequence, index=index, save_axis=False)

    def close(self):

        self._structure_window = None
        super(DataCubeWindow, self).close()


class ScaleParametersWindow(Window):
    """ Window used to adjust scale parameters an ImageViewWindow """

    def __init__(self, viewer, image_structure_window, image):

        # Set initial necessary variables and do other required initialization procedures
        super(ScaleParametersWindow, self).__init__(viewer)

        # Set the title
        self.set_window_title("{0} - Scale Parameters".format(self.get_window_title()))

        # Set instance variables for passed in parameters
        self._structure_window = image_structure_window
        self._structure_image = image

        # Set initial window dimensions
        self._settings = {'pixel_init_dimensions': (520, 160), 'dpi': 80}

        # Create the menu options
        menu_options = [
            {'name': 'histogram_range', 'type': StringVar(),  'default': 'full range', 'trace': self._update_histogram},
            {'name': 'scope',           'type': StringVar(),  'default': 'local',      'trace': self._update_scale},
            {'name': 'scale',           'type': StringVar(),
             'default': self._structure_window.menu_option('scale'), 'trace': self._update_scale},
            {'name': 'scale_limits',    'type': StringVar(),
             'default': self._structure_window.menu_option('scale_limits'), 'trace': self._update_scale},
        ]

        for option in menu_options:

            var = option['type']
            self._menu_options[option['name']] = var

            self._add_trace(var, 'w', option['trace'], option['default'])

        # Add the menu
        self._add_menus()

        # Extract a flattened view of the data, removing any NaN and inf
        flat_data = self._structure_window.data.ravel()
        self._histogram_data = flat_data[np.isfinite(flat_data)]

        # Create variables to store current scale limits
        self._scale_min = DoubleVar()
        self._scale_min.set(self._structure_image.norm.vmin)

        self._scale_max = DoubleVar()
        self._scale_max.set(self._structure_image.norm.vmax)

        # Create variables to store displayed vertical line for scale_min and scale_max
        self._min_line = None
        self._max_line = None

        # Create instance variables for a FigureCanvas containing the histogram image, and
        # a frame to store said FigureCanvas in
        self._histogram_frame = None
        self._figure_canvas = None

        # Draw the main window content
        self._draw_content()

        # Add notify event for window resizing
        self._fit_to_content()
        self.show_window()
        self._histogram_frame.bind('<Configure>', self._window_resize)

    # Adds menu options used for manipulating the data display
    def _add_menus(self):

        # Add a File Menu
        file_menu = self._add_menu('File', in_menu='main')
        file_menu.add_command(label='Close', command=self.close)
        file_menu.add_command(label='Close All', command=self._viewer.quit)

        # Add a Scale menu
        scale_menu = self._add_menu('Scale', in_menu='main')
        scale_types = ('linear', 'log', 'squared', 'square root')

        for scale in scale_types:

            # PowerNorm is an MPL feature available in MPL v1.4+ only
            disable_powernorm = {}

            if (MPLCompat.PowerNorm is None) and (scale in ('squared', 'square root')):
                disable_powernorm = {'state': 'disabled'}

            scale_menu.add_checkbutton(label=scale.title(), onvalue=scale, offvalue=scale,
                                       variable=self._menu_options['scale'], **disable_powernorm)

        # Add a Limits menu
        limits_menu = self._add_menu('Limits', in_menu='main')
        scale_limits = ('min max', 'zscale')

        for limit in scale_limits:
            limits_menu.add_checkbutton(label=limit.title(), onvalue=limit, offvalue=limit,
                                        variable=self._menu_options['scale_limits'])

        # Add a Scope menu
        scope_menu = self._add_menu('Scope', in_menu='main')
        scope_options = ('global', 'local')

        for scope in scope_options:
            scope_menu.add_checkbutton(label=scope.title(), onvalue=scope, offvalue=scope,
                                       variable=self._menu_options['scope'])

        # Add a Graph menu
        graph_menu = self._add_menu('Graph', in_menu='main')
        range_options = ('full range', 'current range')

        for graph_range in range_options:
            graph_menu.add_checkbutton(label=graph_range.title(), onvalue=graph_range, offvalue=graph_range,
                                       variable=self._menu_options['histogram_range'])

    # Draws the main content of the window (including the histogram and the buttons)
    def _draw_content(self):

        # Add the histogram title
        w = Label(self._widget, text='Pixel Distribution', font=self.get_font(size=9))
        w.pack(side='top')

        # Add the frame containing the limits entries and the Apply and Close buttons
        bottom_frame = Frame(self._widget)
        bottom_frame.pack(side='bottom', fill='x', anchor='nw', pady=(15, 10))

        limits_frame = Frame(bottom_frame)
        limits_frame.pack(side='top', anchor='nw')

        w = Label(limits_frame, text='Limits')
        w.pack(side='left')

        w = Label(limits_frame, text='Low')
        w.pack(side='left', padx=(10, 5))

        e = Entry(limits_frame, width=12, bg='white', textvariable=self._scale_min)
        e.pack(side='left')

        w = Label(limits_frame, text='High')
        w.pack(side='left', padx=(10, 5))

        e = Entry(limits_frame, width=12, bg='white', textvariable=self._scale_max)
        e.pack(side='left')

        separator = Frame(bottom_frame, relief='raised', borderwidth=1, height=2, bg='gray')
        separator.pack(side='top', fill='x', expand=1, pady=(5, 5))

        buttons_frame = Frame(bottom_frame)
        buttons_frame.pack(side='top', fill='x', expand=1)
        buttons_frame.grid_columnconfigure(0, weight=1)
        buttons_frame.grid_columnconfigure(1, weight=1)
        button_params = {'width': 10, 'font': self.get_font(weight='bold')}

        apply_button = Button(buttons_frame, text='Apply', command=self._apply_limits, **button_params)
        apply_button.grid(row=0, column=0)

        close_button = Button(buttons_frame, text='Close', command=self.close, **button_params)
        close_button.grid(row=0, column=1)

        # Get basic parameters needed for histogram
        dpi = self._settings['dpi']
        initial_fig_size = self._settings['pixel_init_dimensions']
        fig_size = (initial_fig_size[0] / dpi, initial_fig_size[1] / dpi)

        self._histogram_frame = Frame(self._widget)
        self._histogram_frame.pack(side='top', fill='both', expand=1)
        histogram_bg = 'white' if platform.system() == 'Darwin' else self.get_bg()

        figure = Figure(figsize=fig_size, dpi=dpi, facecolor=histogram_bg)
        self._figure_canvas = FigureCanvas(figure, master=self._histogram_frame)

        # Create axes; allow more space if we need to use scientific notation
        abs_max = abs(max(self._histogram_data.min(), self._histogram_data.max(), key=abs))
        rect = [0.1, 0.22, 0.8, 0.71] if (abs_max > 10e6) else [0.1, 0.13, 0.8, 0.80]
        self._figure_canvas.mpl_figure.add_axes(rect)
        self._histogram = None

        # Create histogram, and set histogram's axis limits to span the desired range
        self._update_histogram()

        self._figure_canvas.pack()
        self._figure_canvas.draw()

    # Applies scale limits to image
    def _apply_limits(self):

        scale_min = self._scale_min.get()
        scale_max = self._scale_max.get()

        scale_limits = '{0},{1}'.format(scale_min, scale_max)
        self._menu_options['scale_limits'].set(scale_limits)

    # Updates scale and scale limits in image
    def _update_scale(self, *args):

        # Update scale and limits
        scale = self.menu_option('scale')
        scale_limits = self.menu_option('scale_limits')
        scope = self.menu_option('scope')

        # If scope is global and scale limits are not manual then we need to calculate scale limits
        # for all data and not just the slice being displayed as `set_scale` normally does
        if (scope == 'global') and (',' not in scale_limits):

            if scale_limits == 'zscale':
                zscale_lim = zscale(self._structure_window.data)
                min_x = zscale_lim[0]
                max_x = zscale_lim[1]

            else:
                min_x = self._histogram_data.min()
                max_x = self._histogram_data.max()

            scale_limits = [min_x, max_x]

        self._structure_window.set_scale(scale=scale, limits=scale_limits)

        # Update displayed limits to match image
        norm = self._structure_image.norm
        self._scale_min.set(norm.vmin)
        self._scale_max.set(norm.vmax)

        # Update histogram range to match (if necessary)
        self._update_histogram()

    # Creates or updates histogram, including histogram X-axis range (either show full range,
    # or current range), and sets Y-axis range to min and max.
    def _update_histogram(self, *args):

        histogram_range = self.menu_option('histogram_range')
        histogram_axis = self._figure_canvas.mpl_figure.axes[0]

        # Retrieve currently set scale limits for image/slice
        scale_min_set = self._scale_min.get()
        scale_max_set = self._scale_max.get()

        # Retrieve new X-axis limits for histogram
        if histogram_range == 'full range':
            scale_min = self._histogram_data.min()
            scale_max = self._histogram_data.max()

        elif histogram_range == 'current range':
            scale_min = scale_min_set
            scale_max = scale_max_set

        else:
            raise ValueError('Unknown histogram range: {0}'.format(histogram_range))

        # Adjust scale min and max slightly if equal; having equal axis limits would cause an MPL error
        if scale_min == scale_max:
            scale_min = float(scale_min) - 0.1
            scale_max = float(scale_max) + 0.1

        # Create the histogram if it does not exist, or redraw it if scale limits have changed
        if (self._histogram is None) or not np.isclose(scale_min, self._histogram[1].min()
                                     or not np.isclose(scale_max, self._histogram[1].max())):

            # Clear the histogram axis (otherwise the next ``hist`` command will plot on top of it)
            histogram_axis.cla()

            # Reset vertical min/max lines since histogram was cleared
            self._min_line = None
            self._max_line = None

            # Enable grid, and disable tick marks on top and right sides of plot
            histogram_axis.grid(color='gray', linestyle=':', linewidth=1, axis='y', which='both', alpha=0.45)
            histogram_axis.set_axisbelow(True)
            MPLCompat.axis_set_facecolor(histogram_axis, self._figure_canvas.mpl_figure.get_facecolor())
            histogram_axis.tick_params(direction='out')
            histogram_axis.xaxis.set_ticks_position('bottom')
            histogram_axis.yaxis.set_ticks_position('left')
            histogram_axis.locator_params(axis='x', nbins=5)

            # Draw the histogram
            self._histogram = histogram_axis.hist(self._histogram_data, bins=100,
                                                  range=[scale_min, scale_max], log=True, color='black')

        # Set X-axis limits of histogram to selected range
        # (1% more expansive than needed to exactly fit the data)
        x_min = scale_min - abs((scale_max - scale_min) * 0.01)
        x_max = scale_max + abs((scale_max - scale_min) * 0.01)
        histogram_axis.set_xlim(x_min, x_max)

        # Set X-axis limits of histogram to have 5 ticks at evenly spaced intervals
        interval = (scale_max - scale_min) / 4
        ticks = [scale_min] + [(scale_min + interval*i) for i in range(1, 4)] + [scale_max]
        histogram_axis.set_xticks(ticks)

        # Set y-axis limits to span from a minimum data frequency, where the minimum is forced to at least 1
        # (MPL v1.5 and earlier do not handle log10 ticks well for some cases otherwise) to the maximum of
        # the data frequency
        min_frequency = self._histogram[0].min() if self._histogram[0].min() > 1 else 1
        histogram_axis.set_ylim(min_frequency, self._histogram[0].max())

        # Add vertical lines to histogram signifying currently set scale limits for image/slice
        if self._min_line is None:
            self._min_line = histogram_axis.axvline(x=scale_min_set, color='r', linewidth=2)
        else:
            self._min_line.set_xdata(scale_min_set)

        if self._max_line is None:
            self._max_line = histogram_axis.axvline(x=scale_max_set, color='g', linewidth=2)
        else:
            self._max_line.set_xdata(scale_max_set)

        self._figure_canvas.draw()

    def _window_resize(self, event):

        self._update_window_dimensions()

        fig_size = (self._histogram_frame.winfo_width(), self._histogram_frame.winfo_height())
        self._figure_canvas.set_dimensions(fig_size, type='pixels')

    def close(self):

        self._figure_canvas.destroy()
        self._structure_window = None
        self._structure_image = None
        self._histogram_data = None

        super(ScaleParametersWindow, self).close()


class ZoomPropertiesWindow(Window):
    """ Window used to adjust zoom and aspect ratio for an ImageViewWindow """

    def __init__(self, viewer, image_structure_window):

        # Set initial necessary variables and do other required initialization procedures
        super(ZoomPropertiesWindow, self).__init__(viewer)

        # Set the title
        self.set_window_title('{0} - Zoom Properties'.format(self.get_window_title()))

        # Set the ImageViewWindow to an instance variable
        self._structure_window = image_structure_window

        # Obtain zoom level (try to use integers where the level is a whole number)
        zoom_level = self._structure_window.get_zoom_level()
        for i, level in enumerate(zoom_level):
            if level.is_integer():
                zoom_level[i] = int(level)
            else:
                zoom_level[i] = round(level, 5)

        # Create variables to store current zoom level / aspect ratio
        self._zoom_width = DoubleVar()
        self._zoom_width.set(zoom_level[0])

        self._zoom_height = DoubleVar()
        self._zoom_height.set(zoom_level[1])

        # Draw the main window content
        self._draw_content()

        # Update window to ensure it has taken its final form, then show it
        self._widget.update_idletasks()
        self.show_window()

    # Draws the main content of the window
    def _draw_content(self):

        top_frame = Frame(self._widget)
        top_frame.pack(side='top', padx=10, pady=(10, 0))

        w = Label(top_frame, text='Zoom')
        w.pack(side='left')

        w = Label(top_frame, text='X')
        w.pack(side='left', padx=(10, 5))

        e = Entry(top_frame, width=10, bg='white', textvariable=self._zoom_width)
        e.pack(side='left')

        w = Label(top_frame, text='Y')
        w.pack(side='left', padx=(10, 5))

        e = Entry(top_frame, width=10, bg='white', textvariable=self._zoom_height)
        e.pack(side='left')

        separator = Frame(self._widget, height=2, bd=1, relief='sunken')
        separator.pack(side='top', fill='x', padx=10, pady=15)

        buttons_frame = Frame(self._widget)
        buttons_frame.pack(side='top', anchor='center', pady=(0,10))

        button_params = {'width': 10, 'font': self.get_font(weight='bold')}

        apply_button = Button(buttons_frame, text='Apply', command=self._apply_aspect_ratio, **button_params)
        apply_button.pack(side='left', padx=(0, 5))

        close_button = Button(buttons_frame, text='Close', command=self.close, **button_params)
        close_button.pack(side='left')

    # Applies scale limits to image
    def _apply_aspect_ratio(self):

        zoom_level = [self._zoom_width.get(), self._zoom_height.get()]
        zoom_level_frac = list(map(Fraction, zoom_level))

        self._structure_window.set_zoom(zoom_level_frac, mode='manual')


class _AxesProperties(object):
    """ Helper class containing data about axes being displayed """

    def __init__(self):

        self.axes_properties = []

    def __getitem__(self, index):
        return self.axes_properties[index]

    def __len__(self):
        return len(self.axes_properties)

    def add_axis(self, name, type, sequence_number, slice, length):

        axis_properties = {'name': name,
                           'type': type,
                           'sequence_number': sequence_number,
                           'slice': slice,
                           'length': length}

        self.axes_properties.append(axis_properties)

    # Finds an axis by property key and value
    def find(self, key, value):

        match = next((d for d in self.axes_properties if d[key] == value), None)

        if match is not None:
            match = match.copy()

        return match

    # Finds the index of an axis by property key and value
    def find_index(self, key, value):

        match = next((i for i, d in enumerate(self.axes_properties) if d[key] == value), None)
        return match

    # For axis having index, sets a key and a value
    def set(self, index, key, value):
        self.axes_properties[index][key] = value

    def copy(self):

        axes_properties = _AxesProperties()

        for axis in self.axes_properties:
            axes_properties.add_axis(axis['name'],
                                     axis['type'],
                                     axis['sequence_number'],
                                     axis['slice'],
                                     axis['length'])

        return axes_properties


def open_image(viewer, array_structure):
    """ Open an image view for an ArrayStructure.

    Parameters
    ----------
    viewer : PDS4Viewer
        An instance of PDS4Viewer.
    array_structure : ArrayStructure
        An array structure to visualize as an image.

    Returns
    -------
    ImageViewWindow
        The window instance for image view.

    """

    image_window = ImageViewWindow(viewer)
    image_window.load_array(array_structure)

    return image_window
