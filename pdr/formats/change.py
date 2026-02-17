from __future__ import annotations

import warnings


def image_prefix_trivial():
    """
    The image prefix pointer is actually a table, that doesn't seem to be
    formatted how the label describes.

    HITS:
    * change1
        * IIMLVL01
        * IIMLVL2A
    """
    warnings.warn(
        f"The image prefix tables do not properly load with PDR."
    )
    return True


def read_change_fw_table(structure, fn):
    """
    Sometimes the data types listed in the label are incompatible with
    pds4_tools, so we load the fixed width tables in a more lax way.

    HITS:
    * change1
        * IIMLVL01
        * IIMLVL2A
    * change6
        * LMS_M_SCI_LVL2B
        * LMS_S_SCI_LVL2B
        * LMS_N_SCI_LVL2B
    * change5
        * LMS_S_SCI_LVL2B
        * LMS_N_SCI_LVL2B
    * change4
        * VNIS_SD_SCI_LVL2B
    """
    import pandas as pd

    cols = []
    for i in structure.meta_data['Record_Character']['Field_Character']:
        cols.append(i['name'])

    # if filename is label
    if fn[-1] == "L":
        fn = fn[:-1]
    df = pd.read_fwf(fn, names=cols)
    return df


def read_table_using_spaces(structure, fn):
    """
    Sometimes the data types listed in the label are incompatible with
    pds4_tools, so we load the fixed width tables in a more lax way.
    When the spaces are not equal between cols, we used the whitespace
    to divide.

    HITS:
    * change4
        * LND_DPSL_LVL2A
        * LND_ThN_LVL2A
        * LND_TID_LVL2A
        * ASAN_SCI_LVL2B
    """
    import pandas as pd

    # gather column names from structure meta data
    cols = []
    for i in structure.meta_data['Record_Character']['Field_Character']:
        cols.append(i['name'])

    # deal with groups where we use same col names several times
    # sometimes there are multiple groups in a list, sometimes one, so
    # we put the single one into a list to easily iterate
    group_chars = structure.meta_data['Record_Character'].get(
        'Group_Field_Character', [])
    if not isinstance(group_chars, list):
        group_chars = [group_chars]
    for group in group_chars:
        name = group.get('name', 'Group')
        repetitions = int(group.get('repetitions', 0))
        for rep in range(repetitions):
            cols.append(f"{name}_{rep + 1}")

    # if filename is label
    if fn[-1] == "L":
        fn = fn[:-1]

    df = pd.read_csv(
        fn,
        sep=r"\s+",  # any space
        names=cols,
        engine="python"
    )
    return df


def cal_target_data_trivial():
    """
    I could not find this table in the CNSA LPDRS system, but it could be
    there somewhere. However, the table filename is also surrounded by non-UTF
    characters in the label, so that would need to be modified to work properly
    as well.

    HITS:
    * change3
        * VNIS_CC_SCI_LVL2A
    """
    warnings.warn(
        f"This is a separate datafile that must also be downloaded. "
        f"The characters around the filename in the label are also not UTF."
    )
    return True


def special_label(fn):
    """
    Load Chang'e labels with characters not in utf-8.

    HITS:
    * change1
    * change2
    * change3
    """
    from pdr.parselabel.utils import trim_label
    from pdr.utils import decompress

    return trim_label(
        decompress(fn),
        strict_decode=False,
        raise_no_ending=False,
        special_encoding="gb18030"
    )
