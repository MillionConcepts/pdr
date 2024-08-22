from pdr import Metadata
from pdr.parselabel.pds3 import parse_pvl

from tests.objects import SILLY_LABEL


def test_metadata_1():
    meta = Metadata(parse_pvl(SILLY_LABEL), 'PDS3')
    assert meta.metaget('POINTINESS') == 12
    assert meta.metablock(
        'TAIL_COORDINATE_SYSTEM_PARMS'
    )['ARTICULATION_DEVICE_ANGLE'][0]['units'] == 'rad'
    assert meta.metaget_fuzzy('KAT') == 'MEOW.CAT'
    assert meta.metaget_('MEOW_SEQUENCE_NUMBERS') == (1, 2, 3, 4, '5')
