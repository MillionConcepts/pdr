"""assorted utility functions"""
import os
import re
import struct
import sys
import warnings
from functools import reduce
from itertools import chain
from numbers import Number
from operator import add
from pathlib import Path
from typing import (
    Optional,
    Collection,
    Union,
    Hashable,
    Sequence,
    Mapping,
    MutableSequence,
)

import numpy as np
import pandas as pd
import pandas.api.types
import pvl
import pvl.grammar
import pvl.decoder
from dustgoggles.structures import dig_for
from typing.io import IO

"""
The following three functions are substantially derived from code in
https://github.com/astroML/astroML and so carry the following license:

Copyright (c) 2012-2013, Jacob Vanderplas All rights reserved.

Redistribution and use in source and binary forms, with or without modification, are permitted provided that the following conditions are met:

Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer. Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution.
THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
"""
from urllib.request import urlopen
from urllib.error import HTTPError
from io import BytesIO


def url_content_length(fhandle):
    length = dict(fhandle.info())["Content-Length"]
    return int(length.strip())


def bytes_to_string(nbytes):
    if nbytes < 1024:
        return "%ib" % nbytes
    nbytes /= 1024.0
    if nbytes < 1024:
        return "%.1fkb" % nbytes
    nbytes /= 1024.0
    if nbytes < 1024:
        return "%.2fMb" % nbytes
    nbytes /= 1024.0
    return "%.1fGb" % nbytes


def download_with_progress_bar(data_url, file_path, force=False, quiet=False):
    if os.path.exists(file_path) and not force:
        if not quiet:
            print("{fn} already exists.".format(fn=file_path.split("/")[-1]))
            print("\t Use `force` to redownload.")
        return 0
    if not os.path.exists(os.path.dirname(file_path)):
        os.makedirs(os.path.dirname(file_path))
    num_units = 40
    try:
        fhandle = urlopen(data_url)
    except HTTPError as e:
        # print("***", e)
        # print("\t", data_url)
        return 1
    content_length = url_content_length(fhandle)
    chunk_size = content_length // num_units
    print(
        "Downloading -from- {url}\n\t-to- {cal_dir}".format(
            url=data_url, cal_dir=os.path.dirname(file_path)
        )
    )
    nchunks = 0
    buf = BytesIO()
    content_length_str = bytes_to_string(content_length)
    while True:
        next_chunk = fhandle.read(chunk_size)
        nchunks += 1
        if next_chunk:
            buf.write(next_chunk)
            s = (
                "["
                + nchunks * "="
                + (num_units - 1 - nchunks) * " "
                + "]  %s / %s   \r"
                % (bytes_to_string(buf.tell()), content_length_str)
            )
        else:
            sys.stdout.write("\n")
            break

        sys.stdout.write(s)
        sys.stdout.flush()

    buf.seek(0)
    open(file_path, "wb").write(buf.getvalue())
    return 0


###
# END code derived from astroML
###


def url_to_path(url, data_dir="."):
    try:
        dirstart = url.split("://")[1].find("/")
        file_path = data_dir + url.split("://")[1][dirstart:]
        if file_path.split("/")[1] != "data":
            file_path = file_path.replace(
                file_path.split("/")[1], "data/" + file_path.split("/")[1]
            )
            print(file_path)
    except AttributeError:  # for url==np.nan
        file_path = ""
    return file_path


def download_data_and_label(
    url: str, data_dir: str = ".", lbl_url: Optional[str] = None
) -> tuple[str, str]:
    """
    Download an observational data file from the PDS.
    Check for a detached label file and also download that, if it exists.
    Optionally specify known url of the label with lbl_url.
    returns local paths to downloaded data and label files.
    """
    _ = download_with_progress_bar(
        url, url_to_path(url, data_dir=data_dir), quiet=True
    )
    try:
        _ = download_with_progress_bar(
            lbl_url, url_to_path(lbl_url, data_dir=data_dir), quiet=True
        )
    except (AttributeError, FileNotFoundError):
        # Attempt to guess the label URL (if there is a label)
        for ext in [
            ".LBL",
            ".lbl",
            ".xml",
            ".XML",
            ".HDR",
        ]:  # HDR? ENVI headers
            lbl_ = url[: url.rfind(".")] + ext
            if not download_with_progress_bar(
                lbl_, url_to_path(lbl_, data_dir=data_dir), quiet=True
            ):
                lbl_url = lbl_
    return url_to_path(url, data_dir=data_dir), url_to_path(
        lbl_url, data_dir=data_dir
    )


