from __future__ import annotations

import warnings


def trvial_dsn_table():
    """
    The TNF "file" objects (.DAT) are a low level product type for VEX VRA
    which already have open-source software available for opening them. IF we
    support more DSN files in the future this might be worth pursuing.

    HITS:
    * vex_vera
        * LV1A_CL_DSN_TNF
    """
    warnings.warn('The Venus Express VRA Level 1A "TNF" product is not '
                  'currently supported due to the complex file format designed'
                  ' for the Deep Space Network (and referred to as TRK-2-34). '
                  'More info can be found in VRA documentation.')
    return True


def get_special_block(data, name):
    """
    Ramp tables pointer (doppler table) does not match the object name
     (RAMP_TABLE).

    HITS
    * vex_vera
        * LV1B_CL_DSN_RMP
    """
    if name == "DOPPLER_SBAND_TABLE":
        return True, data.metablock_("RAMP_TABLE")
    return False, None


def udr_table_loader(fn):
    """
    Loads a table for 1A VERA products that do not have ANY information
    in the label (start byte etc). These tables also have an embedded header we
    find the end of and read what is beyond into pandas as the table.

    HITS
    * vex_vera
        * LV1A_CL_IFMS_AG1
        * LV1A_CL_IFMS_AG2
        * LV1A_CL_IFMS_D1X
        * LV1A_CL_IFMS_D2S
        * LV1A_CL_IFMS_D2X
    """
    import pandas as pd
    with open(fn, "r") as f:
        for i, line in enumerate(f):
            line_stripped = line.strip()
            if line_stripped.startswith("//"):
                header_line = line_stripped
                start_line = i
                break
        else:
            raise ValueError("Couldn't find start of level 1A VRA table.")
    colnames = header_line[2:].strip().split()
    table = pd.read_fwf(
        fn,
        skiprows=start_line + 1,
        names=colnames,
        comment="<"
    )
    return table


def udr_table_structure():
    """
    We can't define structure before loading the table.
    There is no useful info in the label on the "file" object.

    HITS
    * vex_vera
        * LV1A_CL_IFMS_AG1
        * LV1A_CL_IFMS_AG2
        * LV1A_CL_IFMS_D1X
        * LV1A_CL_IFMS_D2S
        * LV1A_CL_IFMS_D2X
    """
    return True, None


def udr_table_special_position():
    """
    We can't define special position before loading the table.
    There is no useful info in the label on the "file" object.

    HITS
    * vex_vera
        * LV1A_CL_IFMS_AG1
        * LV1A_CL_IFMS_AG2
        * LV1A_CL_IFMS_D1X
        * LV1A_CL_IFMS_D2S
        * LV1A_CL_IFMS_D2X
    """
    return True, None