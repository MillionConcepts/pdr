from __future__ import absolute_import
from __future__ import print_function
from __future__ import division
from __future__ import unicode_literals

# PDS4 namespace URIs and default corresponding prefixes. Contains only those that have required
# special usage in the code, and thus must be known.
PDS4_NAMESPACES = {'pds': 'http://pds.nasa.gov/pds4/pds/v1',
                   'disp': 'http://pds.nasa.gov/pds4/disp/v1',
                   'sp': 'http://pds.nasa.gov/pds4/sp/v1'}

# PDS4 root element names for labels that could contain file areas with supported data structures
PDS4_DATA_ROOT_ELEMENTS = ['Product_Observational',
                           'Product_Ancillary',
                           'Product_Browse',
                           'Product_Collection']

# PDS4 file area names that could contain supported data structures
PDS4_DATA_FILE_AREAS = ['File_Area_Observational',
                        'File_Area_Observational_Supplemental',
                        'File_Area_Ancillary',
                        'File_Area_Browse',
                        'File_Area_Inventory']

# PDS4 table types that are supported data structures, and subclasses (which should be supported by default
# since are subclasses) there of
PDS4_TABLE_TYPES = ['Table_Character', 'Table_Binary', 'Table_Delimited', 'Inventory']
