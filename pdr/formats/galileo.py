from typing import TYPE_CHECKING, Callable
import warnings

if TYPE_CHECKING:
    from pdr import Data


def galileo_table_loader(data: "Data") -> Callable:
    if "-EDR-" in data.metaget_("DATA_SET_ID", ""):
        warnings.warn("Galileo EDR binary tables are not yet supported.")
        return data.trivial

    # def load_this_table(*_, **__):
    #     import astropy.io.ascii
    #     table = astropy.io.ascii.read(data.file_mapping['TABLE']).to_pandas()
    #     table.columns = data.read_table_structure('TABLE')['NAME'].values
    #     return table

    return data.read_table

def ssi_cubes_header_loader(data):
    # The Ida and Gaspra cubes have HEADER pointers but no defined HEADER objects
    return data.trivial

# TO-DO: Is there a better sample_type to replace "N/A" with?
# LSB_UNSIGNED_INTEGER also appears to work correctly and other columns in 
# these tables use it.
def nims_edr_sample_type(sample_type, sample_bytes, for_numpy):
    from pdr.datatypes import sample_types
    # Each time byte order is specified for these products it is LSB, so this
    # assumes BIT_STRING refers to LSB_BIT_STRING
    if 'BIT_STRING' == sample_type:
        sample_type = 'LSB_BIT_STRING'
        return True, sample_types(sample_type, int(sample_bytes), for_numpy=True)
    if 'N/A' in sample_type:
        sample_type = 'CHARACTER'
        return True, sample_types(sample_type, int(sample_bytes), for_numpy=True)
    return False, None
