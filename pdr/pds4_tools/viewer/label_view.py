from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import abc

from .core import Window, SearchableTextWindowMixIn
from .widgets.tree import TreeView

from ..reader.label_objects import (get_mission_area, get_discipline_area,
                                    get_spectral_characteristics_for_lid, get_display_settings_for_lid)

from ..extern import six
from ..extern.six.moves.tkinter import Text, BooleanVar, StringVar


@six.add_metaclass(abc.ABCMeta)
class LabelWindow(SearchableTextWindowMixIn, Window):
    """ Base class; Window used to display the content of a label """

    def __init__(self, viewer, full_label, structure_label=None, initial_display='full label'):

        # Set initial necessary variables and do other required initialization procedures
        super(LabelWindow, self).__init__(viewer)

        # Set instance variables
        self.full_label = full_label
        self.structure_label = structure_label

        # Stores possibilities of what can be displayed (these are listed in the View menu), 'break' is
        # not a valid option but simply indicates a break in the menu should be where it occurs
        self._display_types = ['full label', 'object label', 'break',
                               'identification area', 'observation area',
                               'discipline area', 'mission area', 'file area', 'break',
                               'display settings', 'spectral characteristics']

        # Stores what display type is currently selected
        display_type = StringVar()
        self._menu_options['display_type'] = display_type
        self._add_trace(display_type, 'w', self._update_label, default=initial_display)

        # Stores whether label is being pretty printed or shown as in the file
        pretty_print = BooleanVar()
        self._menu_options['pretty_print'] = pretty_print
        self._add_trace(pretty_print, 'w', self._update_label, default=True)

        # Draw the main window content
        self._set_heading('Label')
        self._draw_content()

        # Add notify event for scroll wheel (used to scroll via scroll wheel without focus)
        self._bind_scroll_event(self._mousewheel_scroll)

        # Add menu options
        self._add_menus()
        self._center_and_fit_to_content()
        self.show_window()

    # Adds menu options used for manipulating the label display
    def _add_menus(self):

        # Add a File Menu
        file_menu = self._add_menu('File', in_menu='main')
        file_menu.add_command(label='Close', command=self.close)
        file_menu.add_command(label='Close All', command=self._viewer.quit)

        # Add an Edit Menu
        super(LabelWindow, self)._add_menus()

        # Add View Menu
        view_menu = self._add_menu('View', in_menu='main')

        for display_type in self._display_types:

            if display_type == 'break':
                view_menu.add_separator()
                continue

            view_menu.add_checkbutton(label=display_type.title(), onvalue=display_type,
                                      offvalue=display_type,
                                      variable=self._menu_options['display_type'])

            if self._label_for_display_type(display_type) is None:
                view_menu.entryconfig(view_menu.index('last'), state='disabled')

    # Creates text pad
    @abc.abstractmethod
    def _create_text_pad(self, frame):
        return

    # Sets text shown in text pad for specified label
    @abc.abstractmethod
    def _set_label(self, label):
        return

    # Updates current display to show selected label (based on display type)
    def _update_label(self, *args):

        display_type = self.menu_option('display_type')

        label = self._label_for_display_type(display_type)
        self._set_label(label)

    # Obtain the correct label based on the label display type, or None if there is no available label
    def _label_for_display_type(self, display_type):

        object_lid = None
        if self.structure_label is not None:
            object_lid = self.structure_label.findtext('local_identifier')

        # Retrieve non-structure sections of labels to show, if requested
        label = {'full label':          self.full_label,
                 'identification area': self.full_label.find('Identification_Area'),
                 'observation area':    self.full_label.find('Observation_Area'),
                 'discipline area':     get_discipline_area(self.full_label),
                 'mission area':        get_mission_area(self.full_label),
                 }.get(display_type)

        # Retrieve File_Area_* portion of labels to show, if requested
        if display_type == 'file area':

            label = self.full_label.copy()
            for child in list(label):
                if not child.tag.startswith('File_Area'):
                    for bool_ in [True, False]:
                        label.getroot(unmodified=bool_).remove(child.getroot(unmodified=bool_))

            if len(label) == 0:
                label = None
            elif len(label) == 1:
                label = label[0]

        # Retrieve structure-specific sections of labels to show, if requested
        elif (label is None) and (self.structure_label is not None):

            label = {'object label':             self.structure_label,
                     'display settings':         get_display_settings_for_lid(object_lid, self.full_label),
                     'spectral characteristics': get_spectral_characteristics_for_lid(object_lid, self.full_label),
                     }.get(display_type)

        return label


