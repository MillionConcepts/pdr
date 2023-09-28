from typing import Optional


def takes_a_few_things(a, b, c, *, d: Optional[int] = 1, e=5, **_):
    return a + b + c + d + e


def takes_x_only(x):
    return x + 1


STUB_LABEL = """
^IMAGE = "IMAGE.IMG"
SPACECRAFT_NAME = "ORBITER"
END
"""

SILLY_LABEL = """
PDS_VERSION_ID                    = NO
/* FILE DATA ELEMENTS */
RECORD_TYPE                         = ABSOLUTELY_NOT
RECORD_BYTES                        = 1000000
FILE_RECORDS                        = -1
/* pointer to CAT */
^CAT           = "MEOW.CAT"   /* 0:SPECTRUM IR; 1:IMAGE */  
CAT_NAME             = LILY
SOME_PARAMETER              = "1000" /* h h h   h i! */
OTHER_CATS                    = {
"this_one"}
DESCRIPTION                   = "This is a really 
nice cat. MONTMORILLONITE = 100.
 Great cat"
/* Misidentification Data Elements */  
NOTHING:FF         = "B"
MEOW_SEQUENCE_NUMBERS         = (1, 2,
3, 4, "5"
)
/* Coordinate System State: Tail */


GROUP                              = TAIL_COORDINATE_SYSTEM_PARMS
 COORDINATE_SYSTEM_NAME              = TAIL_FRAME
 OBJECT                             =  TIP_OF_TAIL_FORMAT
    POINTINESS                       = 12
 END_OBJECT                          = TAIL_TIP_FORMAT            
 COORDINATE_SYSTEM_INDEX_NAME        = ("CURL", "FUR", "POSE")
 ARTICULATION_DEVICE_ANGLE           = ( -0.000045 <rad>, -0.785042 <rad> )
END_GROUP                          = I_FORGOT
END
"""

BLOCK_TEXT = """OBJECT                            = IMAGE
  INTERCHANGE_FORMAT              = BINARY
  LINES                           = 650
  LINE_SAMPLES                    = 350
  SAMPLE_TYPE                     = IEEE_REAL
  SAMPLE_BITS                     = 32
  BANDS                           = 3
  BAND_STORAGE_TYPE               = BAND_SEQUENTIAL
  FIRST_LINE                      = 375
  FIRST_LINE_SAMPLE               = 1
  SAMPLE_BIT_MASK                 = 2#0111111111111111#
  INVALID_CONSTANT                = (0.0,0.0,0.0)
  MISSING_CONSTANT                = (0.0,0.0,0.0)
END_OBJECT                        = IMAGE
"""

QUBE_BLOCK_TEXT = """OBJECT = SPECTRAL_QUBE
  AXES = 3
  AXIS_NAME = (SAMPLE, LINE, BAND)
  ISIS_STRUCTURE_VERSION_ID = "2.1"
  /* Core Description */
  CORE_ITEMS = (100, 66, 17)
  CORE_NAME = "CALIBRATED SPECTRAL RADIANCE"
  CORE_ITEM_BYTES = 4
  CORE_ITEM_TYPE = IEEE_REAL
  CORE_BASE = 0.000000
  CORE_MULTIPLIER = 1.000000
  CORE_UNIT = "uWATT*CM**-2*SR**-1*uM**-1"
  CORE_NULL = -1.0
  CORE_VALID_MINIMUM = 0.0
  CORE_LOW_REPR_SATURATION = -32767.0
  CORE_LOW_INSTR_SATURATION = -32766.0
  CORE_HIGH_REPR_SATURATION = -32765.0
  CORE_HIGH_INSTR_SATURATION = -32764.0  
  SUFFIX_ITEMS = (0,0,8)
  BAND_SUFFIX_ITEM_BYTES = 4
END_OBJECT
"""
