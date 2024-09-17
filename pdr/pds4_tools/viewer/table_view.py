from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import platform
import binascii
import functools
import numpy as np
from math import ceil, floor

from .core import DataViewWindow, Window
from .widgets.tooltip import ToolTip
from .widgets.tree import TreeView

from ..reader.table_objects import TableStructure, Meta_Field
from ..reader.data import PDS_array
from ..utils.helpers import is_array_like
from ..utils.logging import logger_init

from ..extern import six
from ..extern.six.moves.tkinter import (Frame, Text, Label, Entry, Button, Scrollbar,
                                        BooleanVar, TclError)

# Initialize the logger
logger = logger_init()

#################################


class TabularViewWindow(DataViewWindow):
    """ Window that displays PDS4 Table data structures as tables.

    This window will display tabular data. After creating it, you should use the open_table() method to load
    the table that it needs to display.
    """

    def __init__(self, viewer):

        # Create basic data view window
        super(TabularViewWindow, self).__init__(viewer)

        # Will be set to the fields for the table structure
        self.data = None

        # Pack the display frame, which contains the scrollbars and the scrollable canvas
        self._display_frame.pack(side='left', anchor='nw', expand=1, fill='both')

        # The window_resize binding adds/removes rows and columns onto the screen based on window size
        self._canvas.bind('<Configure>', self._window_resize)

        # Add notify event for scroll wheel (used to scroll table via scroll wheel)
        self._bind_scroll_event(self._mousewheel_scroll)

        # Menu option variables. These are TKinter type wrappers around standard Python variables. The
        # advantage is that you can use trace(func) on them, to call func whenever one of these variables
        # is changed
        menu_options = [{'name': 'display_data_as_formatted', 'type': BooleanVar(), 'default': True,
                         'trace': lambda *args: self._update_vertical_table_display(self._vert_scrollbar.get())}]

        for option in menu_options:

            var = option['type']
            self._menu_options[option['name']] = var

            self._add_trace(var, 'w', option['trace'], option['default'])

        # These variables are used to store widgets, and info about them, used for displaying tabular data
        self._data_boxes = []
        self._background_boxes = []
        self._deleted_boxes = []

    # Loads the table structure into this window and displays it for the user
    def load_table(self, table_structure):

        # Set a title for the window
        self.set_window_title("{0} - Table '{1}'".format(self.get_window_title(), table_structure.id))

        # Set necessary instance variables for this DataViewWindow
        self.structure = table_structure
        self.data = self.structure.fields
        self.meta_data = table_structure.meta_data if hasattr(table_structure, 'meta_data') else None
        self._settings = {'num_rows': len(self.data[0]), 'num_columns': len(self.data),
                          'num_display_rows': 0, 'display_start_row': 0,
                          'num_display_cols': 0, 'display_start_col': 0}

        # Add vertical scrollbar for the table
        self._vert_scrollbar = Scrollbar(self._display_frame, orient='vertical', command=self._vertical_scroll)
        self._vert_scrollbar.pack(side='right', fill='y')

        # Add horizontal scrollbar for the table
        self._horz_scrollbar = Scrollbar(self._display_frame, orient='horizontal', command=self._horizontal_scroll)
        self._horz_scrollbar.pack(side='bottom', fill='x')

        # Pack the static canvas, which contains the scrollable canvas
        self._static_canvas.pack(side='left', anchor='nw', expand=1, fill='both')

        # Pack the scrollable canvas, which contains the table itself
        self._scrollable_canvas.pack(expand=1, fill='both')

        # Create row count label on left
        box = Frame(self._scrollable_canvas, height=20, width=50)
        box.grid(row=0, column=0, pady=(10, 6), padx=14)

        label = Label(box, text='Row #', font=self.get_font(size=8), bd=0)
        label.pack(fill='both', expand=2)

        # Adds new menu options used for manipulating the data
        self._add_menus()

        # Mark table as open, simulate window resizing to populate the window with the table's data
        self._data_open = True
        self._widget.update_idletasks()
        self._window_resize(None)

    # Sets 'display_data_as_formatted' menu_option to either display_data_as_formatted or display it as
    # unformatted. Updates the on-screen values.
    def set_display_data_format(self, formatted=True):

        self._menu_options['display_data_as_formatted'].set(formatted)
        self._update_vertical_table_display(self._vert_scrollbar.get())

    # Adds menu options used for manipulating the data display
    def _add_menus(self):

        # Add an Options menu
        options_menu = self._add_menu('Options', in_menu='main', index=2)

        # Add a Data Formatting sub-menu to the Options menu
        formatting_menu = self._add_menu('Data formatting', in_menu='Options')

        formatting_menu.add_checkbutton(label='Use field format', onvalue=True, offvalue=False,
                                        variable=self._menu_options['display_data_as_formatted'])

        formatting_menu.add_checkbutton(label='Ignore field format', onvalue=False, offvalue=True,
                                        variable=self._menu_options['display_data_as_formatted'])

        # Add a View menu
        self._add_view_menu()

    # Draws the data from self.data on the screen by adding the appropriate widgets
    #
    # draw_row and draw_col are dictionaries with 'start' and 'stop' values, indicating the physical location
    # of the rows and columns that should be added to the screen. The exception being a row start value of -1,
    # which indicates that the row to add contains the 'column names' header (top row), and a column value
    # of -1 which indicates that the column to add contains the 'row count' (left most column). data_row_offset
    # and data_col_offset are used to indicate the difference between the physical location of the row/column
    # in the table displayed on the screen and the row/column of the data variable that should be used as to
    # pull the value for that physical location (e.g. get_data_point(row + data_row_offset, col + data_col_offset),
    # where row is a value between draw_row's 'start' and 'stop' values) and similar for col).
    def _draw_data(self, draw_row, draw_col, data_row_offset=0, data_col_offset=0):

        # Create column names
        if draw_row['start'] == -1:

            for column in range(draw_col['start'], draw_col['stop']):
                box = Frame(self._scrollable_canvas, height=20)
                box.grid(row=0, column=column + 1, padx=6, pady=(10, 4))

                interior_box = Frame(box, height=18, width=126)
                interior_box.pack()
                interior_box.pack_propagate(False)

                column_name_idx = column + data_col_offset
                column_name = self.data[column_name_idx].meta_data.full_name(skip_parents=True)

                entry = Entry(interior_box, bd=0, highlightthickness=0, font=self.get_font(9, 'bold'),
                              cursor='arrow')
                entry.insert(0, column_name)
                entry.configure(state='readonly')
                entry.pack(fill='both', expand=2)

                self._background_boxes.append({'box': box, 'row': -1, 'col': column})
                self._data_boxes.append({'entry': entry, 'row': -1, 'col': column})

                FieldDefinitionToolTip(self, entry, column)

        # Create row numbers
        if draw_col['start'] == -1:

            for row in range(draw_row['start'], draw_row['stop']):
                border_box = Frame(self._scrollable_canvas, height=20, width=50, background='black')
                border_box.grid(row=row + 1, column=0, padx=6, pady=2)

                interior_box = Frame(border_box, height=18, width=48, background='white')
                interior_box.pack(fill='both', expand=2, padx=1, pady=1)
                interior_box.pack_propagate(False)

                data_row = row + data_row_offset

                entry = Entry(interior_box, bd=0, highlightthickness=0, readonlybackground='white', justify='center')
                entry.insert(0, data_row)
                entry.configure(state='readonly')
                entry.pack(fill='both', expand=2, padx=4)

                self._background_boxes.append({'box': border_box, 'row': row, 'col': -1})
                self._data_boxes.append({'entry': entry, 'row': row, 'col': -1})

        # Create values
        for column in range(draw_col['start'], draw_col['stop']):

            for row in range(draw_row['start'], draw_row['stop']):
                border_box = Frame(self._scrollable_canvas, height=20, width=130, background='black')
                border_box.grid(row=row + 1, column=column + 1, padx=4, pady=2)

                interior_box = Frame(border_box, height=18, width=128, background='white')
                interior_box.pack(fill='both', expand=2, padx=1, pady=1)
                interior_box.pack_propagate(False)

                data_row = row + data_row_offset
                data_column = column + data_col_offset

                entry = Entry(interior_box, bd=0, highlightthickness=0, readonlybackground='white')
                open_table = Button(interior_box, text='Table', font=self.get_font(weight='bold'))

                data_box = {'entry': entry, 'open_table': open_table, 'row': row, 'col': column}
                self._set_data_point_widget(data_row, data_column, data_box)
                entry.configure(state='readonly')

                self._background_boxes.append({'box': border_box, 'row': row, 'col': column})
                self._data_boxes.append(data_box)

    # Erases the appropriate widgets from the screen
    #
    # erase_row and erase_col are dictionaries with 'start' and 'stop' values, indicating the physical
    # location of the rows and columns that should be removed from the table being displayed on the screen
    def _erase_data(self, erase_row, erase_col):

        # Obtain indicies of background boxes (which contain the entries, which contain the data point values)
        # that need to be deleted
        remove_bg_box_idxs = [i for i, data_box in enumerate(self._data_boxes)
                              if erase_row['start'] <= data_box['row'] <= erase_row['stop']
                              if erase_col['start'] <= data_box['col'] <= erase_col['stop']]

        # Remove data boxes that are being deleted from being tracked
        self._data_boxes = [data_box
                            for i, data_box in enumerate(self._data_boxes) if i not in remove_bg_box_idxs]

        # Remove the background boxes that need to be deleted from the screen
        deleted_boxes = []

        for i in range(0, len(remove_bg_box_idxs)):
            box = self._background_boxes[remove_bg_box_idxs[i]]
            deleted_boxes.append(box)
            box['box'].grid_forget()

        # Ideally we could use .destroy() in the above method, instead of .grid_forget(). However, at least
        # on Windows, calling destroy() seems to lead TK to call the widget's (Toplevel) size configure
        # and tell it to stay the same size as it was when window was initially grabbed to start resizing
        # (therefore the window is immediately resized back to its original size when you make it smaller.)
        # Instead we simply hide the boxes above and delete them only if we have built up too many
        # boxes, and only after waiting 5s (because if we do some immediately then it is done while still
        # resizing and therefore window will resize back to before user grabbed it, which is jarring). Note
        # that the window may temporarily freeze during deletion. Think and test carefully if adjusting
        # this code.
        def destroy_boxes(boxes):
            for i in range(len(boxes) - 1, -1, -1):
                boxes[i]['box'].destroy()
                boxes.remove(boxes[i])

        self._deleted_boxes += deleted_boxes
        if len(self._deleted_boxes) > 750:
            self._widget.after(5000, lambda *args: destroy_boxes(self._deleted_boxes))

        # Remove the background boxes that were deleted from being tracked
        for box in deleted_boxes:
            self._background_boxes.remove(box)

    # Adjusts the widget controlling what is displayed for the row and column indicies specified to be the
    # contents of data_box. Note that row and column specify the data row and column, the physical location
    # on the screen is data_box[row] and data_box[col]
    def _set_data_point_widget(self, row, column, data_box):

        field = self.data[column]
        data_point = field[row]
        meta_data = field.meta_data

        # Handle case where the data point is another array-like (e.g. this is a multi-dimensional array)
        if is_array_like(data_point) and len(data_point) > 1:

            column_name = meta_data.full_name(skip_parents=True)
            _table = functools.partial(array_like_to_table, data_point, column_name, meta_data['data_type'],
                                       format=meta_data.get('format'),
                                       full_label=self.structure.full_label,
                                       array_label=self.structure.label,
                                       _copy_data=False)

            # Set widget to display the open table button
            data_box['open_table'].configure(command=lambda *args: open_table(self._viewer, _table()))

            data_box['open_table'].pack(ipadx=1)
            data_box['entry'].pack_forget()

        # Handle case where data point is a single scalar value (this is most of the time)
        else:

            # Convert array-like with single value to a scalar
            if is_array_like(data_point) and len(data_point) == 1:
                data_point = data_point[0]

            # Output bit strings as hex values.
            # Note: we ensure dtype has correct length; otherwise trailing null bytes are skipped by NumPy
            if meta_data.data_type().issubtype('BitString'):
                data_point_bytes = np.asarray(data_point, dtype=field.dtype).tobytes()
                data_point = '0x' + binascii.hexlify(data_point_bytes).decode('ascii').upper()

            # Decode byte strings to unicode strings. Done because byte strings with UTF-8 characters cannot be
            # properly formatted, and so that on Python 2 the warning below does not error out if a non-ASCII
            # data value was not able to be formatted.
            elif isinstance(data_point, six.binary_type):
                data_point = data_point.decode('utf-8')

            # Set display values for data points
            # (except masked values, which are skipped altogether as these values should only be empty
            # values inside delimited tables.)
            if data_point is not np.ma.masked:

                # Format scalar value
                if self.menu_option('display_data_as_formatted'):

                    # Skip formatting scaled/offset values, because the PDS4 Standard is ambiguous on whether
                    # field_format is pre- or post- scaling/offset. This can lead into incorrect formatting.
                    is_scaled = meta_data.get('scaling_factor', 1) != 1 or meta_data.get('value_offset', 0) != 0

                    try:

                        if ('format' in meta_data) and (not is_scaled):

                            # Convert from NumPy types into Python native types, otherwise the format statement below
                            # can return the format itself, when format is invalid, rather than raising an exception.
                            if hasattr(data_point, 'item'):
                                data_point = data_point.item()

                            data_point = meta_data['format'] % data_point

                    except (ValueError, TypeError):
                        self._issue_warning("Unable to format value '{0}' into field_format '{1}'; "
                                            "displaying unformatted value"
                                            .format(data_point, meta_data['format']), show=False)

                # Set widget to display the data point value
                data_box['entry'].insert(0, data_point)

            data_box['entry'].pack(fill='both', expand=2, padx=4)
            data_box['open_table'].pack_forget()

    # Called when the vertical scrollbar is used, this method calls _scroll() to adjust the scrollbar's
    # position and also calls _update_vertical_table_display()
    def _vertical_scroll(self, action, first_cmd, second_cmd=''):

        self._scroll(self._vert_scrollbar, first_cmd, second_cmd)
        self._update_vertical_table_display(self._vert_scrollbar.get())

    # Called when the horizontal scrollbar is used, this method calls _scroll() to adjust the scrollbar's
    # position and also calls _update_horizontal_table_display()
    def _horizontal_scroll(self, action, first_cmd, second_cmd=''):

        self._scroll(self._horz_scrollbar, first_cmd, second_cmd)
        self._update_horizontal_table_display(self._horz_scrollbar.get())

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

    # Adjusts the length of the scrollbars based on the total number of rows and columns in the table,
    # versus how many are being displayed. Called any time window is resized.
    def _set_scrollbar_length(self, num_display_rows, num_display_cols):

        scrollbars = [{'vertical': self._vert_scrollbar}, {'horizontal': self._horz_scrollbar}]

        for scrollbar in scrollbars:
            scrollbar_type = list(scrollbar.keys())[0]
            position = scrollbar[scrollbar_type].get()

            start_offset = position[0]

            if scrollbar_type == 'vertical':
                end_offset = start_offset + float(num_display_rows) / self._settings['num_rows']
            else:
                end_offset = start_offset + float(num_display_cols) / self._settings['num_columns']

            if end_offset > 1:
                start_offset -= end_offset - 1
                end_offset = 1

            scrollbar[scrollbar_type].set(start_offset, end_offset)

        self._widget.update_idletasks()

    # Adjusts data values of self._data_boxes (values in boxes being displayed) to match the vertical position
    # the user is currently viewing
    def _update_vertical_table_display(self, position):

        # Get the new display_start_row of the table (once it is updated)
        start_row = int(round(self._settings['num_rows'] * position[0]))

        if (start_row + self._settings['num_display_rows']) > self._settings['num_rows']:
            start_row = self._settings['num_rows'] - self._settings['num_display_rows']

        # Loop over each data box
        for data_box in self._data_boxes:

            # Skip the 'column name' row since it is statically displayed at the top regardless of scrolling,
            # otherwise adjust the entry contents
            if data_box['row'] != -1:

                data_row_idx = data_box['row'] + start_row
                data_col_idx = data_box['col'] + self._settings['display_start_col']

                data_box['entry'].configure(state='normal')
                data_box['entry'].delete(0, 'end')

                # First column is the 'row count' row
                if data_box['col'] == -1:
                    data_box['entry'].insert(0, data_row_idx)

                # All other columns get data from the data table
                else:

                    self._set_data_point_widget(data_row_idx, data_col_idx, data_box)

                data_box['entry'].configure(state='readonly')

        self._settings['display_start_row'] = start_row

    # Adjusts data values of self._data_boxes (values in boxes being displayed) to match the horizontal
    # position the user is currently viewing
    def _update_horizontal_table_display(self, position):

        # Get the new display_start_col of the table (once it is updated)
        start_col = int(round(self._settings['num_columns'] * position[0]))

        if (start_col + self._settings['num_display_cols']) > self._settings['num_columns']:
            start_col = self._settings['num_columns'] - self._settings['num_display_cols']

        # Loop over each entry
        for data_box in self._data_boxes:

            # Skip the 'row count' column since it is statically displayed at the left regardless of
            # scrolling, otherwise adjust the entry contents
            if data_box['col'] != -1:

                data_row_idx = data_box['row'] + self._settings['display_start_row']
                data_col_idx = data_box['col'] + start_col

                data_box['entry'].configure(state='normal')
                data_box['entry'].delete(0, 'end')

                # First row is the 'column names' header row
                if data_box['row'] == -1:
                    column_name = self.data[data_col_idx].meta_data.full_name(skip_parents=True)
                    data_box['entry'].insert(0, column_name)

                # All other rows get data from the data table
                else:
                    self._set_data_point_widget(data_row_idx, data_col_idx, data_box)

                data_box['entry'].configure(state='readonly')

        self._settings['display_start_col'] = start_col

    # Called on mouse wheel scroll action, scrolls window up or down
    def _mousewheel_scroll(self, event):

        event_delta = int(-1 * event.delta)

        if platform.system() != 'Darwin':
            event_delta //= 120

        self._vertical_scroll('scroll', event_delta, 'units')

    # Determine the number of rows and columns that will fit in the viewer (with current window size)
    def _num_fit_rows_columns(self):

        self._widget.update_idletasks()

        # The Display_Frame contains only the table UI elements, meaning exactly what must fit
        # Rows follows the formula: (Display_Frame_Width - Column_Header_Height) / Row_Height
        # Columns follow the formula: (Display_Frame_Width - Row_Count_Width) / Column_Width
        num_display_rows = int(floor((self._scrollable_canvas.winfo_height() - 34) / 24.))
        num_display_cols = int(floor((self._scrollable_canvas.winfo_width() - 62) / 138.))

        if num_display_rows > self._settings['num_rows']:
            num_display_rows = self._settings['num_rows']
        elif num_display_rows < 0:
            num_display_rows = 0

        if num_display_cols > self._settings['num_columns']:
            num_display_cols = self._settings['num_columns']
        elif num_display_cols < 0:
            num_display_cols = 0

        return num_display_rows, num_display_cols

    # Called when the window has been resized, this method calculates which rows and columns are able to fit
    # with-in the new window size and then calls either _draw_data() or _erase_data() to add or remove the
    # appropriate rows/columns
    def _window_resize(self, event):

        self._update_window_dimensions()

        # Do not continue (since we do not need to re-display anything) if no data is displayed
        if not self._data_open:
            return

        # Determine the number of rows and columns that will fit in the viewer (with current window size)
        num_display_rows, num_display_cols = self._num_fit_rows_columns()

        # Determine number of rows/columns missing or extra rows being shown in comparison to what can fit
        num_missing_rows = num_display_rows - self._settings['num_display_rows']
        num_missing_cols = num_display_cols - self._settings['num_display_cols']

        # Calculate start and stop rows/columns for new rows/columns to add
        if num_missing_rows > 0 or num_missing_cols > 0:

            # Row and column offsets which indicate the difference in position of the row or column being
            # added and the position of the value in the data. I.e., a row being added would have the value:
            # value = get_data_point(draw_row['start'] + data_row_offset)
            data_row_offset = self._settings['display_start_row']
            data_column_offset = self._settings['display_start_col']

            # If window has been vertically enlarged, add new rows to fit
            if num_missing_rows > 0:

                draw_row = {'start': self._settings['num_display_rows'],
                            'stop': self._settings['num_display_rows'] + num_missing_rows}

                draw_col = {'start': 0, 'stop': self._settings['num_display_cols']}

                # Special case where we need to add rows at the beginning because user has tried to expand
                # screen after scrolling all the way down
                if data_row_offset + draw_row['stop'] > self._settings['num_rows']:

                    # Erases all rows, except header row, from the screen
                    erase_row = {'start': 0,
                                 'stop': self._settings['num_display_rows']}

                    self._erase_data(erase_row, draw_col)

                    # We start from beginning and add all requested rows
                    draw_row = {'start': 0,
                                'stop': num_display_rows}
                    data_row_offset = self._settings['num_rows'] - num_display_rows

                    # Adjust the display start row to account for the new starting value
                    self._settings['display_start_row'] = data_row_offset

                # Draw additional data rows
                self._settings['num_display_rows'] = num_display_rows
                self._draw_data(draw_row, draw_col, data_row_offset, data_column_offset)

                # Draw additional 'row count' rows if necessary
                row_count_drawn = next((True for data_box in self._data_boxes
                                        if data_box['col'] == -1
                                        if data_box['row'] >= draw_row['stop'] - 1
                                        ), False)
                if not row_count_drawn:
                    self._draw_data(draw_row, {'start': -1, 'stop': -1}, data_row_offset, 0)

            # If window has been horizontally enlarged, add new columns to fit
            if num_missing_cols > 0:

                draw_col = {'start': self._settings['num_display_cols'],
                            'stop': self._settings['num_display_cols'] + num_missing_cols}

                draw_row = {'start': 0, 'stop': self._settings['num_display_rows']}

                # Special case where we need to add columns at the beginning because user has tried to
                # expand screen after scrolling all the way to the right
                if data_column_offset + draw_col['stop'] > self._settings['num_columns']:

                    # Erases all columns, except row count column, from the screen
                    erase_col = {'start': 0,
                                 'stop': self._settings['num_display_cols']}

                    erase_row = {'start': -1,
                                 'stop': self._settings['num_display_rows']}

                    self._erase_data(erase_row, erase_col)

                    # We start from beginning and add all requested columns
                    draw_col = {'start': 0,
                                'stop': num_display_cols}
                    data_column_offset = self._settings['num_columns'] - num_display_cols

                    # Adjust the display start column to account for the new starting value
                    self._settings['display_start_col'] = data_column_offset

                # Draw additional data columns
                self._settings['num_display_cols'] = num_display_cols
                self._draw_data(draw_row, draw_col, data_row_offset, data_column_offset)

                # Draw additional 'column names' row if necessary
                column_names_drawn = next((True for data_box in self._data_boxes
                                           if data_box['row'] == -1
                                           if data_box['col'] >= draw_col['stop'] - 1
                                           ), False)
                if not column_names_drawn:
                    self._draw_data({'start': -1, 'stop': -1}, draw_col, 0, data_column_offset)

        # Calculate start and stop rows/columns for new rows/columns to remove (note that this should
        # not be an elif with adding columns because in rare cases it is possible to result in both
        # the window growing in one dimension and getting smaller in another despite this method
        # expecting to be called each moment the window size is modified; this can happen when the window
        # is resized many times very quickly)
        if num_missing_rows < 0 or num_missing_cols < 0:

            # Window has been vertically shrunk, erase extra rows that are outside the screen
            if num_missing_rows < 0:
                draw_row = {'start': self._settings['num_display_rows'] + num_missing_rows,
                            'stop': self._settings['num_display_rows']}

                draw_col = {'start': -1, 'stop': self._settings['num_display_cols']}

                # Remove extra rows
                self._settings['num_display_rows'] = num_display_rows
                self._erase_data(draw_row, draw_col)

            # Window has been horizontally shrunk, erase extra columns that are outside the screen
            if num_missing_cols < 0:
                draw_col = {'start': self._settings['num_display_cols'] + num_missing_cols,
                            'stop': self._settings['num_display_cols']}

                draw_row = {'start': -1, 'stop': self._settings['num_display_rows']}

                # Remove extra columns
                self._settings['num_display_cols'] = num_display_cols
                self._erase_data(draw_row, draw_col)

        # Adjusts scrollbar length based on new number of rows and columns being displayed
        self._set_scrollbar_length(num_display_rows, num_display_cols)

    def close(self):

        self.data = None
        super(TabularViewWindow, self).close()