def download_test_data(
    index: int, data_dir: str = ".", refdatafile: str = "pdr/tests/refdata.csv"
) -> tuple[str, str]:
    refdata = pd.read_csv(f"{refdatafile}", comment="#")
    return download_data_and_label(
        refdata["url"][index],
        lbl_url=refdata["lbl"][index],
        data_dir=data_dir,
    )


# TODO: excessively ugly
def get_pds3_pointers(
    label: Optional[pvl.collections.OrderedMultiDict] = None,
    local_path: Optional[str] = None,
) -> tuple[pvl.collections.OrderedMultiDict]:
    """
    attempt to get all PDS3 "pointers" -- PVL objects starting with "^" --
    from a passed label or path to label file.
    """
    if label is None:
        label = pvl.load(local_path)
    # TODO: inadequate? see issue pdr#15 -- did I have a resolution for this
    #  somewhere? do we really need to do a full recursion step...? gross
    return dig_for(label, "^", lambda k, v: k.startswith(v))


def pointerize(string: str) -> str:
    """make a string start with ^ if it didn't already"""
    return string if string.startswith("^") else "^" + string


def depointerize(string: str) -> str:
    """prevent a string from starting with ^"""
    return string[1:] if string.startswith("^") else string


# TODO: replace this with regularizing case of filenames upstream per Michael
#  Aye's recommendation
def in_both_cases(strings: Collection[str]) -> tuple[str]:
    """
    given a collection of strings, return a tuple containing each string in
    that collection in both upper and lower case.
    """
    return tuple(
        chain.from_iterable(
            [(string.upper(), string.lower()) for string in strings]
        )
    )


def read_hex(hex_string: str, fmt: str = ">I") -> Number:
    """
    return the decimal representation of a hexadecimal number in a given
    number format (expressed as a struct-style format string, default is
    unsigned 32-bit integer)
    """
    return struct.unpack(fmt, bytes.fromhex(hex_string))[0]


# heuristic for max label size. we know it's not a real rule.
MAX_LABEL_SIZE = 500 * 1024


def head_file(
    fn_or_reader: Union[IO, Path, str],
    nbytes: Union[int, None] = None,
    offset: int = 0,
    tail: bool = False
) -> BytesIO:
    head_buffer = BytesIO()
    if not hasattr(fn_or_reader, "read"):
        fn_or_reader = open(fn_or_reader, "rb")
    whence = 2 if tail is True else False
    offset = offset * -1 if tail is True else offset
    fn_or_reader.seek(offset, whence)
    head_buffer.write(fn_or_reader.read(nbytes))
    fn_or_reader.close()
    head_buffer.seek(0)
    return head_buffer


KNOWN_LABEL_ENDINGS = (
    b"END\r\n",  # PVL
    b"\x00{3}",  # just null bytes
)


def trim_label(
    fn: Union[IO, Path, str],
    max_size: int = MAX_LABEL_SIZE,
    raise_for_failure: bool = False,
) -> Union[str, bytes]:
    head = head_file(fn, max_size).read()
    # TODO: add some logging or whatever i guess
    for ending in KNOWN_LABEL_ENDINGS:
        if (endmatch := re.search(ending, head)) is not None:
            return head[: endmatch.span()[1]]
    if raise_for_failure:
        raise ValueError("couldn't find a label ending")
    return head


def casting_to_float(array: np.ndarray, *operands: Collection[Number]) -> bool:
    """
    check: will this operation cast the array to float?
    return True if array is integer-valued and any operands are not integers.
    """
    return (array.dtype.char in np.typecodes["AllInteger"]) and not all(
        [isinstance(operand, int) for operand in operands]
    )


