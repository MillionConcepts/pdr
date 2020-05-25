""" Test performance for LRO data. """

import unittest
import pdr

# Cameras

class TestLymanAlpha(unittest.TestCase):
    def setUp(self):
        pass

    def test_lyman_alpha_gdr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/lro/lamp/gdr/LROLAM_2001/DATA/DATA_QUALITY/LAMP_80n_240mpp_long_dqual_01.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],2501)
        self.assertEqual(data.IMAGE.shape[1],2501)
        self.assertEqual(len(data.LABEL),41)

    def test_lyman_alpha_edr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/lro/lamp/edr/LROLAM_0007/DATA/2011082/LAMP_ENG_0322531705_02.fit"
        #data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],2501)
        #self.assertEqual(data.IMAGE.shape[1],2501)
        #self.assertEqual(len(data.LABEL),41)
 
    def test_lyman_alpha_rdr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/lro/lamp/rdr/LROLAM_1010/DATA/2011352/LAMP_SCI_0345885974_03.fit"
        #data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],2501)
        #self.assertEqual(data.IMAGE.shape[1],2501)
        #self.assertEqual(len(data.LABEL),41)

suite = unittest.TestLoader().loadTestsFromTestCase(TestLymanAlpha)
unittest.TextTestRunner(verbosity=2).run(suite)

class TestLROC(unittest.TestCase):
    def setUp(self):
        pass

    def test_lroc_esm_nac_1(self): # Large file (252Mb)
        url = "http://lroc.sese.asu.edu/data/LRO-L-LROC-3-CDR-V1.0/LROLRC_1015/DATA/ESM/2013092/NAC/M1119524889RC.IMG"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],52224)
        self.assertEqual(data.IMAGE.shape[1],2532)
        self.assertEqual(len(data.LABEL),57)

    def test_lroc_esm_wac_1(self):
        url = "http://lroc.sese.asu.edu/data/LRO-L-LROC-3-CDR-V1.0/LROLRC_1015/DATA/ESM/2013092/WAC/M1119570719MC.IMG"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],3080)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.LABEL),59)

    def test_lroc_sci_nac_1(self): # Large file (252Mb)
        url = "http://lroc.sese.asu.edu/data/LRO-L-LROC-2-EDR-V1.0/LROLRC_0010/DATA/SCI/2012019/NAC/M181639328RE.IMG"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],2501)
        #self.assertEqual(data.IMAGE.shape[1],2501)
        #self.assertEqual(len(data.LABEL),41)

    def test_lroc_sci_wac_1(self):
        url = "http://lroc.sese.asu.edu/data/LRO-L-LROC-2-EDR-V1.0/LROLRC_0010/DATA/SCI/2012019/WAC/M181648212CE.IMG"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],2501)
        #self.assertEqual(data.IMAGE.shape[1],2501)
        #self.assertEqual(len(data.LABEL),41)

    def test_lroc_bdr_nac_roi_1(self):
        url = "http://lroc.sese.asu.edu/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/BDR/NAC_ROI/FLMSTEEDHIA/NAC_ROI_FLMSTEEDHIA_E023S3168_20M.IMG"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],2501)
        #self.assertEqual(data.IMAGE.shape[1],2501)
        #self.assertEqual(len(data.LABEL),41)

    def test_lroc_bdr_wac_roi_1(self):
        url = "http://lroc.sese.asu.edu/data/LRO-L-LROC-5-RDR-V1.0/LROLRC_2001/DATA/BDR/WAC_ROI/FARSIDE_DUSK/WAC_ROI_FARSIDE_DUSK_P900S0000_100M.IMG"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],2501)
        #self.assertEqual(data.IMAGE.shape[1],2501)
        #self.assertEqual(len(data.LABEL),41)

suite = unittest.TestLoader().loadTestsFromTestCase(TestLROC)
unittest.TextTestRunner(verbosity=2).run(suite)
