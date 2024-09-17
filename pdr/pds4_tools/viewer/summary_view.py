from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import io
import math
import binascii
import platform
import functools
import traceback

import numpy as np

from . import label_view, table_view, header_view, cache
from .core import Window, MessageWindow
from .widgets.scrolled_frame import ScrolledFrame
from .widgets.tooltip import ToolTip
from .table_view import array_structure_to_table

from ..reader.core import pds4_read
from ..reader.data import PDS_array
from ..reader.read_tables import table_data_size_check

from ..utils.helpers import is_array_like
from ..utils.logging import logger_init

from ..extern import six
from ..extern.six.moves.tkinter import (Canvas, Frame, Label, Entry, Button, Radiobutton,
                                        BooleanVar, StringVar)
from ..extern.six.moves.tkinter_tkfiledialog import askopenfilename, asksaveasfilename

# Initialize the logger
logger = logger_init()

#################################


class StructureListWindow(Window):
    """ Window that summarizes the structures showing some of their properties and giving buttons to open them """

    def __init__(self, viewer, quiet=False, lazy_load=False, show_headers=False, withdrawn=False):

        # Set initial necessary variables and do other required initialization procedures
        super(StructureListWindow, self).__init__(viewer, withdrawn=withdrawn)

        # Set window width to not be resizable
        self._widget.resizable(width=0, height=1)

        # Initialize structure list window variables
        self._canvas = None
        self._scrolled_frame = None
        self._structure_list = None
        self._label_open = False

        # Create menu
        self._add_menus(quiet, lazy_load, show_headers)

        # Add notify event for scroll wheel (used to scroll structure list)
        self._bind_scroll_event(self._mousewheel_scroll)

    # Opens the label, reads in any structures it contains, calls _draw_summary()
    def open_label(self, filename=None, from_existing_structures=None):

        if (filename is None) and (from_existing_structures is None):
            raise TypeError('Cannot open a label without either a filename or existing StructureList.')

        # Reset the summary if a label is already open
        if self._label_open:
            self.reset()

        # Open the label and data, or show an error if one occurs
        try:

            # Lazy-load all structures from file (to obtain meta data)
            if filename is not None:

                self._structure_list = pds4_read(filename, quiet=self.menu_option('quiet'),
                                                 lazy_load=True, decode_strings=False)

                cache.write_recently_opened(filename)

            # Load (lazy if previously was lazy) structures from existing list
            else:
                self._structure_list = from_existing_structures

            # Set title
            title = 'Data Structure Summary' if len(self._structure_list) > 0 else 'Label'
            title += '' if (filename is None) else " for '{0}'".format(filename)
            self.set_window_title("{0} - {1}".format(self.get_window_title(), title))

        except Exception as e:

            trace = traceback.format_exc()
            if isinstance(trace, six.binary_type):
                trace = trace.decode('utf-8')

            log = logger.get_handler('log_handler').get_recording()
            error = log + '\n' + trace
            MessageWindow(self._viewer, 'An Error Occurred!', error)
            logger.exception('An error occurred during label processing.')

        else:

            # Read data from file (or try to access if it exists) for each structure if lazy-load disabled
            if not self.menu_option('lazy_load'):
                self.reify_structures()

            # Draw the summary window
            self._draw_summary()
            self._label_open = True

    # Read-in the data for all unread structures
    def reify_structures(self):

        # Get list of unread structures
        unread_structures = [structure for structure in self._structure_list if not structure.data_loaded]

        # Inform user about large structures
        large_structures = []
        for structure in unread_structures:

            if structure.is_table() and table_data_size_check(structure, quiet=True):
                large_structures.append(structure)

        if large_structures:
            large_struct_message = 'The following structures: \n\n'

            for structure in large_structures:
                large_struct_message += '{0} structure: {1} \n'.format(structure.type, structure.id)

            large_struct_message += (
                '\ncontain a large amount of data. Loading them may take a while. Recommend lazy-load '
                'be enabled via the Options menu.'
            )

            warning_window = self._issue_warning(large_struct_message, log=False, show=True)

        # Read data for all unread structures
        for structure in unread_structures:

            self._reify_structure(structure, size_check=False)

    # Read-in data for a particular structure. Returns False if an error was encountered during reification.
    def _reify_structure(self, structure, size_check=True):

        # Skip reifying structure if it has already been reified
        if structure.data_loaded:
            return True

        # Initialize logging for data read-in
        exception_occurred = False
        logger.get_handler('log_handler').begin_recording()

        # On request and for large, still unread, structures issue a warning message prior to
        # attempting to read-in the data
        warning_window = None
        is_large_table = structure.is_table() and table_data_size_check(structure, quiet=True)

        if size_check and is_large_table:

            message = ("{0} structure '{1}' contains a large amount of data. This process may take "
                       "a while. Loading...".format(structure.type, structure.id))

            warning_window = self._issue_warning(message, log=False, show=True)

        # Read the data for the structure
        try:
            logger.info('Now processing a {0} structure: {1}'.format(structure.type, structure.id))
            structure.data

        except Exception:

            if structure.data_loaded:
                del structure.data

            exception_occurred = True
            logger.exception('An error occurred during data read-in.')

        # Close warning window once loading is finished
        if warning_window:
            warning_window.close()

        # Add logging messages for data read-in to log
        log = logger.get_handler('log_handler').get_recording()
        self._structure_list.read_in_log += log

        # Show errors that occurred on loading
        if exception_occurred:
            MessageWindow(self._viewer, 'An Error Occurred!', log)

        return not exception_occurred

    # Draws a summary of the opened label onto the screen
    def _draw_summary(self):

        # Add View Menu and the Export Menu, if not already done
        if not self._label_open:

            # Add a View menu
            view_menu = self._add_menu('View', in_menu='main')

            view_menu.add_command(label='Full Label', command=self._open_label)

            view_menu.add_command(label='Read-In Log', command=lambda:
                MessageWindow(self._viewer, 'Label/Data Read-in Log', self._structure_list.read_in_log))

            view_menu.add_separator()

            view_menu.add_checkbutton(label='Show Headers', onvalue=True, offvalue=False,
                                      variable=self._menu_options['show_headers'])

            # Add an Export menu
            self._add_menu('Export', in_menu='main', postcommand=self._update_export)

        # Draw summary for structures found
        has_structures = len(self._structure_list) > 0
        all_headers = all(structure.is_header() for structure in self._structure_list)

        if has_structures and (not all_headers or self.menu_option('show_headers')):
            self._draw_structure_summary()

        # Draw summary that shows only the full label if no data structures to display are found
        else:
            self._draw_empty_summary()

    # Draws a summary of the label  of when the StructureList contains supported data structures
    def _draw_structure_summary(self):

        # Shorten the Name column if we only have structures with short names
        structure_names = [structure.id for structure in self._structure_list]
        name_column_size = 200 if len(max(structure_names, key=len)) > 8 else 125

        # Create main canvas (which will contain the header frame, and a structures canvas for the rest)
        self._canvas = Canvas(self._widget, highlightthickness=0)

        # Add the header
        header_frame = Frame(self._canvas, takefocus=False)
        header_frame.pack(side='top', fill='y', expand=0, anchor='nw', pady=(2, 0))

        index = Label(header_frame, text='Index', font=self.get_font(10, 'bold'))
        header_frame.grid_columnconfigure(0, minsize=100)
        index.grid(row=0, column=0)

        name = Label(header_frame, text='Name', font=self.get_font(10, 'bold'))
        header_frame.grid_columnconfigure(1, minsize=name_column_size)
        name.grid(row=0, column=1)

        type = Label(header_frame, text='Type', font=self.get_font(10, 'bold'))
        header_frame.grid_columnconfigure(2, minsize=165)
        type.grid(row=0, column=2)

        dimension = Label(header_frame, text='Dimension', font=self.get_font(10, 'bold'))
        header_frame.grid_columnconfigure(3, minsize=165)
        dimension.grid(row=0, column=3)

        # Create structures frame, which will contain all structure meta data inside it
        self._scrolled_frame = ScrolledFrame(self._canvas, vscrollmode='dynamic', hscrollmode='none')
        self._scrolled_frame.pack(side='bottom', fill='both', expand=1, pady=(12, 0))

        structures_frame = self._scrolled_frame.interior

        # Show structure meta data for each structure
        for i, structure in enumerate(self._structure_list):

            # Skips headers if requested
            if structure.is_header() and not self.menu_option('show_headers'):
                continue

            # Index
            index = Label(structures_frame, text=i, font=self.get_font())
            structures_frame.grid_columnconfigure(0, minsize=100)
            index.grid(row=i, column=0, pady=(2, 7))

            # Name or LID
            name_text = structure.id if (len(structure.id) <= 30) else structure.id[:29] + '...'
            name = Label(structures_frame, text=name_text, font=self.get_font())
            structures_frame.grid_columnconfigure(1, minsize=name_column_size)
            name.grid(row=i, column=1, pady=(2, 7))

            if len(structure.id) > 30:
                ToolTip(name, structure.id)

            # Type
            type = Label(structures_frame, text=structure.type, font=self.get_font())
            structures_frame.grid_columnconfigure(2, minsize=165)
            type.grid(row=i, column=2, pady=(2, 7))

            # Dimensions
            if structure.is_header():
                dimensions_text = '---'

            else:

                dimensions = structure.meta_data.dimensions()

                if structure.is_table():
                    dimensions_text = '{0} cols X {1} rows'.format(dimensions[0], dimensions[1])

                elif structure.is_array():
                    dimensions_text = ' X '.join(
                        six.text_type(dim) for dim in dimensions)

            dimension = Label(structures_frame, text=dimensions_text, font=self.get_font())
            structures_frame.grid_columnconfigure(3, minsize=165)
            dimension.grid(row=i, column=3, pady=(2, 7))

            # Open Data View Buttons
            button_frame = Frame(structures_frame)
            button_frame.grid(row=i, column=4, padx=(30, 40), sticky='w')
            font = self.get_font(weight='bold')

            open_label = functools.partial(self._open_label, i)
            view_label = Button(button_frame, text='Label', font=font, width=7, command=open_label)
            view_label.pack(side='left')

            if _is_tabular(structure):
                open_table = functools.partial(self._open_table, i)
                view_table = Button(button_frame, text='Table', font=font, width=7, command=open_table)
                view_table.pack(side='left')

            if _is_plottable(structure):
                open_plot = functools.partial(self._open_plot, i)
                view_plot = Button(button_frame, text='Plot', font=font, width=7, command=open_plot)
                view_plot.pack(side='left')

            if _is_displayable(structure):
                open_image = functools.partial(self._open_image, i)
                view_image = Button(button_frame, text='Image', font=font, width=7, command=open_image)
                view_image.pack(side='left')

            if _is_parsable_header(structure):
                open_header = functools.partial(self._open_header, i)
                view_header = Button(button_frame, text='Text', font=font, width=7, command=open_header)
                view_header.pack(side='left')

        # Set the width and the initial height of the window
        self._widget.update_idletasks()

        half_screen_height = self._get_screen_size()[1] // 2
        window_height = structures_frame.winfo_height() + header_frame.winfo_reqheight() + 16
        window_width = structures_frame.winfo_reqwidth()

        if window_height > half_screen_height:

            # Find a window height such that it exactly fits the closest number of structures which can
            # fit in half the screen height (i.e. such that no structure fits only part way on the screen)
            possible_heights = [30*i + header_frame.winfo_reqheight() + 16
                                for i in range(0, len(self._structure_list))]
            window_height = min(possible_heights, key=lambda x:abs(x-half_screen_height))

        self.set_window_geometry(window_width, window_height)

        # Add line dividing header and summary data
        self._canvas.create_line(5, 27, window_width - 5, 27)

        # Add the View text header
        view = Label(header_frame, text='View', font=self.get_font(10, 'bold'))
        view_left_pad = math.floor((window_width - 100 - name_column_size - 165 - 165) / 2 - 25)
        view_left_pad = view_left_pad if view_left_pad > 0 else 0
        view.grid(row=0, column=4, padx=(view_left_pad, 0))

        # Once all widgets are added, we pack the canvas. Packing it prior to this can result
        # in ugly resizing and redrawing as widgets are being added above.
        self._canvas.pack(fill='both', expand=1)

    # Draws a summary the label when the StructureList does not contain any supported data structures
    def _draw_empty_summary(self):

        # Create main canvas (which will contain the header frame, and a frame for the label info)
        self._canvas = Canvas(self._widget, highlightthickness=0)

        # Add the header
        header_frame = Frame(self._canvas, takefocus=False)
        header_frame.pack(side='top', fill='y', expand=0, anchor='nw', pady=(2, 0))

        type = Label(header_frame, text='Type', font=self.get_font(10, 'bold'))
        header_frame.grid_columnconfigure(0, minsize=165)
        type.grid(row=0, column=0)

        view = Label(header_frame, text='View', font=self.get_font(10, 'bold'))
        header_frame.grid_columnconfigure(1, minsize=100)
        view.grid(row=0, column=1, padx=(70, 0))

        # Create scrolled frame, which will contain info about the label
        self._scrolled_frame = ScrolledFrame(self._canvas, vscrollmode='dynamic', hscrollmode='none')
        self._scrolled_frame.pack(side='bottom', fill='both', expand=1, pady=(12, 0))

        label_info_frame = self._scrolled_frame.interior

        type = Label(label_info_frame, text=self._structure_list.type, font=self.get_font())
        label_info_frame.grid_columnconfigure(0, minsize=165)
        type.grid(row=0, column=0, pady=(2, 7))

        view_label = Button(label_info_frame, text='Full Label', font=self.get_font(weight='bold'), width=15,
                            command=self._open_label)
        header_frame.grid_columnconfigure(1, minsize=100)
        view_label.grid(row=0, column=1, padx=(30, 10), pady=(2, 7))

        # Set the width and the initial height of the window
        self._widget.update_idletasks()

        window_height = label_info_frame.winfo_height() + header_frame.winfo_reqheight() + 16
        window_width = label_info_frame.winfo_reqwidth()

        self.set_window_geometry(window_width, window_height)

        # Add line dividing header and summary data
        self._canvas.create_line(5, 27, window_width - 5, 27)

        # Once all widgets are added, we pack the canvas. Packing it prior to this can result
        # in ugly resizing and redrawing as widgets are being added above.
        self._canvas.pack(fill='both', expand=1)

    # Opens the label view for a structure
    def _open_label(self, structure_idx=None):

        if structure_idx is None:
            initial_display = 'full label'
            structure_label = None
        else:
            initial_display = 'object label'
            structure_label = self._structure_list[structure_idx].label

        label_view.open_label(self._viewer, self._structure_list.label, structure_label, initial_display)

    # Opens a header view for a structure
    def _open_header(self, structure_idx):

        # Read-in data for the structure if that has not happened already
        structure = self._structure_list[structure_idx]
        reified = self._reify_structure(structure, size_check=True)

        # Do not attempt to open table view if an error was encountered during reification
        if not reified:
            return

        # Open a header view
        if _is_parsable_header(structure):
            header_view.open_header(self._viewer, structure)

        else:
            raise TypeError('Cannot show header view of a non-parsable structure with type ' + structure.type)

    # Opens a table view for a structure
    def _open_table(self, structure_idx):

        # Read-in data for the structure if that has not happened already
        structure = self._structure_list[structure_idx]
        reified = self._reify_structure(structure, size_check=True)

        # Do not attempt to open table view if an error was encountered during reification
        if not reified:
            return

        # Open the table view
        if _is_tabular(structure):

            if structure.is_array():
                structure = array_structure_to_table(structure, _copy_data=False)

            table_view.open_table(self._viewer, structure)

        else:
            raise TypeError('Cannot show table view of structure having type ' + structure.type)

    # Opens a plot view for a structure
    def _open_plot(self, structure_idx):

        # Import plot view; this module requires MPL, so we import it here as opposed to at the top.
        from . import plot_view

        # Read-in data for the structure if that has not happened already
        structure = self._structure_list[structure_idx]
        reified = self._reify_structure(structure, size_check=True)

        # Do not attempt to open plot view if an error was encountered during reification
        if not reified:
            return

        # Open the plot view
        if _is_plottable(structure):

            if structure.is_array():
                structure = array_structure_to_table(structure)

            plot_view.open_plot_column_select(self._viewer, structure)

        else:
            raise TypeError('Cannot show plot of non-plottable structure with type ' + structure.type)

    # Opens an image view for a structure
    def _open_image(self, structure_idx):

        # Import image view; this module requires MPL, so we import it here as opposed to at the top.
        from . import image_view

        # Read-in data for the structure if that has not happened already
        structure = self._structure_list[structure_idx]
        reified = self._reify_structure(structure, size_check=True)

        # Do not attempt to open image view if an error was encountered during reification
        if not reified:
            return

        # Open the image view
        if _is_displayable(structure):
            image_view.open_image(self._viewer, structure)

        else:
            raise TypeError('Cannot show image view of structure having type ' + structure.type)

    # Dialog window to create a new summary view for another label
    def _open_file_box(self, new_window=True):

        # On Linux, the default filetype selected goes first. On Windows it depends on the version of the
        # askopenfilename dialog being used. There is an old bug in Tkinter, at least under Windows 7, where
        # the older Windows dialog is used; and this older dialog also takes the default filetype first, but
        # the newer dialog takes it last. Ultimately this setting for Windows should be based on the system
        # that the frozen distribution is packaged, such that the correct default filetype is first. On Mac
        # adding any type seems to only allow that type to be selected, so we ignore this option.
        if platform.system() == 'Darwin':
            filetypes = []
        else:
            filetypes = [('XML Files', '.xml'), ('All Files', '*')]

        initial_dir = cache.get_last_open_dir(if_exists=True)

        filename = askopenfilename(title='Open Label',
                                   parent=self._widget,
                                   filetypes=filetypes,
                                   initialdir=initial_dir)

        # Check that filename is a string type (some OS' return binary str and some unicode for filename).
        # Also check that it is neither None or empty (also depends on OS)
        if isinstance(filename, (six.binary_type, six.text_type)) and (filename.strip() != ''):

            if new_window:
                open_summary(self._viewer, filename=filename,
                             quiet=self.menu_option('quiet'), lazy_load=self.menu_option('lazy_load'))

            else:
                self.open_label(filename)

    def _add_menus(self, quiet, lazy_load, show_headers):

        # Initialize menu options
        self._menu_options['quiet'] = BooleanVar()
        self._add_trace(self._menu_options['quiet'], 'w', self._update_quiet, default=quiet)

        self._menu_options['lazy_load'] = BooleanVar()
        self._add_trace(self._menu_options['lazy_load'], 'w', self._update_lazy_load, default=lazy_load)

        self._menu_options['show_headers'] = BooleanVar()
        self._add_trace(self._menu_options['show_headers'], 'w', self._update_show_headers, default=show_headers)

        # Add a File menu
        file_menu = self._add_menu('File', in_menu='main')
        file_menu.add_command(label='Open...', command=lambda: self._open_file_box(False))
        file_menu.add_command(label='Open from URL...', command=lambda:
                                self._add_dependent_window(OpenFromURLWindow(self._viewer, self._widget, self)))
        file_menu.add_command(label='Open in New Window...', command=lambda: self._open_file_box(True))
        file_menu.add_separator()

        # Add an Open Recent sub-menu to File menu
        self._add_menu('Open Recent', in_menu='File', postcommand=self._update_recently_opened)

        file_menu.add_separator()
        file_menu.add_command(label='Exit', command=self._viewer.quit)

        # Add an Options menu
        options_menu = self._add_menu('Options', in_menu='main')
        options_menu.add_checkbutton(label='Lazy-Load Data', onvalue=True, offvalue=False,
                                     variable=self._menu_options['lazy_load'])
        options_menu.add_checkbutton(label='Hide Warnings', onvalue=True, offvalue=False,
                                     variable=self._menu_options['quiet'])

    # Updates the logger state to match current menu options value
    def _update_quiet(self, *args):

        if self.menu_option('quiet'):
            logger.quiet()

        else:
            logger.loud()

    # On disable of lazy-load, loads all data immediately
    def _update_lazy_load(self, *args):

        if self._label_open and (not self.menu_option('lazy_load')):
            self.reify_structures()

    # Updates whether Headers structures are shown in the structure summary
    def _update_show_headers(self, *args):

        if not self._label_open:
            return

        self._erase_summary()
        self._draw_summary()

    # Updates the export menu just prior to showing it
    def _update_export(self):

        if not self._label_open:
            return

        # Clear out all existing menu entries
        export_menu = self._menu('Export')
        export_menu.delete(0, export_menu.index('last'))

        # Show export buttons for arrays and tables
        has_export_structures = False

        for structure in self._structure_list:
            if structure.is_array() or structure.is_table():
                has_export_structures = True
                export_menu.add_command(label='{0}...'.format(structure.id[0:29]),
                    command=lambda structure=structure:
                    self._add_dependent_window(DataExportWindow(self._viewer, self._widget, structure)))

        # Handle case when are no supported export structures
        if not has_export_structures:
            export_menu.add_command(label='None', state='disabled')

    # Updates recently opened menu just prior to showing it
    def _update_recently_opened(self):

        recent_paths = cache.get_recently_opened()
        recent_menu = self._menu('Open Recent', in_menu='File')

        # Clear out all existing menu entries
        recent_menu.delete(0, recent_menu.index('last'))

        # Handle case when there are no recently opened files
        if len(recent_paths) == 0:
            recent_menu.add_command(label='None', state='disabled')

        # Show recently opened files
        else:

            for path in recent_paths:
                recent_menu.add_command(label=path, command=lambda path=path: self.open_label(path))

    # Called on mouse wheel scroll action, scrolls structure list up or down if scrollbar is shown
    def _mousewheel_scroll(self, event):

        if (not self._label_open) or (not self._scrolled_frame.can_vert_scroll()):
            return

        event_delta = int(-1 * event.delta)

        if platform.system() != 'Darwin':
            event_delta //= 120

        self._scrolled_frame.yview_scroll(event_delta, 'units')

    # Erases the structure list summary as shown on the screen
    def _erase_summary(self):

        if self._label_open:

            self._scrolled_frame.destroy()
            self._canvas.destroy()

    # Resets the window to a state before any data was opened
    def reset(self):

        if self._label_open:

            self.set_window_title(self.get_window_title().split('-')[0].strip())
            self._remove_menu('View', in_menu='main')
            self._remove_menu('Export', in_menu='main')
            self._erase_summary()
            self._structure_list = None
            self._label_open = False

    def close(self):

        self._structure_list = None
        super(StructureListWindow, self).close()