class FieldDefinitionToolTip(ToolTip):
    """ A tooltip that pops up on mouse-over of Field name and shows its meta data. """

    def __init__(self, table_structure_window, field_entry, field_physical_idx):

        super(FieldDefinitionToolTip, self).__init__(field_entry, '', delay=300)

        # Set instance variables
        self._structure_window = table_structure_window
        self._field_short_idx = field_physical_idx

    def show_contents(self):

        # Determine the real index of the field this tooltip should be for
        settings = self._structure_window.settings
        column_idx = self._field_short_idx + settings['display_start_col']
        meta_data = self._structure_window.data[column_idx].meta_data

        frame = Frame(self._tip_window, relief='solid', bd=1, bg='#ffffe0')
        frame.pack()

        # Adds `count` method to Text widget, which is broken in Python 2
        def count_bugfix(self, index1, index2, *args):
            args = [self._w, "count"] + ["-" + arg for arg in args] + [index1, index2]
            return self.tk.call(*args)

        Text.count = count_bugfix

        max_line_width = 80
        text_pad = Text(frame, wrap='word', width=max_line_width, relief='flat',
                        highlightthickness=0, bd=0, bg='#ffffe0')

        # Create tree view for meta data inside text_pad
        TreeView(text_pad, meta_data,
                 header_font=Window.get_font(weight='bold'),
                 key_font=Window.get_font(weight='underline'),
                 value_font=Window.get_font(name='monospace'),
                 spacing_font=Window.get_font())

        text_pad.config(state='disabled')
        text_pad.pack(padx=5, pady=(2, 0))

        # Adjust text pad size to fit its content
        text_lines = text_pad.get('1.0', 'end').strip().splitlines()
        width = 0
        height = len(text_lines)

        for i, line in enumerate(text_lines):

            line_width = len(line)

            if line_width > max_line_width:
                width = max_line_width
                height += ceil(line_width / max_line_width) - 1

            elif line_width > width:
                width = line_width + 1

        text_pad.config(width=width, height=height)

        # To set correct tooltip height (one which properly accounts for extra lines due to wordwrap),
        # we must use displaylines. However displaylines is accurate only once width is correctly set
        # and tooltip is drawn, and sometimes not even then.
        try:

            text_pad.update()
            display_height = text_pad.count('1.0', 'end', 'displaylines')

            if height > display_height:
                text_pad.config(height=display_height)

        # Likely due to the count bugfix above, sometimes text_pad is destroyed by the time
        # `count` runs, and this raises an exception.
        except TclError:
            pass


