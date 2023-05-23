import datetime as dt
import json
import os
from functools import partial
from inspect import currentframe, getframeinfo
from itertools import count
from operator import contains
from pathlib import Path
from random import randint


def looks_like_ascii(block, name):
    return (
        ("SPREADSHEET" in name)
        or ("ASCII" in name)
        or (block.get('INTERCHANGE_FORMAT') == 'ASCII')
    )


def quantity_start_byte(quantity_dict, record_bytes):
    # TODO: are there cases in which _these_ aren't 1-indexed?
    if quantity_dict["units"] == "BYTES":
        return quantity_dict["value"] - 1
    if record_bytes is not None:
        return record_bytes * max(quantity_dict["value"] - 1, 0)


def _count_from_bottom_of_file(filename, rows, row_bytes):
    tab_size = rows * row_bytes
    if isinstance(filename, list):
        filename = filename[0]
    return os.path.getsize(Path(filename)) - tab_size


def _check_delimiter_stream(identifiers, name, target):
    """
    do I appear to point to a delimiter-separated file without
    explicit record byte length
    """
    # TODO: this may be deprecated. assess against notionally-supported
    #  products.
    if isinstance(target, dict):
        if target.get("units") == "BYTES":
            return False
    # TODO: untangle this, everywhere
    if isinstance(target, (list, tuple)):
        if isinstance(target[-1], dict):
            if target[-1].get("units") == "BYTES":
                return False
    # TODO: not sure this is a good assumption -- it is a bad assumption
    #  for the CHEMIN RDRs, but those labels are just wrong
    if identifiers["RECORD_BYTES"] not in (None, ""):
        return False
    # TODO: not sure this is a good assumption
    if not identifiers["RECORD_TYPE"] == "STREAM":
        return False
    textish = map(
        partial(contains, name), ("ASCII", "SPREADSHEET", "HEADER")
    )
    if any(textish):
        return True
    return False


def check_explicit_delimiter(block):
    if "FIELD_DELIMITER" in block.keys():
        return {
            "COMMA": ",",
            "VERTICAL_BAR": "|",
            "SEMICOLON": ";",
            "TAB": "\t",
        }[block["FIELD_DELIMITER"]]
    return ","


class TrivialTracker:

    def dump(self):
        pass

    def track(self, *_, **__):
        pass

    def clear(self):
        pass

    def set_metadata(self, **metadata):
        pass


class Tracker(TrivialTracker):
    """watches where it's been"""

    def __init__(self, name=None, identifier="", outdir=None):
        self.history, self.metadata, self.counter = [], {}, count(1)
        self.name = name
        if outdir is None:
            outdir = Path(__file__).parent.parent / ".tracker_logs"
        if identifier != "":
            identifier = f"{identifier}_"
        outdir.mkdir(exist_ok=True)
        self.outpath = Path(outdir, f"{identifier}{self.name}.json")

    def clear(self):
        self.outpath.unlink(missing_ok=True)
        self.history = []
        self.counter = count(1)

    def track(self, func, **metadata):
        if "__name__" in dir(func):
            target = func.__name__
        else:
            target = str(func)
        caller = currentframe().f_back
        info = getframeinfo(caller)
        rec = {
            'target': target,
            'caller': info.function,
            'lineno': info.lineno,
            'trackcount': next(self.counter),
            'trackname': self.name
        } | self.metadata | metadata
        self.history.append(rec)

    def set_metadata(self, **metadata):
        self.metadata |= metadata

    def _get_paused(self):
        return self._paused

    def _set_paused(self, state: bool):
        self._paused = state

    def dump(self):
        if self.paused is True:
            return
        log = {'time': dt.datetime.now().isoformat(), 'history': self.history}
        # TODO: do this more cleverly with incremental writes etc.
        with self.outpath.open("a") as stream:
            json.dump(log, stream)

    _paused = False
    paused = property(_get_paused, _set_paused)