class OpenFromURLWindow(Window):
    """ Window for entering a remote URL of a label to open. """

    def __init__(self, viewer, master, summary_window):

        # Set initial necessary variables and do other required initialization procedures
        super(OpenFromURLWindow, self).__init__(viewer, withdrawn=True)

        # Set the title
        self.set_window_title('{0} - Open Label from URL'.format(self.get_window_title()))

        # Set OpenFromURLWindow to be transient, meaning it does not show up in the task bar and it stays
        # on top of its master window. This mimics behavior of normal open windows, that ask the path to open,
        # encouraging user to have at most one of these open.
        self._widget.transient(master)

        # Initialize open from URL window variables
        self._summary_window = summary_window

        self._url = StringVar()
        self._url.set('')

        # Draw the main window content
        self._show_content()

        # Update window to ensure it has taken its final form, then show it
        self._widget.update_idletasks()
        self.show_window()

    # Draws the main content of the window
    def _show_content(self):

        # Add URL box
        url_box = Frame(self._widget)
        url_box.pack(anchor='center', padx=45, pady=(20, 10))

        url_label = Label(url_box, text='Enter Label URL:', font=self.get_font(9))
        url_label.pack(anchor='nw', pady=(0, 3))

        url = Entry(url_box, bg='white', bd=0, highlightthickness=1, highlightbackground='gray',
                    width=35, textvariable=self._url)
        url.pack(pady=(0, 10))

        separator = Frame(url_box, height=2, bd=1, relief='sunken')
        separator.pack(side='bottom', fill='x', pady=5)

        # Add buttons to Open / Cancel
        button_box = Frame(self._widget)
        button_box.pack(side='bottom', anchor='ne', padx=45, pady=(0, 20))

        open_button = Button(button_box, bg=self.get_bg(), width=10, text='Open',
                             font=self.get_font(weight='bold'), command=self._open_label)
        open_button.pack(side='left', padx=(0, 5))

        cancel_button = Button(button_box, bg=self.get_bg(), width=10, text='Cancel',
                               font=self.get_font(weight='bold'), command=self.close)
        cancel_button.pack(side='left')

        # Place cursor on URL bar to start
        url.focus()

    # Opens a summary window from a remote URL
    def _open_label(self):

        url = self._url.get().strip()

        if url != '':

            if '://' not in url:
                url = 'http://{0}'.format(url)

            self._summary_window.open_label(url)
            self.close()

    def close(self):

        self._summary_window = None
        super(OpenFromURLWindow, self).close()


