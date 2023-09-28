from pathlib import Path
from typing import Union

import numpy as np

from pdr.tests.objects import (
    STUB_IMAGE_LABEL,
    STUB_IMAGE_LABEL_MB,
    STUB_BINARY_TABLE_LABEL,
    STUB_DSV_TABLE_LABEL,
)

SYSTEM_PATH_CLASS = Path().__class__


class TempFile(SYSTEM_PATH_CLASS):

    def __del__(self):
        if self.is_dir():
            return
        self.unlink(missing_ok=True)


def make_simple_image_product():
    zeros = np.zeros((100, 100), dtype=np.uint8)
    fpath, lpath = writepaths(zeros)
    return fpath, lpath


def make_simple_binary_table_product():
    dtype = np.dtype([('x', np.uint8), ('y', np.float32), ('z', np.float64)])
    row = np.array([(1, 4.4, 8.8)], dtype=dtype)
    table = np.tile(row, 10)
    return writepaths(table, STUB_BINARY_TABLE_LABEL)


def make_simple_dsv_table_product():
    table = "5.5| cat| -12\r\n" * 10
    return writepaths(table, STUB_DSV_TABLE_LABEL)


def make_simple_image_product_mb():
    zeros = np.zeros((100, 100, 3), dtype=np.uint8)
    return writepaths(zeros, STUB_IMAGE_LABEL_MB)


def writepaths(content: Union[np.ndarray, bytes, str], label=STUB_IMAGE_LABEL):
    fpath = TempFile((Path(__file__).parent / 'PRODUCT.QQQ'))
    lpath = TempFile((Path(__file__).parent / 'PRODUCT.LBL'))
    if isinstance(content, np.ndarray):
        content = content.tobytes()
    mode = "wb" if isinstance(content, bytes) else "w"
    with fpath.open(mode) as stream:
        stream.write(content)
    with lpath.open("w") as stream:
        stream.write(label)
    return fpath, lpath
