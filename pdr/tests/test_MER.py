""" Test performance for MER data. """

import unittest
import pdr

# Cameras

class TestPancam(unittest.TestCase):

    def setUp(self):
        pass

    def test_pancam_edr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1po_0xxx/data/sol0071/edr/1p134482118erp0902p2600r8m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1024)
        self.assertEqual(data.IMAGE.shape[1],32)
        self.assertEqual(len(data.LABEL),84)
        self.assertEqual(len(data.IMAGE_HEADER),339)

    def test_pancam_edr_2(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2po_0xxx/data/sol0037/edr/2p129641989eth0361p2600r8m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],64)
        self.assertEqual(data.IMAGE.shape[1],64)
        self.assertEqual(len(data.LABEL),84)
        self.assertEqual(len(data.IMAGE_HEADER),339)

    def test_pancam_rdr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1po_0xxx/data/sol0071/rdr/1p134482118sfl0902p2600l8m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],63)
        self.assertEqual(data.IMAGE.shape[1],63)
        self.assertEqual(len(data.LABEL),85)
        self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_pancam_rdr_2(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2po_0xxx/data/sol0037/rdr/2p129641989mrd0361p2600r8m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],63)
        self.assertEqual(data.IMAGE.shape[1],63)
        self.assertEqual(len(data.LABEL),85)
        self.assertEqual(len(data.IMAGE_HEADER),365)

    def test_pancam_xyl_1(self):    ### Uses *.RGB extension
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1mw_0xxx/data/pancam/site0025/1p137953271xyl2513p2366l7m1.rgb"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_pancam_xyl_2(self):    ### Uses *.RGB extension
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2mw_0xxx/data/pancam/site0015/2p132046745xyl1500p2445l7m1.rgb"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_pancam_rat_1(self):
        url = "http://pds-geosciences.wustl.edu/mer/mer1-m-pancam-3-radcal-rdr-v1/mer1pc_1xxx/data/sol0183/1p144429114rat3370p2542l2c1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],64)
        self.assertEqual(data.IMAGE.shape[1],64)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_pancam_rad_1(self):
        url = "http://pds-geosciences.wustl.edu/mer/mer2-m-pancam-3-radcal-rdr-v1/mer2pc_1xxx/data/sol0052/2p130975038rad1100p2820l4c1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],272)
        self.assertEqual(data.IMAGE.shape[1],320)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_pancam_erp_1(self):
        url = "http://pds-geosciences.wustl.edu/mer/mer1-m-pancam-2-edr-sci-v1/mer1pc_0xxx/data/sol0704/1p190678905erp64kcp2600l8c1.img"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_pancam_erp_2(self):
        url = "http://pds-geosciences.wustl.edu/mer/mer2-m-pancam-2-edr-sci-v1/mer2pc_0xxx/data/sol0048/2p130614950erp09bvp2556r1c1.img"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_pancam_cyp_1(self): # Note: large file (290Mb)
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1om_0xxx/data/pancam/site0011/1pp081ilf11cyp00p2425l777m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],10890)
        self.assertEqual(data.IMAGE.shape[1],13953)
        self.assertEqual(len(data.IMAGE_HEADER),102)
 
    def test_pancam_cyp_2(self): # Note: large file (382Mb)
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2om_0xxx/data/pancam/site0013/2pp062ilf13cyp00p2119l666m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],7984)
        self.assertEqual(data.IMAGE.shape[1],25088)
        self.assertEqual(len(data.IMAGE_HEADER),102)

suite = unittest.TestLoader().loadTestsFromTestCase(TestPancam)
unittest.TextTestRunner(verbosity=2).run(suite)