class DataExportWindow(Window):
    """ Window used to show export-to-file options for data """

    def __init__(self, viewer, master, structure):

        # Set initial necessary variables and do other required initialization procedures
        super(DataExportWindow, self).__init__(viewer, withdrawn=True)

        # Set the title
        type = 'Array' if structure.is_array() else 'Table'
        self.set_window_title("{0} - Export {1} '{2}'".format(self.get_window_title(), type, structure.id))

        # Set DataExportWindow to be transient, meaning it does not show up in the task bar and it stays
        # on top of its master window. This mimics behavior of normal save windows, that ask where to save,
        # encouraging user to have at most one of these open.
        self._widget.transient(master)

        # Initialize export window variables
        self._structure = structure

        self._output_format = StringVar()

        self._user_delimiter = StringVar()
        self._user_delimiter.set('')

        # Draw the main window content
        self._show_content()

        # Update window to ensure it has taken its final form, then show it
        self._widget.update_idletasks()
        self.show_window()

    # Draws the main content of the window
    def _show_content(self):

        # Add options box, allowing user to select delimiter for output
        options_box = Frame(self._widget)
        options_box.pack(anchor='center', padx=45, pady=(20, 15))

        if self._structure.is_array():

            output_type = 'Values'
            self._output_format.set('space')

            radiobutton = Radiobutton(options_box, text='Space-Separated {0}'.format(output_type),
                                      variable=self._output_format, value='space')
            radiobutton.grid(row=0, column=0, sticky='W')

        else:

            output_type = 'Columns'
            self._output_format.set('fixed')

            radiobutton = Radiobutton(options_box, text='Fixed Width {0}'.format(output_type),
                                      variable=self._output_format, value='fixed')
            radiobutton.grid(row=0, column=0, sticky='W')

        radiobutton = Radiobutton(options_box, text='Comma-Separated {0}'.format(output_type),
                                  variable=self._output_format, value='csv')
        radiobutton.grid(row=1, column=0, sticky='W')

        radiobutton = Radiobutton(options_box, text='Tab-Separated {0}'.format(output_type),
                                  variable=self._output_format, value='tab')
        radiobutton.grid(row=2, column=0, sticky='W')

        radiobutton = Radiobutton(options_box, text='User-Defined Separator: ',
                                  variable=self._output_format, value='user')
        radiobutton.grid(row=3, column=0, sticky='W')

        custom_sep = Entry(options_box, bg='white', bd=0, highlightthickness=1, highlightbackground='gray',
                           width=5, textvariable=self._user_delimiter)
        custom_sep.grid(row=3, column=1, sticky='W', ipadx=2)

        separator = Frame(options_box, height=2, bd=1, relief='sunken')
        separator.grid(row=4, column=0, columnspan=5, sticky='WE', pady=(20, 5))

        # Add buttons to Save / Cancel
        button_box = Frame(self._widget)
        button_box.pack(side='bottom', anchor='center', pady=(0, 20))

        save_button = Button(button_box, bg=self.get_bg(), width=5, text='Save',
                             font=self.get_font(weight='bold'), command=self._save_file_box)
        save_button.pack(side='left', padx=(0, 5))

        cancel_button = Button(button_box, bg=self.get_bg(), width=7, text='Cancel',
                               font=self.get_font(weight='bold'), command=self.close)
        cancel_button.pack(side='left')

    # Dialog window to select where the exported data should be saved
    def _save_file_box(self):

        initial_dir = cache.get_last_open_dir(if_exists=True)

        filename = asksaveasfilename(title='Export Data',
                                     parent=self._widget,
                                     initialdir=initial_dir,
                                     initialfile='Untitled.tab')

        if filename == '' or filename == ():
            return

        cache.write_last_open_dir(os.path.dirname(filename))

        # Export the data
        delimiter = {'fixed': None,
                     'csv': ',',
                     'tab': '\t',
                     'user': self._user_delimiter.get(),
                     }.get(self._output_format.get())

        _export_data(filename, data=self._structure.data, delimiter=delimiter)
        self.close()


