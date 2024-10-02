from pathlib import Path

import pytest

import pdr

IMPATH = Path(__file__).parent / 'data'

try:
    from PIL import Image
    pil_available = True
except ImportError:
    pil_available = False


# NOTE: loose value checks in this module are intended to allow for
# differences in environment-level versions of libjpeg etc.


@pytest.mark.skipif(not pil_available, reason="PIL not available")
def test_simple_primary_jpeg():
    im = pdr.read(IMPATH / 'squirrel.jpg')
    assert abs(im.IMAGE.mean() - 125.5) < 0.5
    assert im.metaget('mode') == 'RGB'
    assert im.metaget('format') == 'JPEG'
    assert im.standard == 'JPEG'


@pytest.mark.skipif(not pil_available, reason="PIL not available")
def test_phone_camera_mpo():
    im = pdr.read(IMPATH / 'concert.jpeg')
    assert abs(im.IMAGE.mean() - 40 < 0.5)
    assert abs(im.Undefined_1.mean() - 5 < 0.5)
    assert im.metaget(
        'MPEntry'
    )[0]['Attribute']['MPType'] == 'Baseline MP Primary Image'
    assert im.metaget('Model') == 'iPhone 13 Pro Max'
    assert im.metaget('Longitude') == (82.0, 33.0, 3.61)
    assert im.metaget('mode') == 'RGB'
    assert im.standard == 'MPO'


@pytest.mark.skipif(not pil_available, reason="PIL not available")
def test_simple_tiff():
    im = pdr.read(IMPATH / 'kings_river_canyon.tiff')
    assert abs(im.IMAGE.mean() - 152.6 < 0.5)
    assert im.metaget('mimetype') == 'image/tiff'
    assert im.metaget('mode') == 'L'
    assert im.standard == 'TIFF'


@pytest.mark.skipif(not pil_available, reason="PIL not available")
def test_anigif():
    im = pdr.read(IMPATH / 'F187B51_cycle_3.gif')
    assert len(im) == 43
    assert abs(im.FRAME_30.mean() - 115.5 < 0.5)
    assert abs(im.FRAME_5.mean() - 1.5 < 0.5)
    assert im.metaget('mode') == 'P'
    assert im.metaget('palette')[(238, 255, 0)] == 0


@pytest.mark.skipif(not pil_available, reason="PIL not available")
def test_png():
    im = pdr.read(IMPATH / 'catseye_1.png')
    assert abs(im.IMAGE.mean() - 19.4 < 0.5)
    assert im.metaget('mode') == 'RGB'
    assert im.metaget('ExifOffset') == 168


@pytest.mark.skipif(not pil_available, reason="PIL not available")
def test_bmp():
    im = pdr.read(IMPATH / 'weather.bmp')
    assert abs(im.IMAGE.mean() - 118.6 < 0.5)
    assert im.metaget('mode') == 'RGB'
    assert im.standard == 'BMP'


@pytest.mark.skipif(not pil_available, reason="PIL not available")
def test_animated_webp():
    im = pdr.read(IMPATH / 'Simple_Animated_Clock.webp')
    assert len(im) == 287
    assert abs(im.FRAME_286.mean() - 1.5 < 0.5)
    assert im.metaget('mode') == 'RGBA'
    assert im.standard == 'WEBP'
