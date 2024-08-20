import sys
from importlib import resources, util
from pathlib import Path


__all__ = ["patch_pds4_tools"]


def load_patched_module(mod_path, patched_mod):
    """
    Load the module {patched_mod}, which is a sibling of this
    module, as if it were the module named {mod_path}, which must
    be an absolute module name.

    This helper is necessary because some of the patches we load
    (e.g. an updated copy of `six`) care about what their __name__
    is at load time, so we cannot just do

        from pdr._patches import {patched_mod}
        sys.modules[{mod_path}] = {patched_mod}
    """

    src = resources.files(__package__).joinpath(patched_mod + ".py")
    with resources.as_file(src) as src_path:
        spec = util.spec_from_file_location(mod_path, src_path)
        mod = util.module_from_spec(spec)
        sys.modules[mod_path] = mod
        spec.loader.exec_module(mod)


def patch_outdated_six():
    """
    Replace pds4_tools' bundled copy of `six`, which is outdated
    and doesn't work correctly with Python 3.12, with a good copy
    from our own code.
    """
    six_mod_path = "pds4_tools.extern.six"

    if six_mod_path in sys.modules:
        # Get rid of the bad copy of six.  It installs itself on
        # sys.meta_path as well as in sys.modules.
        del sys.modules[six_mod_path]
        sys.meta_path = [
            importer for importer in sys.meta_path
            if importer.__module__ != six_mod_path
        ]

    load_patched_module(six_mod_path, "six_new")


def patch_missing_tkinter():
    """
    pds4_tools depends on tkinter for its viewer feature; however, in
    1.3 and prior, tkinter must exist for pds4_tools to be importable
    at all.  Inject a stub version of tkinter into sys.modules to mask
    the bug.
    """
    load_patched_module("tkinter", "tkinter_stub")


def patch_pds4_tools(*, force=None):
    """
    Patch pds4_tools to address various reasons why it might fail
    to be importable.  Does nothing if none of the patches are
    required.  You can force a patch to be applied even if it doesn't
    seem necessary by listing it in the "force" argument, which
    accepts either a single string or a list.
    """
    patches = {
        "pds4_tools.extern.six.moves": patch_outdated_six,
        "tkinter": patch_missing_tkinter,
    }

    if force is not None:
        if not isinstance(force, list):
            force = [force]
        for patch in force:
            patches[patch]()
            del patches[patch]

    while True:
        try:
            import pds4_tools
            return
        except ModuleNotFoundError as e:
            if e.name in patches:
                patches[e.name]()
                del patches[e.name] # don't try to apply the same patch twice
            else:
                raise
