from pathlib import Path

from pdr.tests.utilz.checkers import get_dimension_checker

REF_ROOT = Path(Path(__file__).parent.parent)

DATASET_TESTING_RULES = {
    "CH1": {
        "M3_L0": {
            "index": "CH1M3.csv",
            "filter": "_L0.",
            "special_cases": True
        },
    },
    "MSL": {
        "MSLMRD": {
            "index": "MSL.csv",
            "filter": "MSLMRD",
            "extra_checks": [get_dimension_checker],
        }
    }
}
