from pathlib import Path
from typing import Union

import numpy as np
import pytest

from dustgoggles.tracker import Tracker
from pdr.tests.objects import (
    STUB_IMAGE_LABEL,
    STUB_BINARY_TABLE_LABEL,
    STUB_DSV_TABLE_LABEL,
)

@pytest.fixture(scope="session")
def tracker_factory(tmp_path_factory):
    tracker_log_dir = tmp_path_factory.mktemp("tracker_logs", numbered=False)

    def make_tracker(path):
        return Tracker(path.name.replace(".", "_"), outdir=tracker_log_dir)

    return make_tracker


def make_product(
    dir: Path,
    name: str,
    content: Union[np.ndarray, bytes, str],
    label: str,
    **extra_label_params: Union[str, int]
):
    if isinstance(content, np.ndarray):
        content = content.tobytes()
        mode = "wb"
    elif isinstance(content, bytes):
        mode = "wb"
    else:
        mode = "w"

    label = label.format(product_name=name, **extra_label_params)

    fpath = dir / (name + ".QQQ")
    lpath = dir / (name + ".LBL")

    with fpath.open(mode) as stream:
        stream.write(content)
    with lpath.open("w") as stream:
        stream.write(label)
    return (name, fpath, lpath)


@pytest.fixture(scope="session")
def products_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("products", numbered=False)


@pytest.fixture(scope="session")
def uniband_image_product(products_dir):
    zeros = np.zeros((100, 100), dtype=np.uint8)
    return make_product(
        products_dir, "UB-IMG-PROD", zeros, STUB_IMAGE_LABEL, bands=1
    )


@pytest.fixture(scope="session")
def multiband_image_product(products_dir):
    zeros = np.zeros((100, 100, 3), dtype=np.uint8)
    return make_product(
        products_dir, "MB-IMG-PROD", zeros, STUB_IMAGE_LABEL, bands=3
    )


@pytest.fixture(scope="session")
def binary_table_product(products_dir):
    dtype = np.dtype([("x", np.uint8), ("y", np.float32), ("z", np.float64)])
    row = np.array([(1, 4.4, 8.8)], dtype=dtype)
    table = np.tile(row, 10)
    return make_product(
        products_dir, "BIN-TBL-PROD", table, STUB_BINARY_TABLE_LABEL
    )


@pytest.fixture(scope="session")
def dsv_table_product(products_dir):
    table = "5.5| cat| -12\r\n" * 10
    return make_product(
        products_dir, "DSV-TBL-PROD", table, STUB_DSV_TABLE_LABEL
    )
