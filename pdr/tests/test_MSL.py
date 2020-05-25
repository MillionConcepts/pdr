""" Test performance for MSL data. """

import unittest
import pdr

# Cameras

class TestMD(unittest.TestCase):
    def setUp(self):
        pass

    def test_md_rdr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLMRD_0002/DATA/RDR/SURFACE/0000/0000MD0000000000100027C00_DRCL.IMG"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1533)
        self.assertEqual(data.IMAGE.shape[1],2108)
        self.assertEqual(data.IMAGE.shape[2],3)
        self.assertEqual(len(data.LABEL),84)

    def test_md_edr_1(self): # MSSS compressed format
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLMRD_0002/DATA/EDR/SURFACE/0000/0000MD0000000000100027C00_XXXX.DAT"
        #data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],1533)
        #self.assertEqual(data.IMAGE.shape[1],2108)
        #self.assertEqual(data.IMAGE.shape[2],3)
        #self.assertEqual(len(data.LABEL),84)


suite = unittest.TestLoader().loadTestsFromTestCase(TestMD)
unittest.TextTestRunner(verbosity=2).run(suite)

class TestMastcam(unittest.TestCase):
    def setUp(self):
        pass

    def test_mastcam_rdr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLMST_0002/DATA/RDR/SURFACE/0025/0025ML0001270000100807E01_DRCL.IMG"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1208)
        self.assertEqual(data.IMAGE.shape[1],1208)
        self.assertEqual(data.IMAGE.shape[2],3)
        self.assertEqual(len(data.LABEL),84)
    
    def test_mastcam_edr_1(self): # MSSS compressed format
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLMST_0002/DATA/EDR/SURFACE/0025/0025ML0001270000100807E01_XXXX.DAT"
        #data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],1533)
        #self.assertEqual(data.IMAGE.shape[1],2108)
        #self.assertEqual(data.IMAGE.shape[2],3)
        #self.assertEqual(len(data.LABEL),84)

suite = unittest.TestLoader().loadTestsFromTestCase(TestMastcam)
unittest.TextTestRunner(verbosity=2).run(suite)

class TestMAHLI(unittest.TestCase):
    def setUp(self):
        pass

    def test_mahli_rdr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLMHL_0002/DATA/RDR/SURFACE/0047/0047MH0000110010100214C00_DRCL.IMG"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1198)
        self.assertEqual(data.IMAGE.shape[1],1646)
        self.assertEqual(data.IMAGE.shape[2],3)
        self.assertEqual(len(data.LABEL),84)

    def test_mahli_edr_1(self): # MSSS compressed format
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLMHL_0002/DATA/EDR/SURFACE/0047/0047MH0000110010100214C00_XXXX.DAT"
        #data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],1533)
        #self.assertEqual(data.IMAGE.shape[1],2108)
        #self.assertEqual(data.IMAGE.shape[2],3)
        #self.assertEqual(len(data.LABEL),84)

suite = unittest.TestLoader().loadTestsFromTestCase(TestMAHLI)
unittest.TextTestRunner(verbosity=2).run(suite)

class TestHazcam(unittest.TestCase):
    def setUp(self):
        pass

    def test_hazcam_edr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLHAZ_0XXX/DATA/SOL00382/FLB_431397159EDR_F0141262FHAZ00323M1.IMG"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1024)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.LABEL),102)
        self.assertEqual(len(data.IMAGE_HEADER),374)

suite = unittest.TestLoader().loadTestsFromTestCase(TestHazcam)
unittest.TextTestRunner(verbosity=2).run(suite)

class TestNavcam(unittest.TestCase):
    def setUp(self):
        pass

    def test_navcam_ecs_1(self): # 1-pixel tall image???
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLNAV_0XXX/DATA/SOL00002/NLA_397671934ECS_N0010008AUT_04096M1.IMG"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.LABEL),101)
        self.assertEqual(len(data.IMAGE_HEADER),357)
    
    def test_navcam_edr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/msl/MSLMOS_1XXX/DATA/SOL00012/N_A000_0012XEDR003CYPTUM0004XTOPMTM1.IMG"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],3)
        self.assertEqual(data.IMAGE.shape[1],3337)
        self.assertEqual(data.IMAGE.shape[2],7824)
        self.assertEqual(len(data.LABEL),29)
        self.assertEqual(len(data.IMAGE_HEADER),126)

suite = unittest.TestLoader().loadTestsFromTestCase(TestNavcam)
unittest.TextTestRunner(verbosity=2).run(suite)
