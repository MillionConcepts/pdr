from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import io
import sys
import json
import shutil

from ..utils.logging import logger_init

from ..extern import six, appdirs

# Initialize the logger
logger = logger_init()

#################################


def init_cache():
    """
    Initializes necessary settings for PDS4 Viewer cache.
    These should be initialized as early as possible into the Viewer startup sequence.

    Currently the cache is used to persist the most recently opened files, the MPL cache and the last
    version of the viewer used. Additionally, when files are opened from a URL, they are temporary
    downloaded into the cache as well.

    Returns
    -------
    None
    """

    # Create cache directory as necessary
    cache_dir = _get_cache_dir()
    if not os.path.isdir(cache_dir):

        try:
            os.mkdir(cache_dir)
        except (OSError, IOError) as e:
            logger.warning('Unable to create cache directory. Cache will not work. '
                           'Received: {0}'.format(str(e)))
            return

    # Set the download cache location to match the Viewer cache location
    os.environ['PDS4TOOLSCACHEDIR'] = cache_dir

    # Set MPL cache
    _set_mpl_cache()

    # Write current version out to cache file
    # (must be done after any checks that depend on knowing last cached version, such as setting MPL cache)
    _write_cache_version()


def get_recently_opened():
    """
    Returns
    -------
    list[str or unicode]
        A list containing the filenames, including the full path, of recent PDS4 labels opened.
        The list is sorted from most recent to least recent.
    """

    cache_data = _get_cache_data()

    return cache_data.get('recently_opened', [])


def write_recently_opened(file_paths, append=True, update_last_open_dir=True):
    """ Writes the file paths given to cache as the most recently opened PDS4 labels.

    Notes
    -----
    This function hardcodes the maximum number of *file_paths* written out to ensure that
    the cache file does not grow out of control.

    Parameters
    ----------
    file_paths : list[str or unicode]
        A list containing the filenames, including the full path, of PDS4 labels. The paths should
        be sorted most recent to least recent.
    append : bool, optional
        If True, the indicated file paths are appended to the cached most recently opened paths.
        For duplicates, only the most recent entries are kept. Defaults to True.
    update_last_open_dir : bool, optional
        If True, the last opened directory is updated to be the directory of the most recently opened
        file. Defaults to True.

    Returns
    -------
    bool
        True if successfully written to file, False if an exception occurred.
    """

    max_files = 10

    # Allow a single file path as a string-like
    if isinstance(file_paths, (six.binary_type, six.text_type)):
        file_paths = [file_paths]

    # Append *file_paths* to previously opened files if requested
    if append:
        file_paths += get_recently_opened()

    # Remove duplicates from file_paths, keeping newer paths closer to the top
    write_file_paths = set()
    write_file_paths = [x for x in file_paths if x not in write_file_paths and not write_file_paths.add(x)]
    write_file_paths = list(write_file_paths)[0:max_files]

    # Update last opened directory if requested
    if update_last_open_dir and len(write_file_paths) > 0:
        write_last_open_dir(os.path.dirname(write_file_paths[0]))

    # Write most recently opened files (up to `max_files`) to cache file
    cache_data = _get_cache_data()
    cache_data['recently_opened'] = write_file_paths
    return _write_cache_data(cache_data)


def get_last_open_dir(if_exists=True):
    """ Reads the last opened/looked at directory from cache file.

    Parameters
    ----------
    if_exists : bool, optional
        If True, and the last open directory no longer exists then None is returned.

    Returns
    -------
    str, unicode or None
        A string containing the path to the last opened or looked at directory. Returns None if
        this is the first time the Viewer is being run or *if_exists* is True and directory does not exist.
    """

    cache_data = _get_cache_data()
    last_open_dir = cache_data.get('last_open_dir')

    if if_exists and (last_open_dir is not None) and (not os.path.exists(last_open_dir)):
        last_open_dir = None

    return last_open_dir


def write_last_open_dir(dir_path):
    """ Writes the directory path given to cache as the most recently opened/looked at directory.

    Parameters
    ----------
    dir_path : str or unicode
        A directory path.

    Returns
    -------
    bool
        True if successfully written to file, False if an exception occurred.
    """

    cache_data = _get_cache_data()
    cache_data['last_open_dir'] = dir_path

    return _write_cache_data(cache_data)


def _get_cache_dir():
    """ Obtain location to store cache files for the Viewer.

    By default, this uses use appdirs to resolve the user's application directory for all OS'. E.g.::

       Windows this usually C:/Users/<username>/AppData/local/<appname>
       Mac this is usually ~/Library/Application Support/<appname>
       Linux this is usually ~/.local/share/<AppName> or XDG defined

    A directory for the viewer cache is made inside the user's application directory.

    The environment variable ``PDS4VIEWERCACHEDIR`` may be used to specify an alternate directory.

    Returns
    -------
    str or unicode
        Path to directory used to store cache files for the Viewer.
    """

    environ_cache_dir = os.environ.get('PDS4VIEWERCACHEDIR')

    if environ_cache_dir:
        cache_dir = environ_cache_dir

    else:
        cache_dir = appdirs.user_data_dir(appname=str('pds4_viewer'), appauthor=False)

    return cache_dir


def _get_cache_data():
    """
    Returns
    -------
    dict
        A dict representation of the JSON in the cache file.
    """

    cache_dir = _get_cache_dir()
    cache_file = os.path.join(cache_dir, 'cache_file')

    try:

        with io.open(cache_file, 'r', encoding='utf-8') as file_handler:
            cache_data = json.load(file_handler)

    except (OSError, IOError) as e:

        logger.warning('Unable to read cache file: {0}'.format(str(e)), max_repeat=1)
        cache_data = {}

    return cache_data