def _is_tabular(structure):
    """ Determines if a PDS4 structure can be shown as a table.

    Tabular structures are either:
        (1) Tables, or
        (2) Arrays

    Parameters
    ----------
    structure : Structure
        PDS4 structure to check.

    Returns
    -------
    bool
        True if *structure* can be displayed as a table, False otherwise.
    """

    return structure.is_table() or structure.is_array()


def _is_plottable(structure):
    """ Determines if a PDS4 structure is plottable.

    Plottable structures are either:
        (1) 1D arrays, or
        (2) Tables

    Parameters
    ----------
    structure : Structure
        PDS4 structure to check.

    Returns
    -------
    bool
        True if *structure* can be plotted, False otherwise.
    """

    plottable = False

    if structure.is_table():
        plottable = True

    elif structure.is_array() and structure.meta_data.num_axes() == 1:
        plottable = True

    return plottable


def _is_displayable(structure):
    """ Determines if a PDS4 structure is displayable as an image.

    Displayable structures are PDS4 arrays are those that are either:
        (1) a 2D array, or
        (2) sub-types of Array_2D or Array_3D, or
        (3) have a display dictionary

    Parameters
    ----------
    structure : Structure
        PDS4 structure to check.

    Returns
    -------
    bool
        True if *structure* can be displayed as an image, False otherwise.
    """

    if structure.is_array():

        has_display_dict = structure.meta_data.display_settings is not None
        is_2d_array = structure.meta_data.num_axes() == 2

        if ('Array_2D_' in structure.type) or ('Array_3D_' in structure.type) or is_2d_array or has_display_dict:
            return True

    return False


