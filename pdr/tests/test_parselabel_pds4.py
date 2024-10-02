from pdr.pds4_tools.reader.label_objects import Label
from pdr.parselabel.pds4 import reformat_pds4_tools_label

from pdr.tests.objects import MINIMAL_PDS4_LABEL


# pds4_tools offers no obvious way to parse a Label out of a str,
# nor from an open file handle (which could be a stringio instance).

def test_parse_label(tmp_path):
    minimal_pds4_label_f = tmp_path / "minimal_pds4.xml"
    with open(minimal_pds4_label_f, "wt") as fp:
        fp.write(MINIMAL_PDS4_LABEL)
    unpacked, params = reformat_pds4_tools_label(
        Label.from_file(minimal_pds4_label_f)
    )
    assert sorted(params) == [
        'File_Area_Observational',
        'Identification_Area',
        'Observation_Area',
        'Product_Observational',
        'Reference_List',
        'logical_identifier'
    ]

    PO = unpacked["Product_Observational"]
    assert PO["Observation_Area"] is None
    assert PO["Reference_List"] is None
    assert PO["File_Area_Observational"] is None

    IA = PO["Identification_Area"]
    assert IA["logical_identifier"] == "urn:nasa:pds:mc_pdr_testsuite:test_labels:test_minimal_label.dat"
