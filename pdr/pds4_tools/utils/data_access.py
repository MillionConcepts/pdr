from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import os
import ssl
import atexit
import tempfile

from ..utils.logging import logger_init

from ..extern import six
from ..extern.six.moves import urllib

# Safe import of Certifi
try:
    import certifi
except ImportError:
    certifi = None


# Initialize the logger
logger = logger_init()

#################################


# Used to store URL (keys)and path (values) as temporary cache, then delete
# the downloaded files on Python interpreter exit.
_temp_files = {}


def is_supported_url(string):
    """ Check if a string is a supported URL.

    Parameters
    ----------
    string : str or unicode
        The string to test.

    Returns
    -------
    bool
        True if URL scheme is supported for download (HTTP, HTTPS, FTP); False otherwise.
    """

    url = urllib.parse.urlparse(string)

    return url.scheme.lower() in ['http', 'https', 'ftp', 'file']


def download_file(url, force=False, block_size=65536, timeout=10):
    """ Download a remote file from a URL.

    Files are downloaded into a local cache location, and deleted upon Python interpreter exit.
    Uses `is_supported_url` to determine supported URL schemes.

    Notes
    -----
    The cache location can be customized via the ``PDS4TOOLSCACHEDIR`` environment variable.
    Partially adapted from ``astropy.utils.data.download_file``.

    Parameters
    ----------
    url : str or unicode
        A supported remote URL to download.
    force : bool, optional
        Re-download file even if the URL is already cached. Defaults to None.
    block_size : int, optional
        The block-size of each remote read command, in bytes. Defaults to 64 KB.
    timeout : int, optional
        A timeout in seconds for blocking operations like the connection attempt. Defaults to 10 seconds.

    Returns
    -------
    str or unicode
        Path to the local (cache) location of the downloaded file.
    """

    # Keep a copy of the original URL prior to encoding/decoding
    url_original = url

    # Obtain URL to pass to ``urlopen``; ultimately same location as *url* but may-be encoded/decoded as needed
    # to avoid ``urlopen`` raising exceptions.
    url = _process_url(url)

    # Download the URL when not cached
    if (url not in _temp_files) or force:

        logger.info('Downloading URL: {0} ... '.format(url_original), end='')

        # Use Certifi where available (avoids SSL verification errors on older platforms and some architectures)
        kwargs = {}
        if certifi is not None:

            try:
                kwargs['context'] = ssl.create_default_context(cafile=certifi.where())

            # SSLContext and context argument available from Python 2.7.9+
            except AttributeError:
                pass

        # Open the connection to remote URL (should not download content)
        try:

            try:
                remote = urllib.request.urlopen(url, timeout=timeout, **kwargs)

            # If Certifi is available but received an SSL error, try system default certificates
            except urllib.error.URLError as e:

                if (certifi is not None) and isinstance(e.reason, ssl.SSLError):
                    remote = urllib.request.urlopen(url, timeout=timeout)
                else:
                    raise

        # Improve error message for unexpected errors
        except urllib.error.URLError as e:

            try:
                e.msg = '{0} for URL: {1}'.format(e.msg, url)
            except AttributeError:

                try:
                    e.reason = '{0} for URL: {1}'.format(e.reason, url)
                except AttributeError:
                    pass

            raise six.raise_from(e, None)

        # Obtain size of file to download
        info = remote.info()
        if 'Content-Length' in info:
            try:
                size = int(info['Content-Length'])
            except ValueError:
                size = None
        else:
            size = None

        size_MB = None if (size is None) else size / 1e6

        # Determine whether to show a progress bar
        show_progress_bar = (size_MB is not None) and (size_MB > 1)

        # Open a temporary file, get its path
        file_handler = tempfile.NamedTemporaryFile(prefix='temp_', dir=_get_cache_dir(), delete=False)
        filename = file_handler.name

        # Download the remote URL into a temporary file
        with _ProgressBar(size_MB, unit='MB') as progress_bar:

            try:

                block = remote.read(block_size)
                bytes_read = block_size

                while block:

                    file_handler.write(block)
                    block = remote.read(block_size)
                    bytes_read += block_size

                    if show_progress_bar:

                        line_start = '\n' if (progress_bar.percent_done == 0) else '\r'
                        msg = progress_bar.update(block_size / 1e6)
                        line_end = '\n' if (progress_bar.percent_done == 100) else ''

                        logger.info('{0}{1}'.format(line_start, msg), end=line_end)

                file_handler.close()

                if not show_progress_bar:
                    logger.info('done')

            except BaseException:

                file_handler.close()

                if os.path.exists(filename):
                    os.remove(filename)

                raise

        _temp_files[url] = filename

    # URL is cached, obtain physical location of file on disk
    else:

        filename = _temp_files[url]

    return filename


