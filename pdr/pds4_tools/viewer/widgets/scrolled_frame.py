from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from ...extern.six.moves.tkinter import Canvas, Frame, Scrollbar


class ScrolledFrame(Frame):
    """ A frame with optional scrollbars.

    Supports Python 2.6, 2.7 and 3+.

    Parameters
    ----------
    master
        Parent widget for this ScrolledFrame.
    vscrollmode : str, unicode or None
        Vertical scrollbar mode; 'static' means the scrollbar is always visible, 'dynamic' means
        the scrollbar is visible only when necessary, 'none' or None means the scrollbar is not displayed.
    hscrollmode : str, unicode or None
        Horizontal scrollbar mode; 'static' means the scrollbar is always visible, 'dynamic' means
        the scrollbar is visible only when necessary, 'none' or None means the scrollbar is not displayed.
    *args
        Variable length argument list, passed to Frame.
    **kwargs
        Arbitrary keyword arguments, passed to Frame.
    """

    def __init__(self, master=None, vscrollmode='static', hscrollmode='static', *args, **kw):
        Frame.__init__(self, master, *args, **kw)

        if vscrollmode not in ('static', 'dynamic', 'none', None):
            raise ValueError('Unknown vscrollmode: {0}'.format(vscrollmode))

        if hscrollmode not in ('static', 'dynamic', 'none', None):
            raise ValueError('Unknown hscrollmode: {0}'.format(hscrollmode))

        # Create a Canvas, which will contain the scrollbars and the interior/scrolled frame
        self.canvas = canvas = Canvas(self, bd=0, highlightthickness=0)
        canvas.pack(fill='both', expand=1)

        # The interior/scrolled frame, which will contain the widgets to be scrolled
        self.interior = interior = Frame(canvas)
        canvas.create_window((0, 0), window=interior, anchor='nw')

        # Frames to hold the vertical and horizontal scrollbars (if they will be shown)
        vert_frame = Frame(canvas)
        horz_frame = Frame(canvas)

        # Add vertical scrollbar if requested
        if vscrollmode in ('static', 'dynamic'):
            vert_scrollbar = Scrollbar(vert_frame, orient='vertical', command=canvas.yview)
            vert_scrollbar.pack(side='right', fill='y')
            canvas.config(yscrollcommand=vert_scrollbar.set)

        # Add horizontal scrollbar if requested
        if hscrollmode in ('static', 'dynamic'):
            horz_scrollbar = Scrollbar(horz_frame, orient='horizontal', command=canvas.xview)
            horz_scrollbar.pack(side='bottom', fill='x')
            canvas.config(xscrollcommand=horz_scrollbar.set)

        def _on_resize(event):

            self.update_idletasks()

            # Update the scrollbars to match the size of the interior frame
            canvas.config(scrollregion=interior.bbox('all'))

            # Hide both vertical and horizontal scrollbars (this ensures that placement
            # of the scrollbars is always correct, i.e. vertical is placed first, followed by
            # horizontal.)
            vert_frame.pack_forget()
            horz_frame.pack_forget()

            # Show or hide vertical scrollbar as needed
            if vscrollmode == 'static' or (vscrollmode == 'dynamic' and self.can_vert_scroll()):
               vert_frame.pack(side='right', fill='y')

            # Show or hide horizontal scrollbar as needed
            if hscrollmode == 'static' or (hscrollmode == 'dynamic' and self.can_horz_scroll()):
                horz_frame.pack(side='bottom', fill='x')

        canvas.bind('<Configure>', _on_resize)

    # Returns True if there is room to scroll horizontally, false otherwise
    def can_horz_scroll(self):

        # Detect width of frame being shown vs width needed to fit all items in frame
        actual_width = self.canvas.winfo_width()
        needed_width = self.interior.winfo_reqwidth()

        # Show the scrollbar if there are more structures than can fit in window
        if needed_width > actual_width:
            return True

        return False

    # Returns True if there is room to scroll vertically, false otherwise
    def can_vert_scroll(self):

        # Detect height of frame being shown vs height needed to fit all items in frame
        actual_height = self.canvas.winfo_height()
        needed_height = self.interior.winfo_reqheight()

        # Show the scrollbar if there are more structures than can fit in window
        if needed_height > actual_height:
            return True

        return False

    def xview(self, how, *args):
        self.canvas.xview(how, args)

    def xview_moveto(self, fraction):
        self.canvas.xview_moveto(fraction)

    def xview_scroll(self, number, what):
        self.canvas.xview_scroll(number, what)

    def yview(self, how, *args):
        self.canvas.yview(how, args)

    def yview_scroll(self, number, what):
        self.canvas.yview_scroll(number, what)

    def yview_moveto(self, fraction):
        self.canvas.yview_moveto(fraction)

    def destroy(self):

        self.canvas.destroy()
        self.interior.destroy()
        Frame.destroy(self)
