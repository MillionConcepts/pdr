from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import platform

from ...utils.compat import OrderedDict
from ...extern.six.moves.tkinter import Frame, Button


_BASE = 'raised'
_SELECTED = 'sunken'


class TabBar(Frame):
    """ A bar containing and controlling the tabs of a Notebook-like widget.

     Uses Tabs, which are essentially TK frames, hiding or showing them as needed when the relevant button
     to show the selected Tab is clicked in the tab bar.

     Supports Python 2.6, 2.7 and 3+.
     Adapted from http://code.activestate.com/recipes/577261-python-tkinter-tabs. """

    def __init__(self, master=None, init_name=None):

        Frame.__init__(self, master)

        self.tabs = OrderedDict()
        self.buttons = OrderedDict()
        self.current_tab = None
        self.init_name = init_name

    # Show the tab bar for the first time
    def show(self):

        self.pack(side='top', anchor='nw', fill='x')
        self.switch(self.init_name or self.tabs.keys()[0])

    # Add a tab
    def add(self, tab):

        # Hide the tab on init
        tab.pack_forget()

        # On Macs, the buttons are not fully stylable, and end up squished. To make buttons look
        # more like normal tab buttons, we pad the text slightly and slightly bigger font.
        ipadx = 5 if platform.system() == 'Darwin' else 0
        ipady = 2 if platform.system() == 'Darwin' else 0
        # font = 'TkDefaultFont 14' if platform.system() == 'Darwin' else None

        # Create a button to switch to the tab
        b = Button(self, text=tab.name, bd=1, relief=_BASE, #font=font,
                   command=lambda name=tab.name: self.switch(name))
        b.pack(side='left', ipadx=ipadx, ipady=ipady)

        # Storage the tab and its button
        self.tabs[tab.name] = tab
        self.buttons[tab.name] = b

    # Delete a tab
    def delete(self, tab_name):

        # Delete the currently shown tab, show the next available tab if possible
        if tab_name == self.current_tab:

            self.current_tab = None
            self.tabs[tab_name].pack_forget()
            del self.tabs[tab_name]

            if len(self.tabs) > 0:
                self.switch(self.tabs.keys()[0])

        # Delete a currently hidden tab
        else:
            del self.tabs[tab_name]

        self.buttons[tab_name].pack_forget()
        del self.buttons[tab_name]

    # Switch to a tab
    def switch(self, tab_name):

        # Hide the currently shown tab
        if self.current_tab:
            self.buttons[self.current_tab].config(relief=_BASE)
            self.tabs[self.current_tab].pack_forget()

        # Show the newly selected tab
        self.tabs[tab_name].pack(side='top', fill='both', expand=1)
        self.current_tab = tab_name

        self.buttons[tab_name].config(relief=_SELECTED)

    # Obtain maximum dimensions needed to display the tabs and tab bar
    def dimensions(self):

        self.update_idletasks()

        max_width = 0
        max_height = 0

        for tab_name in self.tabs.keys():

            tab = self.tabs[tab_name]
            button = self.buttons[tab_name]

            width = max(tab.winfo_reqwidth(), button.winfo_reqwidth())
            height = tab.winfo_reqheight() + button.winfo_reqheight()

            if width > max_width:
                max_width = width

            if height > max_height:
                max_height = height

        return max_width, max_height


class Tab(Frame):
    """ Contains the content of a single Tab.

    Used together with TabBar.
    """

    def __init__(self, master, name):

        Frame.__init__(self, master, bd=2, relief='raised')
        self.name = name
