from pathlib import Path

from pdr.tests.utilz.checkers import dimension_checker, specified_image_size

REF_ROOT = Path(Path(__file__).parent.parent)

DATASET_TESTING_RULES = {
    "ch1": {"m3_l0": {"filter": "_L0."}, "m3_l1b": {"filter": "_L1B."}},
    "msl": {
        "mslmrd": {
            "filter": "MSLMRD",
            "extra_checks": [dimension_checker("mslmrd")],
        },
        "mastcam": {"filter": "MSLMST"},
        "mahli": {"filter": "MSLMHL"},
        "hazcam": {"filter": "MSLHAZ", "extra_checks": [specified_image_size]},
        "navcam": {"filter": "MSLNAV"},
    },
    "lro": {"lyman_alpha": {"filter": "LROLAM"}, "lroc": {"filter": "LROLRC"}},
    "mer": {
        "pancam": {"index": "mer_pancam.csv"},
        "navcam": {"index": "mer_navcam.csv"},
        "hazcam": {"index": "mer_hazcam.csv"},
    },
}