def _is_parsable_header(structure):
    """ Determines if a PDS4 header structure can be parsed into plain text.

    Header structures that can be displayed as text are:
        (1) Plain-text Headers
        (2) Headers that can be turned into plain-text via a parser

    """

    return structure.is_header() and hasattr(structure.parser(), 'to_string')


def _export_data(filename, data, delimiter=None, fmt=None, newline='\r\n'):
    """ Exports PDS4 data to a text file.

    Notes
    -----
    Supports PDS4 Tables and Arrays.

    This function is not particularly fast, however it is designed to work
    for all PDS4 data.

    Parameters
    ----------
    filename : str or unicode
        The filename, including path, to write the exported output to.
    data : PDS_narray or PDS_marray
        The data to export to file, i.e. the ``structure.data`` attribute.
    delimiter : str or unicode, optional
        The delimiter between each value. Defaults to None, which indicates
        fixed-width output for PDS4 tables, and separated by a single space
        for PDS4 arrays.
    fmt : str, unicode or list[str or unicode], optional
        For PDS4 tables, the format for all, or each, field. For PDS4 arrays,
        the format for data values. Set 'none' to indicate no formatting
        of output values. Defaults to None, which uses the PDS4 field_format
        in the meta data when available.
    newline : str or unicode, optional
        The line separator for each record (row) of a PDS4 table. Defaults to CRLF.
        Has no effect when exporting PDS4 arrays.

    Returns
    -------
    None
    """

    # Formats a single data value according to PDS4 field_format
    def format_value(datum, format, is_bitstring=False, dtype=None):

        if isinstance(datum, six.binary_type):

            # Handle bitstrings
            # (Note: we ensure dtype has correct length; otherwise trailing null bytes are skipped by NumPy)
            if is_bitstring:
                datum_bytes = np.asarray(datum, dtype=dtype).tobytes()
                datum = '0x' + binascii.hexlify(datum_bytes).decode('ascii').upper()

            # Handle strings
            else:
                datum = datum.decode('utf-8')

        # Format datum
        try:

            # Convert from NumPy types into Python native types, otherwise the format statement below
            # can return the format itself, when format is invalid, rather than raising an exception
            if hasattr(datum, 'item'):
                datum = datum.item()

            value = format % datum
        except (ValueError, TypeError):
            value = datum

        return six.text_type(value)

    # Formats a NumPy ndarray to a string; similar to np.array2string's default functionality
    # but does not add newlines to deeply nested arrays
    def format_array(array, format, is_bitstring=False, dtype=None, _top_level=True):

        kwargs = {'format': format,
                  'is_bitstring': is_bitstring,
                  'dtype': dtype}

        output = '['
        for value in array:

            if value.ndim == 0:

                value = format_value(value, **kwargs)

                if np.issubdtype(array.dtype, np.character):
                    output += "'{0}' ".format(value)
                else:
                    output += "{0} ".format(value.strip())

            else:
                output += format_array(value, _top_level=False, **kwargs)

        output = output[:-1] + '] '

        output = output[:-1] if _top_level else output
        return output

    # Ensure input data is a PDS array, and unmask any masked arrays
    data = PDS_array(data, masked=False)

    # Determine if we are dealing with an array or a table
    is_array = False
    is_fixed_width = delimiter is None

    if data.dtype.names is not None:

        fields = [data[name] for name in data.dtype.names]
        bitstring_field_nums = [i for i, field in enumerate(fields)
                                if field.meta_data.data_type().issubtype('BitString')]
        num_fields = len(fields)
        last_field_num = num_fields-1

    else:

        is_array = True
        data = data.reshape(-1)

    # For arrays
    if is_array:

        if delimiter is None:
            delimiter = ' '

        formats = '%s' if (fmt is None or fmt.lower() == 'none') else fmt

    # For tables
    else:

        # Obtain a list of formats for table fields
        if fmt is None:

            formats = []
            for field in fields:

                # Skip formatting scaled/offset values, because the PDS4 Standard is ambiguous on whether
                # field_format is pre- or post- scaling/offset. This can lead into incorrect formatting.
                meta_data = field.meta_data
                is_scaled = meta_data.get('scaling_factor', 1) != 1 or meta_data.get('value_offset', 0) != 0

                format = '%s' if is_scaled else meta_data.get('format', '%s')
                formats.append(format)

        elif isinstance(fmt, six.string_types) and fmt.lower() == 'none':
            formats = ['%s'] * fmt

        elif is_array_like(fmt):

            if len(fmt) == num_fields:
                formats = fmt

            else:
                raise TypeError("Number of formats ({0}), does not match number of fields ({1}).".
                                format(len(fmt), num_fields))

        else:
            formats = [fmt] * num_fields

        # For fixed-width tables, we need to find the proper length of each field (column) such that each
        # column is separated by a single space (spaces part of string values will add to this)
        if is_fixed_width:

            fixed_formats = []
            delimiter = ' '

            for field_num, value in enumerate(fields):

                ndim = value.ndim
                dtype = value.dtype
                kwargs = {'format': formats[field_num],
                          'dtype': dtype,
                          'is_bitstring': field_num in bitstring_field_nums}

                if ndim > 1:
                    value = [format_array(element, **kwargs) for element in value]
                else:
                    value = [format_value(element, **kwargs) for element in value]

                max_length = len(max(value, key=len))
                sign = '-' if np.issubdtype(dtype, np.character) or (ndim > 1) else '+'

                fixed_format = '%{0}{1}s'.format(sign, max_length)
                fixed_formats.append(fixed_format)

    # Write exported output to file for arrays
    if is_array:

        data.tofile(filename, sep=delimiter, format=formats)

    # Write exported output to file for tables
    # Note: ideally np.savetxt would be able to achieve the same output, however it cannot. This
    # steps most critically for it (or more specifically `np.array2string`) adding newlines to highly
    # nested array outputs, resulting in extraneous newlines. Additionally it does not support a formatter
    # function, and it is not clear that it deals gracefully with UTF-8 until NumPy 1.14.
    else:

        with io.open(filename, 'w', newline='', encoding='utf-8') as file_handler:

            # Format and write out data
            for record in data:

                for field_num, value in enumerate(record):

                    # Format the value (either a scalar, or a group field) according to *fmt*
                    kwargs = {'format': formats[field_num],
                              'dtype': fields[field_num].dtype,
                              'is_bitstring': field_num in bitstring_field_nums}

                    if isinstance(value, np.ndarray):
                        output_value = format_array(value, **kwargs)

                    else:
                        output_value = format_value(value, **kwargs)

                    # For fixed-width tables, format the string-value to give the table its fixed width
                    if is_fixed_width:
                        output_value = fixed_formats[field_num] % output_value

                    # Add delimiter following the value
                    if field_num != last_field_num:
                        output_value += delimiter

                    file_handler.write(output_value)

                file_handler.write(newline)