# Transforms array-like data into a TableStructure
def array_like_to_table(array_like, name, data_type, format=None, full_label=None, array_label=None,
                        _copy_data=True):

    # Create a dictionary for a fake Meta_Field, containing only name, data_type (the two things needed to
    # display a field) and format if it exists
    meta_dict = {'name': name,
                 'data_type': data_type}
    if format is not None:
        meta_dict['format'] = format

    array_like = np.asanyarray(array_like)
    array_depth = array_like.ndim

    # Store the new table fields
    fields = []

    # For 1D arrays, we add them as a single field. For 3D arrays, it is likely the array has dimensions
    # something like [time, x, y]. Therefore, instead of displaying [time, x] and opening a table for y for
    # each [time, x], we instead display only table for [time], and store [x,y] as a sub-table for each
    # [time].
    if (array_depth == 1) or (array_depth == 3):
        meta_field = Meta_Field(meta_dict)
        meta_field.shape = array_like.shape
        fields.append(PDS_array(array_like, meta_field))

    # For arrays other than 1D and 3D
    else:

        # Rotate the array such that the first 2 axes are in column-major order (it is assumed the array is
        # coming in as row-major, since PDS4 requires that storage order)
        array_like = array_like.swapaxes(0, 1)

        # Add each column (potentially an array instead of single valued) to the table
        for field_num, field_data in enumerate(array_like):

            meta_field = Meta_Field(meta_dict)
            meta_field['name'] = '{0} : {1}'.format(field_num, meta_field['name'])
            meta_field.shape = field_data.shape

            fields.append(PDS_array(field_data, meta_field))

    # Initialize the TableStructure
    kwargs = {'structure_id': name, 'structure_label': array_label, 'full_label': full_label}

    if _copy_data:
        table_structure = TableStructure.from_fields(fields, no_scale=True, decode_strings=False, **kwargs)

    else:

        # We override the TableStructure class so that some of its typical functionality is retained
        # if we simply assign fields without converting them into a structured ``ndarray``. However this
        # breaks a lot of other typical functionality, such as record access. This is needed to show arrays
        # as tables without copying the data.
        class _TableStructure(TableStructure):
            @property
            def fields(self):
                return self.data

        table_structure = _TableStructure(structure_data=fields, **kwargs)

    return table_structure


def array_structure_to_table(array_structure, _copy_data=True):
    """ Transform an Array Structure to a Table Structure.

    Parameters
    ----------
    array_structure : ArrayStructure
        A PDS4 array structure.
    _copy_data : bool, optional
        If True, data will be input into an structured NumPy array, thus requiring a copy. If False, data
        will be assigned as a list of existing data. However this results in a non-standard TableStructure
        that does not have typical functionality.

    Returns
    -------
    TableStructure
    """

    table_structure = array_like_to_table(array_structure.data, array_structure.id,
                                          array_structure.meta_data['Element_Array']['data_type'],
                                          full_label=array_structure.full_label,
                                          array_label=array_structure.label,
                                          _copy_data=_copy_data)

    return table_structure


def open_table(viewer, table_structure):
    """ Open a table view for a TableStructure.

    Parameters
    ----------
    viewer : PDS4Viewer
        An instance of PDS4Viewer.
    table_structure : TableStructure
        Table structure from which to display.

    Returns
    -------
    TabularViewWindow
        The window instance for table view.
    """

    table_window = TabularViewWindow(viewer)
    table_window.load_table(table_structure)

    return table_window
