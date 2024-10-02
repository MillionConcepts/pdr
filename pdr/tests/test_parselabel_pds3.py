from pdr.parselabel.pds3 import parse_pvl
from pdr.tests.objects import SILLY_LABEL


def test_parse_label():
    params, _ = parse_pvl(SILLY_LABEL)
    assert params['^CAT'] == 'MEOW.CAT'
    assert params['CAT_NAME'] == 'LILY'
    assert params[
               'TAIL_COORDINATE_SYSTEM_PARMS'
           ]['TIP_OF_TAIL_FORMAT']['POINTINESS'] == 12
    assert params[
               'TAIL_COORDINATE_SYSTEM_PARMS'
           ]['ARTICULATION_DEVICE_ANGLE'][0] == \
        {'value': -4.5e-05, 'units': 'rad'}
