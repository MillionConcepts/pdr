import numpy as np

import pdr
from pdr._scaling import find_special_constants
from pdr.parselabel.pds3 import parse_pvl

RNG = np.random.default_rng()

STUB = """
OBJECT =                    IMAGE
    INVALID_CONSTANT =      33
END_OBJECT
END
"""


def test_find_special_constants():
    meta = pdr.Metadata(parse_pvl(STUB), 'PDS3')
    arr = RNG.choice(np.array([33, -32766, 100]), (100, 100))
    specials = find_special_constants(meta, arr.astype(np.int16), 'IMAGE')
    assert specials == {"INVALID_CONSTANT": 33, "ISIS_LOW_INST_SAT": -32766}
