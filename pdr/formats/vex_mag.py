from __future__ import annotations


def special_label(fn):
    """
    Load Vex Mag labels with characters not in utf-8.
    (There is a degree symbol).

    HITS:
    * vex_mag
        * EDR
        * RDR
        * REFDR

    """
    from pdr.parselabel.utils import trim_label
    from pdr.utils import decompress

    return trim_label(
        decompress(fn),
        strict_decode=True,
        raise_no_ending=False,
        special_encoding="latin-1"
    )