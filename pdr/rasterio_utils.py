"""utilities for optional rasterio-wrapping functionality"""
import warnings

import rasterio
from rasterio import RasterioIOError
from rasterio.errors import NotGeoreferencedWarning

from pdr.utils import check_cases


def open_with_rasterio(file_mapping, filename, object_name):

    # we do not want rasterio to shout about data not being
    # georeferenced; most rasters are not _supposed_ to be georeferenced.
    warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
    if object_name in file_mapping.keys():
        fn = file_mapping[object_name]
    else:
        fn = check_cases(filename)
    # some rasterio drivers can only make sense of a label, attached
    # or otherwise
    dataset = None
    for path in (fn, file_mapping['LABEL']):
        try:
            dataset = rasterio.open(path)
        except RasterioIOError:
            continue
    if dataset is None:
        warnings.warn(
            f"userasterio=True passed, but rasterio couldn't open "
            f"{object_name}. Falling back to standard image handling."
        )
        raise IOError("rasterio failed to open the file.")
    if len(dataset.indexes) == 1:
        # Make 2D images actually 2D
        return dataset.read()[0, :, :]
    else:
        return dataset.read()