def check_cases(filename: Union[Path, str]) -> str:
    """
    check for oddly-cased versions of a specified filename in local path --
    very common to have case mismatches between PDS3 labels and actual archive
    contents.
    """
    if Path(filename).exists():
        return filename
    matches = tuple(
        filter(
            lambda path: path.name.lower() == Path(filename).name.lower(),
            Path(filename).parent.iterdir(),
        )
    )
    if len(matches) == 0:
        raise FileNotFoundError
    if len(matches) > 1:
        warning_list = ", ".join([path.name for path in matches])
        warnings.warn(
            f"Multiple off-case versions of {filename} found in search path: "
            f"{warning_list}. Using {matches[0].name}."
        )
    return str(matches[0])


def byte_columns_to_object(df: pd.DataFrame) -> pd.DataFrame:
    """
    pandas does not support numpy void ('V') types, which are sometimes
    required to deal with unstructured padding containing null bytes, etc.,
    and are probably the appropriate representation for binary blobs like
    bit strings. cast them to object so it does not explode.

    TODO: maybe find a more efficient way to do this upstream, like in the
     DataFrame constructor?
    """
    void_columns = df.dtypes.loc[
        df.dtypes.astype("str").str.contains("V")
    ].index
    # using a selector -- or anything at all more complicated than casting
    # to another data type -- appears to make it explode
    for column in void_columns:
        df[column] = df[column].astype(object)
    return df


def enforce_byteorder(array: np.ndarray, inplace=True) -> np.ndarray:
    """
    determine which, if any, of an array's fields are in nonnative byteorder
    and swap them
    TODO: benchmark
    """
    if inplace is False:
        array = array.copy()
    if len(array.dtype) == 1:
        if array.dtype.isnative:
            return array
        return array.byteswap().newbyteorder("=")
    swap_targets = []
    swapped_dtype = []
    for name, field in array.dtype.fields.items():
        if field[0].isnative is False:
            swap_targets.append(name)
            swapped_dtype.append((name, field[0].newbyteorder("=")))
        else:
            swapped_dtype.append((name, field[0]))
    array[swap_targets] = array[swap_targets].byteswap()
    array.dtype = swapped_dtype
    return array


class TimelessOmniDecoder(pvl.decoder.OmniDecoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, grammar=pvl.grammar.OmniGrammar(), **kwargs)

    def decode_datetime(self, value: str):
        raise ValueError


def numeric_columns(df: pd.DataFrame) -> list[Hashable]:
    return [
        col
        for col, dtype in df.dtypes.iteritems()
        if pandas.api.types.is_numeric_dtype(dtype)
    ]


def booleanize_booleans(
    table: pd.DataFrame, fmtdef: pd.DataFrame
) -> pd.DataFrame:
    boolean_columns = fmtdef.loc[fmtdef["DATA_TYPE"] == "BOOLEAN", "NAME"]
    table[boolean_columns] = table[boolean_columns].astype(bool)
    return table


def append_repeated_object(
    obj: Union[Sequence[Mapping], Mapping],
    fields: MutableSequence[Mapping],
    repeat_count: int,
) -> Sequence[Mapping]:
    # sum lists (from containers) together and add to fields
    if hasattr(obj, "__add__"):
        if repeat_count > 1:
            fields += reduce(add, [obj for _ in range(repeat_count)])
        else:
            fields += obj
    # put dictionaries in a repeated list and add to fields
    else:
        if repeat_count > 1:
            fields += [obj for _ in range(repeat_count)]
        else:
            fields.append(obj)
    return fields


def filter_duplicate_pointers(pointers, pt_groups):
    for pointer, group in pt_groups.items():
        if (len(group) > 1) and (pointer != "^STRUCTURE"):
            warnings.warn(
                f"Duplicate handling for {pointer} not yet "
                f"implemented, ignoring"
            )
        else:
            pointers.append(group[0][0])
    return pointers


