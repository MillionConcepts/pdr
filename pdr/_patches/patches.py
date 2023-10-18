import atexit
from pathlib import Path
import shutil
import site


SIX_PATH = Path(site.getsitepackages()[0]) / 'pds4_tools/extern/six.py'


def replace_pds4_tools_six():
    try:
        shutil.copyfile(Path(__file__).parent / 'six_old.py', SIX_PATH)
    except FileNotFoundError:
        pass


def patch_pds4_tools_six():
    shutil.copyfile(SIX_PATH, Path(__file__).parent / 'six_old.py')
    shutil.copyfile(Path(__file__).parent / 'six_new.py', SIX_PATH)
    atexit.register(replace_pds4_tools_six)