## Navcam
class TestNavcam(unittest.TestCase):
    
    def setUp(self):
        pass

    def test_navcam_edr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1no_0xxx/data/sol0015/edr/1n129510489eff0312p1930l0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1024)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.IMAGE_HEADER),340)

    def test_navcam_rdr_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1no_0xxx/data/sol0015/rdr/1n129510489mrl0312p1930l0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1024)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.IMAGE_HEADER),366)

    def test_navcam_xyl_1(self): ### Uses *.RGB extension
        # ** WTF?
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1mw_0xxx/data/navcam/site0023/1n137786085xyl2300p1981l0m1.rgb"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_navcam_xyl_2(self): ### Uses *.RGB extension
        # ** WTF?
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2mw_0xxx/data/navcam/site0014/2n131962517xyl1400p1917l0m1.rgb"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_navcam_cyl_1(self): # Note: Large file (168Mb)
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1om_0xxx/data/navcam/site0003/1nn013ilf03cyl00p1652l000m2.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],3543)
        self.assertEqual(data.IMAGE.shape[1],24804)
        self.assertEqual(len(data.IMAGE_HEADER),100)

    def test_navcam_eth_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2no_0xxx/data/sol0035/edr/2n129472048eth0327p1874l0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],64)
        self.assertEqual(data.IMAGE.shape[1],64)
        self.assertEqual(len(data.IMAGE_HEADER),340)

    def test_navcam_inn_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2no_0xxx/data/sol0035/rdr/2n129472048inn0327p1874r0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],512)
        self.assertEqual(data.IMAGE.shape[1],512)
        self.assertEqual(len(data.IMAGE_HEADER),348)

    def test_navcam_cyp_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2om_0xxx/data/navcam/site0006/2nn043ilf06cyp00p1817l000m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1132)
        self.assertEqual(data.IMAGE.shape[1],7704)
        self.assertEqual(len(data.IMAGE_HEADER),102)

suite = unittest.TestLoader().loadTestsFromTestCase(TestNavcam)
unittest.TextTestRunner(verbosity=2).run(suite)

## Hazcam
class TestHazcam(unittest.TestCase):
    
    def setUp(self):
        pass

    def test_hazcam_xyl_1(self): # Uses .RGB extension
        # ** WTF?
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1mw_0xxx/data/hazcam/site0030/1f139471884xyl3000p1214l0m1.rgb"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_hazcam_xyl_2(self): # Uses .RGB extension
        # ** WTF?
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2mw_0xxx/data/hazcam/site0020/2f132759178xyl2000p1212l0m1.rgb"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_hazcam_edn_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1ho_0xxx/data/sol0370/edr/1f161026369edn42d9p1111l0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],512)
        self.assertEqual(data.IMAGE.shape[1],512)
        self.assertEqual(len(data.IMAGE_HEADER),338)

    def test_hazcam_uvl_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1ho_0xxx/data/sol0370/rdr/1f161026369uvl42d9p1111l0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],512)
        self.assertEqual(data.IMAGE.shape[1],512)
        self.assertEqual(data.IMAGE.shape[2],3)
        self.assertEqual(len(data.IMAGE_HEADER),372)

    def test_hazcam_vrt_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1om_0xxx/data/hazcam/site0002/1rr012eff02vrt42p1211l000m2.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],2400)
        self.assertEqual(data.IMAGE.shape[1],2400)
        self.assertEqual(len(data.IMAGE_HEADER),101)

    def test_hazcam_ilf_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2ho_0xxx/data/sol0045/rdr/2f130352973ilf0800p1120r0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1024)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.IMAGE_HEADER),346)

    def test_hazcam_eff_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2ho_0xxx/data/sol0045/edr/2f130356488eff0800p1110r0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1024)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.IMAGE_HEADER),338)

    def test_hazcam_eff_2(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2om_0xxx/data/hazcam/site0002/2ff010eff02per11p1003l000m2.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],922)
        self.assertEqual(data.IMAGE.shape[1],970)
        self.assertEqual(len(data.IMAGE_HEADER),99)

suite = unittest.TestLoader().loadTestsFromTestCase(TestHazcam)
unittest.TextTestRunner(verbosity=2).run(suite)

