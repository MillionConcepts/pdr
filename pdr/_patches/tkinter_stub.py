"""
Stub version of tkinter, exposing all the names that pds4_tools.viewer
expects to be available at module load time, allowing pds4_tools to be
imported even if tkinter isn't actually installed.  (tkinter is only
declared as a dependency for the [viewer] feature, but "import pds4_tools"
tries to load part of the viewer component regardless.)
"""

class BooleanVar: pass
class Button: pass
class Canvas: pass
class Checkbutton: pass
class Entry: pass
class Event: pass
class Frame: pass
class Label: pass
class Menu: pass
class PhotoImage: pass
class Scrollbar: pass
class StringVar: pass
class TclError: pass
class Text: pass
class Tk: pass
class Toplevel: pass
