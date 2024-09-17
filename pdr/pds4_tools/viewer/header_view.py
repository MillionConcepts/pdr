from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from .core import DataViewWindow, SearchableTextWindowMixIn


class HeaderViewWindow(SearchableTextWindowMixIn, DataViewWindow):
    """ Window used to display character version of PDS4 Header objects. """

    def load_header(self, header_structure):

        # Set a title for the window
        self.set_window_title("{0} - Header '{1}'".format(self.get_window_title(), header_structure.id))

        # Set necessary instance variables for this DataViewWindow
        self.structure = header_structure
        self.meta_data = header_structure.meta_data

        # Change the MixIn's master widget to be the DataViewWindow's static canvas, so all content
        # is drawn inside of it
        self._display_frame.pack(expand=1, fill='both')
        self._static_canvas.pack(expand=1, fill='both')
        self._master = self._static_canvas

        # Add notify event for scroll wheel (used to scroll via scroll wheel without focus)
        self._bind_scroll_event(self._mousewheel_scroll)

        # Draw main window contents
        self._draw_content()

        # Fill the text content
        text = header_structure.parser().to_string()
        self._set_text(text)
        self._set_heading(header_structure.id)

        self._add_menus()
        self._add_view_menu()
        self._data_open = True


def open_header(viewer, header_structure):
    """ Open an image view for an ArrayStructure.

    Parameters
    ----------
    viewer : PDS4Viewer
        An instance of PDS4Viewer.
    header_structure : HeaderStructure
        A parsable header structure to visualize as text.

    Returns
    -------
    HeaderViewWindow
        The window instance for header view.
    """

    header_window = HeaderViewWindow(viewer)
    header_window.load_header(header_structure)

    return header_window