## Microscopic Imager
class TestMI(unittest.TestCase):
    
    def setUp(self):
        pass

    def test_mi_cfd_1(self): # PDS4 data?
        # ???
        url = "http://pds-geosciences.wustl.edu/mer/mer1-m-mi-3-rdr-sci-v1/mer1mi_1xxx/data/sol0143/1m140877373cfd3190p2936m2f1.img"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_mi_eff_1(self): # PDS4 data?
        url = "http://pds-geosciences.wustl.edu/mer/mer1-m-mi-2-edr-sci-v1/mer1mi_0xxx/data/sol1135/1m228942450eff81d2p2976m2f1.img"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_mi_eff_2(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1mo_0xxx/data/sol1918/edr/1m298459885effa312p2956m2m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1024)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.IMAGE_HEADER),335)
        self.assertEqual(len(data.LABEL),84)

    def test_mi_eff_3(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2mo_0xxx/data/sol0052/edr/2m130974443eff1100p2953m2m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],1024)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.IMAGE_HEADER),335)
        self.assertEqual(len(data.LABEL),84)

    def test_mi_eff_4(self):
        # Contains no data?
        url = "http://pds-geosciences.wustl.edu/mer/mer2-m-mi-2-edr-sci-v1/mer2mi_0xxx/data/sol0078/2m133285881eff2232p2971m2f1.img"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_mi_mrd_1(self): # PDS4 data?
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/opportunity/mer1mo_0xxx/data/sol1918/rdr/1m298459667mrda312p2956m2m1.img"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

    def test_mi_rst_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2mo_0xxx/data/sol0052/rdr/2m130974067rst1100p2942m1m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],64)
        self.assertEqual(data.IMAGE.shape[1],64)
        self.assertEqual(len(data.IMAGE_HEADER),359)

    def test_mi_cfd_1(self): # PDS4 data?
        url = "http://pds-geosciences.wustl.edu/mer/mer2-m-mi-3-rdr-sci-v1/mer2mi_1xxx/data/sol0070/2m132591087cfd1800p2977m2f1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],63)
        self.assertEqual(data.IMAGE.shape[1],63)
        self.assertEqual(len(data.IMAGE_HEADER),350)

suite = unittest.TestLoader().loadTestsFromTestCase(TestMI)
unittest.TextTestRunner(verbosity=2).run(suite)

## Descent Imager
class TestDI(unittest.TestCase):
    
    def setUp(self):
        pass

    def test_di_edn_1(self):
        url = "http://pds-imaging.jpl.nasa.gov/data/mer/spirit/mer2do_0xxx/data/sol0001/edr/2e126462398edn0000f0006n0m1.img"
        data = pdr.open(pdr.get(url))
        self.assertEqual(data.IMAGE.shape[0],256)
        self.assertEqual(data.IMAGE.shape[1],1024)
        self.assertEqual(len(data.IMAGE_HEADER),335)

suite = unittest.TestLoader().loadTestsFromTestCase(TestDI)
unittest.TextTestRunner(verbosity=2).run(suite)

## Descent Imager
class TestAPXS(unittest.TestCase):
    
    def setUp(self):
        pass

    def test_apxs_edn_1(self):
        url = "http://pds-geosciences.wustl.edu/mer/mer2-m-apxs-2-edr-ops-v1/mer2ap_0xxx/data/sol0071/2a132656587edr1800n1438n0m1.dat"
        data = pdr.open(pdr.get(url))
        self.assertEqual(len(data.ENGINEERING_TABLE),1)
        self.assertEqual(len(data.ENGINEERING_TABLE.keys()),240)
        self.assertEqual(len(data.MEASUREMENT_TABLE),12)
        self.assertEqual(len(data.MEASUREMENT_TABLE.keys()),1536)

suite = unittest.TestLoader().loadTestsFromTestCase(TestAPXS)
unittest.TextTestRunner(verbosity=2).run(suite)

## Descent Imager
class TestMB(unittest.TestCase):
    
    def setUp(self):
        pass

    def test_mb_ed_1(self):
        # No data pointers -- no data
        url = "http://pds-geosciences.wustl.edu/mer/mer2-m-mb-2-edr-ops-v1/mer2mb_0xxx/data/sol0034/2b129423244ed50327n1940n0m1.dat"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

suite = unittest.TestLoader().loadTestsFromTestCase(TestMB)
unittest.TextTestRunner(verbosity=2).run(suite)

class TestRAT(unittest.TestCase):
    
    def setUp(self):
        pass

    def test_rat_edr_1(self):
        # AttributeError: 'HeaderStructure' object has no attribute 'fields'
        url = "http://pds-geosciences.wustl.edu/mer/mer2-m-rat-2-edr-ops-v1/mer2ra_0xxx/data/sol0236/2d147320057edr8600d2515n0m1.dat"
        data = pdr.open(pdr.get(url))
        #self.assertEqual(data.IMAGE.shape[0],63)
        #self.assertEqual(data.IMAGE.shape[1],63)
        #self.assertEqual(len(data.IMAGE_HEADER),350)

suite = unittest.TestLoader().loadTestsFromTestCase(TestRAT)
unittest.TextTestRunner(verbosity=2).run(suite)
