import importlib.util

from pdr import Metadata
from pdr.parselabel.pds3 import parse_pvl
from pdr.tests.objects import SILLY_LABEL

import pytest
if importlib.util.find_spec("Levenshtein"):
    lev_available = True
else:
    lev_available = False


def test_metadata_1():
    meta = Metadata(parse_pvl(SILLY_LABEL), 'PDS3')
    assert meta.metaget('POINTINESS') == 12
    assert meta.metablock(
        'TAIL_COORDINATE_SYSTEM_PARMS'
    )['ARTICULATION_DEVICE_ANGLE'][0]['units'] == 'rad'
    assert meta.metaget_('MEOW_SEQUENCE_NUMBERS') == (1, 2, 3, 4, '5')


@pytest.mark.skipif(not lev_available, reason="Levenshtein not available")
def test_fuzzy_metadata():
    meta = Metadata(parse_pvl(SILLY_LABEL), 'PDS3')
    assert meta.metaget_fuzzy('KAT') == 'MEOW.CAT'