def open_summary(viewer, filename=None, from_existing_structures=None, quiet=False, lazy_load=True):
    """ Open a new structure summary window (for structures found in label).

    Shows a summary of the structures found in the label, letting the appropriate structures be
    opened as a table, plot or image. Also allows label segments and the full label to be examined.

    Parameters
    ----------
    viewer : PDS4Viewer
        An instance of PDS4Viewer.
    filename : str or unicode, optional
        The filename, including full or relative path if necessary, of
        the PDS4 label describing the data to be viewed.
    from_existing_structures : StructureList, optional
        An existing StructureList, as returned by pds4_read(), to view. Takes
        precedence if given together with filename.
    quiet : bool, int or str, optional
        Suppress all info/warnings from being output and displayed. Supports
        log-level style options for more fine grained control. Defaults to False.
    lazy_load : bool, optional
        Do not read-in data of each data structure until attempt to view said
        data structure. Defaults to True.

    Returns
    -------
    StructureListWindow
        The window instance for the structure summary.

    """

    # Create window
    summary_window = StructureListWindow(viewer, quiet=quiet, lazy_load=lazy_load, withdrawn=lazy_load)

    # Open label (if requested)
    if (filename is not None) or (from_existing_structures is not None):
        summary_window.open_label(filename=filename, from_existing_structures=from_existing_structures)

    # Show window
    if lazy_load:
        summary_window.show_window()

    return summary_window
