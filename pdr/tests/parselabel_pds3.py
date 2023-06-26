import re

from pdr.parselabel.pds3 import parse_pvl, parse_pvl_quantity_statement

label = """
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


def parse_label():
    params, aggregations = parse_pvl(label)
    assert params['^CAT'] == '"MEOW.CAT"'
    assert params['CAT_NAME'] == 'LILY'
    assert params[
       'TAIL_COORDINATE_SYSTEM_PARMS'
    ]['TIP_OF_TAIL_FORMAT']['POINTINESS'] == '12'
    return params


def parse_quantity():
    params = parse_label()
    assert parse_pvl_quantity_statement(
        params['TAIL_COORDINATE_SYSTEM_PARMS']['ARTICULATION_DEVICE_ANGLE']
    )[0] == {'value': -4.5e-05, 'units': 'rad'}