def clear_download_cache(urls=None):
    """ Clears the data file cache by deleting the local file(s).

    Parameters
    ----------
    urls : list[str or unicode], optional
        If given, a list of URLs to delete from the cache. Defaults to None,
        which deletes all files/URLs from the cache.

    Returns
    -------
    None
    """

    if urls is not None:
        urls = [_process_url(url) for url in urls]

    if _temp_files is not None:

        for url, filename in list(_temp_files.items()):

            if (urls is None) or (url in urls):

                if os.path.exists(filename):
                    os.remove(filename)

                del _temp_files[url]


def _get_cache_dir():
    """ Obtain location to store downloaded files for temporary caching.

    Uses `tempfile.gettempdir` by default. The environment variable
    ``PDS4TOOLSCACHEDIR`` may be used to specify an alternate directory.

    Returns
    -------
    str or unicode
        Path to directory used to store a temporary cache of downloaded files.
    """

    environ_cache_dir = os.environ.get('PDS4TOOLSCACHEDIR')

    if environ_cache_dir:
        cache_dir = environ_cache_dir
    else:
        cache_dir = tempfile.gettempdir()

    return cache_dir


def _process_url(url):
    """ Processes URL to one suitable for use with `urlib`.

    Parameters
    ----------
    url : str or unicode
        A supported remote URL.

    Returns
    -------
    str or unicode
        A URL that points to the same address as *url*, but where the actual string is potentially adjusted
        such that it does not cause errors with `urllib`.
    """

    # URL decode, e.g. in case user is pasting UTF8 URLs from a browser URL bar, which for most
    # popular browsers will encode first
    if six.PY2:
        url = urllib.parse.unquote(url.encode('utf-8')).decode('utf-8')
    else:
        url = urllib.parse.unquote(url)

    # URL encode, necessary for URLs with non-ASCII characters or urllib will raise an Exception.
    # The above combination of decode first (which does nothing if not already encoded) then encode allows us to
    # handle both URLs coming in as decoded and encoded.
    # Note: the underscore methods of `urlsplit` are not private, but rather used for disambiguation; see Python docs.
    url_parsed = urllib.parse.urlparse(url)

    for attrib in url_parsed._fields:

        if (attrib == 'netloc') and (url_parsed.port is not None):
            replace_dict = {attrib: '{0}:{1}'.format(
                                                    urllib.parse.quote(url_parsed.hostname.encode('utf-8')),
                                                    url_parsed.port)}

        else:
            attrib_value = getattr(url_parsed, attrib)
            replace_dict = {attrib: urllib.parse.quote(attrib_value.encode('utf-8'))}

        url_parsed = url_parsed._replace(**replace_dict)

    return urllib.parse.urlunparse(url_parsed)


@atexit.register
def _delete_temp_files():
    """
    Deletes files downloaded on Python interpreter exit.

    Notes
    -----
    This will not work if the process is killed, thus leaving temporary files around.
    Not great, but hopefully a rare occurrence.

    Returns
    -------
    None
    """
    clear_download_cache()


class _ProgressBar(object):
    """ A class to display a progress bar in a console/terminal.

    Adapted from ``astropy.utils.console.ProgressBar``.

    Parameters
    ----------
    total : int or float
        The maximum number of what the progress bar is tracking, i.e. the value when the bar is 100% filled.
    unit : str or unicode, optional
        The unit of what the progress bar is tracking. Defaults to no units, i.e. an empty string.
    output_func : any_function, optional
        A function that takes a str or unicode as input. This function is called to output the current progress
        bar on each update. Defaults to None, which means no output.
    bar_length : int
        The length of the progress bar, in characters. Defaults to 50.
    """

    def __init__(self, total, unit='', output_func=None, bar_length=50):

        self._total = total
        self._current_value = 0
        self._output_func = output_func

        self._unit = unit
        self._bar_length = bar_length

    @property
    def percent_done(self):
        """
        Returns
        -------
        float
            The percentage of the progress bar currently filled.
        """

        if self._current_value >= self._total:
            percent_done = 100.0

        else:
            percent_done = self._current_value / self._total * 100.0

        return percent_done

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return

    def update(self, value=1, set_value=False):
        """ Update the progress bar in console/terminal.

        Parameters
        ----------
        value : int or float, optional
            The value to update the current progress, out of total, by. Defaults to 1.
        set_value : bool, optional
            If True, the current value, out of total, is set to *value*. If False, the current value is incremented
            by *value*. Defaults to False.

        Returns
        -------
        str or unicode
            The current progress bar string.
        """

        if set_value:
            self._current_value = value
        else:
            self._current_value += value

        done_char_len = int(self.percent_done / 100 * self._bar_length)
        remain_char_len = self._bar_length - done_char_len
        done = self._total if self.percent_done == 100 else self._current_value
        units = ' {0}'.format(self._unit) if len(self._unit) > 0 else ''

        msg = '{percent:3.0f}% [{done_char}{remain_char}] ' \
              '({done:.2f} / {total:.2f}{unit})'.format(percent=self.percent_done,
                                                        done_char='=' * done_char_len,
                                                        remain_char=' ' * remain_char_len,
                                                        done=done,
                                                        total=self._total,
                                                        unit=units)

        if self._output_func is not None:
                self._output_func(msg)

        return msg
