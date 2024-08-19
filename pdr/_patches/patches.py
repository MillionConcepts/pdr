import sys
import importlib.util
from pathlib import Path

def patch_pds4_tools_six():
    # Don't do anything if pds4_tools no longer embeds a copy of six,
    # or if its embedded copy of six works correctly.
    try:
        import pds4_tools
        return
    except ModuleNotFoundError as e:
        if e.name != "pds4_tools.extern.six.moves":
            raise

    target_mod_path = "pds4_tools.extern.six"
    six_new_file_path = Path(__file__).parent / "six_new.py"

    if target_mod_path in sys.modules:
        # The test import above left the bad copy of six in sys.modules
        # and in sys.meta_path; get rid of it.
        del sys.modules[target_mod_path]
        sys.meta_path = [
            importer for importer in sys.meta_path
            if importer.__module__ != target_mod_path
        ]

    # Load our up-to-date 'six_new.py' in place of pds4_tools.extern.six.
    # Its __name__ must be pds4_tools.extern.six from the very beginning
    # so that its custom importer for [pds4_tools.extern.]six.moves works
    # correctly; this is why we cannot just do
    #    from pdr._patches import six_new
    #    sys.modules["pds4_tools.extern.six"] = six_new

    spec_six_new = importlib.util.spec_from_file_location(
        target_mod_path,
        six_new_file_path,
    )
    six_new = importlib.util.module_from_spec(spec_six_new)
    sys.modules[target_mod_path] = six_new
    spec_six_new.loader.exec_module(six_new)

    # and verify that it worked
    import pds4_tools
