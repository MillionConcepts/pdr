from __future__ import annotations

import warnings


def trivial_history():
    """
    The history object is a holdover object purely for ISIS compatibility.

    HITS:
    * vex_virtis
        * RAW
        * CALIBRATED
    """
    warnings.warn('The VIRTIS "HISTORY" object is not supported. It is a '
                  'vestige of ISIS compatability.')
    return True
