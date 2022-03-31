"""possibly-deprecated download functions."""
import os
import sys
from typing import Optional

import pandas as pd

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


###
# END code derived from astroML
###


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