class LabelTreeViewWindow(LabelWindow):
    """ Window used to display the content of a label as a TreeView """

    def __init__(self, viewer, full_label, structure_label=None, initial_display='full label'):

        # Set initial necessary variables and do other required initialization procedures
        super(LabelTreeViewWindow, self).__init__(viewer, full_label, structure_label,
                                                  initial_display=initial_display)

        # Set a title for the window
        self.set_window_title("{0} - Label View".format(self._widget.title()))

        # TreeView object, which manages the text pad used to display the label
        self._tree_view = None

        # Display initial label content
        self._update_label()

    # Adds menu options used for manipulating the label display
    def _add_menus(self):

        super(LabelTreeViewWindow, self)._add_menus()

        # Append to View menu
        view_menu = self._menu('View')
        view_menu.add_separator()

        view_menu.add_command(label='Show XML Label', command=lambda:
        open_label(self._viewer, self.full_label, self.structure_label,
                   initial_display=self.menu_option('display_type'), type='xml'))

    # Create TreeView of the label, which has the text pad
    def _create_text_pad(self, frame):
        self._text_pad = Text(frame, width=100, height=30, wrap='none', relief='flat',
                              highlightthickness=0, bd=0, bg='white')

    # Sets text shown in text pad
    def _set_label(self, label):

        label_dict = label.to_dict()

        # Delete top-level attributes of a full label (e.g. those of Product_Observational)
        if self.menu_option('display_type') == 'full label':

            values = list(label_dict.values())[0]
            for key in values:
                if key[0] == '@':
                    del values[key]
                    break

        # Clear any existing text in the text pad
        self._set_text('')

        # Create the TreeView for label
        self._tree_view = TreeView(self._text_pad, label_dict,
                                   header_font=self.get_font(weight='bold'),
                                   key_font=self.get_font(weight='underline'),
                                   value_font=self.get_font(name='monospace'),
                                   spacing_font=self.get_font())

        # Reset search because the text has changed
        self._reset_search()

    # Searches label for the string in the search box
    def _do_search(self, *args):

        # Search the label
        super(LabelTreeViewWindow, self)._do_search(*args)

        # Do not continue if no results found
        if len(self._search_match_results) == 0:
            return

        matching_result = self._text_pad.tag_ranges('search')

        # Maximize element and any necessary parents of element such that result can be seen
        for tag_name in self._text_pad.tag_names(matching_result[0]):
            element = self._tree_view.find_element_by_id(tag_name)

            if element is not None:

                for parent in reversed(element.parents()):
                    parent.maximize()

                break

        # Show the match
        self._text_pad.see(matching_result[1])


class LabelXMLWindow(LabelWindow):
    """ Window used to display the content of a label as XML """

    def __init__(self, viewer, full_label, structure_label=None, initial_display='full label'):

        # Set initial necessary variables and do other required initialization procedures
        super(LabelXMLWindow, self).__init__(viewer, full_label, structure_label,
                                             initial_display=initial_display)

        # Set a title for the window
        self.set_window_title("{0} - Label XML View".format(self._widget.title()))

        # Display initial label content
        self._update_label()

    # Adds menu options used for manipulating the label display
    def _add_menus(self):

        super(LabelXMLWindow, self)._add_menus()

        # Add an Options Menu
        options_menu = self._add_menu('Options', in_menu='main', index='last')

        options_menu.add_checkbutton(label='Format Label', onvalue=True, offvalue=False,
                                     variable=self._menu_options['pretty_print'])
        options_menu.add_checkbutton(label="Initial Label", onvalue=False, offvalue=True,
                                     variable=self._menu_options['pretty_print'])

    def _create_text_pad(self, frame):
        self._text_pad = Text(frame, width=100, height=30, wrap='none', background='white',
                              borderwidth=0, highlightthickness=0)

    # Sets text shown in text pad
    def _set_label(self, label):

        # Retrieve whether label should be formatted or not
        if self.menu_option('pretty_print'):
            label_text = label.to_string(pretty_print=True)
        else:
            label_text = label.to_string(pretty_print=False)

        self._set_text(label_text)


#  Opens a new LabelWindow, either for TreeView or for XMLView
def open_label(viewer, full_label, structure_label=None, initial_display=None, type='tree'):

    args = [viewer, full_label]
    kwargs = {'structure_label': structure_label, 'initial_display': initial_display}

    if type == 'tree':
        label_view = LabelTreeViewWindow(*args, **kwargs)

    else:
        label_view = LabelXMLWindow(*args, **kwargs)

    return label_view
