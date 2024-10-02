import random

import pandas as pd

from pdr.bit_handling import expand_bit_strings
from pdr.loaders.queries import read_table_structure
from pdr.parselabel.pds3 import literalize_pvl_block, parse_pvl
from pdr.pdrtypes import DataIdentifiers

BIT_STUB = """
OBJECT                  = COLUMN
    NAME                = BITS1
    BYTES               = 2
    START_BYTE          = 1
    DATA_TYPE           = "MSB_BIT_STRING"
    OBJECT              = BIT_COLUMN
        NAME            = BITS2
        BIT_DATA_TYPE   = "MSB_INTEGER"
        BITS            = 3
        START_BIT       = 1
    END_OBJECT          = BIT_COLUMN
    OBJECT              = BIT_COLUMN
        NAME            = BITS2
        BIT_DATA_TYPE   = "MSB_INTEGER"
        BITS            = 3
        START_BIT       = 5
    END_OBJECT          = BIT_COLUMN
    OBJECT              = BIT_COLUMN
        NAME            = BITS3
        BIT_DATA_TYPE   = "MSB_INTEGER"
        BITS            = 4
        START_BIT       = 9
    END_OBJECT          = BIT_COLUMN
    OBJECT              = BIT_COLUMN
        NAME            = BITS4
        BIT_DATA_TYPE   = "MSB_INTEGER"
        BITS            = 4
        START_BIT       = 13
    END_OBJECT          = BIT_COLUMN
END_OBJECT              = COLUMN
"""

NULL_IDENTIFIERS = {field: "" for field in DataIdentifiers.__required_keys__}


def test_bit_handling():
    block = parse_pvl(BIT_STUB)[0]
    fmtdef = read_table_structure(block, 'TABLE', None, None, NULL_IDENTIFIERS)
    bits = random.choices((0, 1), k=16)
    table = pd.DataFrame(
        {'BITS1': [int("".join(map(str, bits)), 2).to_bytes(2, 'big')]}
    )
    table = expand_bit_strings(table, fmtdef)
    strings = table.loc[0, 'BITS1']
    assert strings[0] == ''.join(map(str, bits[0:3]))
    assert strings[1] == ''.join(map(str, bits[4:7]))
    assert strings[2] == "".join(map(str, bits[8:12]))
    assert strings[3] == "".join(map(str, bits[12:16]))
