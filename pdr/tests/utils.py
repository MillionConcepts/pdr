from pathlib import Path

from pdr.utils import read_hex, head_file, stem_path


def rhex():
    assert read_hex("AAAAAAAA", ">I") == 2863311530


def hfile():
    head = head_file('test_data/bin1', 4)
    assert head.read() == b"\x00\x01\x02\x03"
    headhead = head_file(head, 2, tail=True)
    assert headhead.read() == b"\x02\x03"


# TODO: how is this not throwing errors in production?
def spath():
    p = Path('themis/ir_GEO_v2/I74696023EQR.CUB.gz')
    exts = tuple(map(str.lower, p.suffixes))
    print(exts)
    stemmed_1 = stem_path(p)
    print(stemmed_1)
    assert stemmed_1 == "eijfijeijfei.fits"
    stemmed_2 = stem_path(Path('eijfijeijfeI.gz'))
    assert stemmed_2 == "eijfijeijfei.gz"