def _write_cache_data(cache_data):
    """ Write cache data to file.

    Parameters
    ----------
    cache_data : dict
        Cache data to write to file. Each key/value pair represents a particular setting to be cached.

    Returns
    -------
    bool
        True if successfully written to file, False if an exception occurred.
    """

    cache_dir = _get_cache_dir()
    cache_file = os.path.join(cache_dir, 'cache_file')

    try:

        with io.open(cache_file, 'w', encoding='utf-8') as file_handler:

            # Python 2's ``json.dump`` has a bug when ensure_ascii is False, where some data turns
            # out as str instead of unicode
            if six.PY2:
                cache_data = json.dumps(cache_data, ensure_ascii=False, encoding='utf-8')
                file_handler.write(unicode(cache_data))

            # Python 3 gets rid of encoding attribute in ``json.dump``, does right thing by default
            else:
                json.dump(cache_data, file_handler, ensure_ascii=False)

    except (OSError, IOError, UnicodeError) as e:

        logger.warning('Unable to write to cache file: {0}'.format(str(e)), max_repeat=1)
        return False

    return True


def _get_current_version():
    """
    Returns
    -------
    str or unicode
        String containing the current version the Viewer.
    """

    return sys.modules['pds4_tools'].__version__


def _get_cache_version():
    """
    Returns
    -------
    str, unicode or None
        String containing the version of the Viewer used the last time it was run. None will result if
        this is the first time it is being run, or if the file storing the last version is inaccessible.
    """

    cache_data = _get_cache_data()

    return cache_data.get('version')


def _write_cache_version():
    """
    Writes a string containing the current version the Viewer to a cache file.

    Returns
    -------
    bool
        True if successfully written to file, False if an exception occurred.
    """

    cache_data = _get_cache_data()
    cache_data['version'] = _get_current_version()

    return _write_cache_data(cache_data)


def _set_mpl_cache():
    """
    Matplotlib has a cache directory. When PDS4 Viewer code is frozen, e.g. via PyInstaller, it would be
    good if this was the same directory each time the application was opened because there is a fair delay
    in creating this cache. This method takes care of ensuring this is the case.

    Notes
    -----
    MPL tries to create aspects of this cache as soon as it believes it's needed, which is often
    as soon as some MPL import is called. Therefore it is wise to set this cache directory early.

    Setting the MPL cache when not frozen is not necessary because MPL will find a reliable place on
    its own. However, when the application is frozen, it is unpacked into a temporary directory on start
    up, and MPL is generally unable to find a reliable place in this circumstance, instead extracting
    inside the temporary directory it's started from. Since this temporary directory may well change unless
    it is fixed, MPL will try to create a new cache directory in a different place.

    Amongst other things, MPL will store a font cache, which includes the physical location of fonts.
    MPL also ships with the fonts it uses by default. Upon trying to locate the necessary fonts, it will
    often find the fonts it ships with. When frozen, these fonts will be located in the temporary directory
    it is extracted to. Therefore, although we may create a permanent place for the cache, it will not be
    correct if the correct font locations change each time the application is run (MPL will automatically
    rebuild its cache if a font location does not exist). To fix this, we also copy matplotlib's fonts to
    the cache directory and instruct it to look there.

    Returns
    -------
    bool or None
        True if successfully set MPL cache, False otherwise. None if setting MPL cache unnecessary.
    """

    # Pinning MPL cache is only necessary when the application is frozen, see docstring
    if not hasattr(sys, 'frozen'):
        return

    # Obtain the cache directory for the Viewer
    app_cache_dir = _get_cache_dir()

    # Obtain the cache directory for MPL (inside the Viewer's cache directory)
    mpl_cache_dir = os.path.join(app_cache_dir, 'mpl-data')

    # Obtain resource directory location for PyInstaller and Py2App respectively
    if hasattr(sys, '_MEIPASS'):
        resource_dir = sys._MEIPASS
    elif 'RESOURCEPATH' in os.environ:
        resource_dir = os.environ['RESOURCEPATH']
    else:
        resource_dir = None

    # Copy mpl-data to cache if necessary and possible. See notes docstring above for why this is necessary.
    # To save time, we copy only if Viewer version has changed since last time mpl-data was copied
    error_occurred = False

    if _get_cache_version() != _get_current_version():

        logger.warning('Copying mpl-data to enable permanent MPL cache. This should only run once, '
                       'on the initial run of each new version of PDS4 Viewer.')

        # Attempt to copy 'mpl-data' to cache
        try:

            if resource_dir is None:
                raise IOError('Unable to determine resource path for Pyinstaller or Py2App.')

            # Frozen location of 'mpl-data'
            mpl_frozen_dir = os.path.join(resource_dir, 'mpl-data')

            if os.path.exists(mpl_cache_dir):
                shutil.rmtree(mpl_cache_dir, ignore_errors=True)

            shutil.copytree(mpl_frozen_dir, mpl_cache_dir)

        except (OSError, IOError, shutil.Error) as e:
            error_occurred = True
            logger.warning('Unable to set MPL datapath. MPL cache may not work. '
                           'Received: {0}'.format(e))

    if not error_occurred:

        # Set environment variable used by MPL to look for config and cache to the above defined cache folder
        os.environ['MPLCONFIGDIR'] = mpl_cache_dir

        # Import matplotlib now that cache dir has been set and mpl-data copied, and set datapath
        import matplotlib as mpl
        mpl.rcParams['datapath'] = mpl_cache_dir

    return not error_occurred
