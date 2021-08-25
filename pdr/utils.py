import os
import pickle
import sys
import warnings
from typing import Union, Sequence

import astropy.io.fits
import numpy as np
import pandas as pd
from PIL import Image
import pvl
from dustgoggles.structures import dig_for

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


def download_data_and_label(url, data_dir=".", lbl=None):
    """Download an observational data file from the PDS.
    Check for a detached label file and also download that, if it exists.
    """
    _ = download_with_progress_bar(
        url, url_to_path(url, data_dir=data_dir), quiet=True
    )
    try:
        _ = download_with_progress_bar(
            lbl, url_to_path(lbl, data_dir=data_dir), quiet=True
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
                lbl = lbl_
    return url_to_path(url, data_dir=data_dir), url_to_path(
        lbl, data_dir=data_dir
    )


def download_test_data(
    index, data_dir=".", refdatafile="pdr/tests/refdata.csv"
):
    refdata = pd.read_csv(f"{refdatafile}", comment="#")
    return download_data_and_label(
        refdata["url"][index],
        labelurl=refdata["lbl"][index],
        data_dir=data_dir,
    )


# TODO: excessively ugly
def get_pds3_pointers(label=None, local_path=None):
    if label is None:
        label = pvl.load(local_path)
    # TODO: inadequate? see issue pdr#15 -- did I have a resolution for this
    #  somewhere? do we really need to do a full recursion step...? gross
    return dig_for(label, "^", lambda k, v: k.startswith(v))


def pointerize(string):
    return string if string.startswith("^") else "^" + string


def depointerize(string):
    return string[1:] if string.startswith("^") else string


# noinspection PyArgumentList
def normalize_range(
    image: np.ndarray,
    bounds: Sequence[int] = (0, 1),
    stretch: Union[float, Sequence[float]] = None,
) -> np.ndarray:
    """
    simple linear min-max scaler that optionally cuts off low and high

    percentiles of the input
    """
    working_image = image.copy()
    if isinstance(stretch, Sequence):
        cheat_low, cheat_high = stretch
    else:
        cheat_low, cheat_high = (stretch, stretch)
    range_min, range_max = bounds
    if cheat_low is not None:
        minimum = np.percentile(image, cheat_low).astype(image.dtype)
    else:
        minimum = image.min()
    if cheat_high is not None:
        maximum = np.percentile(image, 100 - cheat_high).astype(image.dtype)
    else:
        maximum = image.max()
    if not ((cheat_high is None) and (cheat_low is None)):
        working_image = np.clip(working_image, minimum, maximum)
    return range_min + (working_image - minimum) * (range_max - range_min) / (
        maximum - minimum
    )


def eightbit(array, stretch=(0, 0)):
    """return an eight-bit version of an array"""
    return np.round(normalize_range(array, (0, 255), stretch)).astype(np.uint8)


def browsify(obj, outfile):
    if isinstance(obj, pvl.collections.OrderedMultiDict):
        try:
            pvl.dump(obj, open(outfile + ".lbl", 'w'))
        except (ValueError, TypeError) as e:
            warnings.warn(
                f"pvl will not dump; {e}; writing to {outfile}.badpvl.txt"
            )
            with open(outfile + ".badpvl.txt", 'w') as file:
                file.write(str(obj))
    elif isinstance(obj, np.recarray):
        try:
            obj = pd.DataFrame.from_records(obj)
            obj.to_csv(outfile + ".csv")
        except ValueError:
            pickle.dump(obj, open(outfile + '_nested_recarray.pkl', 'wb'))
    elif isinstance(obj, np.ndarray):
        if len(obj.shape) == 3:
            if obj.shape[0] != 3:
                warnings.warn("dumping only middle band of this image")
                middle_band = round(obj.shape[0] / 2)
                obj = obj[middle_band]
            else:
                obj = np.dstack([channel for channel in obj])
        Image.fromarray(eightbit(obj)).save(outfile + ".jpg")
    elif isinstance(obj, pd.DataFrame):
        obj.to_csv(outfile + ".csv"),
    elif obj is None:
        return
    else:
        with open(outfile + ".txt", "w") as stream:
            stream.write(str(obj))
