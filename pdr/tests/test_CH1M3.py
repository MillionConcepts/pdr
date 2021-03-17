import unittest
import pdr

class TestL0(unittest.TestCase):
    def setUp(self):
        pass

    def test_L0_1(self):
        url = "https://pds-imaging.jpl.nasa.gov/data/m3/CH1M3_0001/DATA/20081118_20090214/200811/L0/M3G20081118T222604_V01_L0.IMG"
        lbl = " https://pds-imaging.jpl.nasa.gov/data/m3/CH1M3_0001/DATA/20081118_20090214/200811/L0/M3G20081118T222604_V01_L0.LBL"
        data = pdr.open(pdr.get(url))
