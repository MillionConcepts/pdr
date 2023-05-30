import re

import pdr.loaders.queries


def get_offset(data, pointer):
    start_row = int(re.split(r",|[(|)]", data.metadata[f"^{pointer}"])[2])
    return True, (start_row - 1) * data.metadata["RECORD_BYTES"]


def get_fn(data, object_name):
    target = re.split(r",|[(|)]", data.metadata[f"^{object_name}"])[1]
    return True, target


def get_structure(block, name, filename, data, identifiers):
    fmtdef = pdr.loaders.queries.read_table_structure(
        block, name, filename, data, identifiers
    )
    import pandas as pd

    fmtdef = pd.concat([fmtdef, fmtdef], ignore_index=True)
    fmtdef["NAME"] = fmtdef["NAME"].str.split("_", expand=True)[0]
    fmtdef["NAME"] = fmtdef["NAME"].str.cat(map(str, fmtdef.index), sep="_")
    fmtdef.ITEM_OFFSET = 8
    fmtdef.ITEM_BYTES = 8
    from pdr.pd_utils import insert_sample_types_into_df

    fmtdef, dt = insert_sample_types_into_df(fmtdef, identifiers)
    return fmtdef, dt
