from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from ...extern.six.moves.tkinter import Toplevel, Label, TclError


class ToolTip(object):
    """ A tooltip that popups on mouse-over, and disappears when mouse-out.

    When the mouse hovers over the *widget* for *delay* time (ms), a popup containing the
    string *text* is displayed.

    Supports Python 2.6, 2.7 and 3+.
    Adapted from Python's idlelib module.
    """

    def __init__(self, widget, text, delay=100):

        self._widget = widget
        self._tip_window = None
        self._delay = delay
        self._id = None
        self._x = self._y = 0
        self._id1 = self._widget.bind('<Enter>', self.enter)
        self._id2 = self._widget.bind('<Leave>', self.leave)

        self._text = text

    # On tooltip mouse enter
    def enter(self, event=None):
        self.schedule()

    # On tooltip mouse leave
    def leave(self, event=None):
        self.unschedule()
        self.hide_tip()

    # Schedule showing the tooltip after elapsed time
    def schedule(self):
        self.unschedule()
        self._id = self._widget.after(self._delay, self.show_tip)

    # Unschedule showing the tooltip if it has been scheduled
    def unschedule(self):
        id = self._id
        self._id = None
        if id:
            self._widget.after_cancel(id)

    # Show the tooltip
    def show_tip(self):

        if self._tip_window:
            return

        # The tip window must be completely outside the button;
        # otherwise when the mouse enters the tip window we get
        # a leave event and it disappears, and then we get an enter
        # event and it reappears, and so on forever :-(
        x = self._widget.winfo_rootx() + 20
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 1
        self._tip_window = Toplevel(self._widget)
        self._tip_window.wm_overrideredirect(1)
        self._tip_window.wm_geometry("+%d+%d" % (x, y))

        self.show_contents()

        # Work around bug in Tk 8.5.18+ on OSX
        try:
            self._tip_window.update_idletasks()
            self._tip_window.lift()
        except (TclError, AttributeError):
            pass

    # Contains the contents of the tooltip
    def show_contents(self):
        label = Label(self._tip_window, text=self._text, justify='left',
                      background="#ffffe0", relief='solid', borderwidth=1)
        label.pack()

    # Hide the tooltip if it has been shown
    def hide_tip(self):
        tw = self._tip_window
        self._tip_window = None
        if tw:
            tw.destroy()