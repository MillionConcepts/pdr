"""note that this writes to reference/temp/hash"""

from pdr.tests.definitions.datasets import DATASET_TESTING_RULES
from pdr.tests.utilz.test_utilz import regenerate_test_hashes

# regenerate_test_hashes("msl", "hazcam", dump_browse=True)
#
dump_browse = True

for mission_name, datasets in DATASET_TESTING_RULES.items():
    for dataset in datasets.keys():
        print(mission_name, dataset)
        regenerate_test_hashes(mission_name, dataset, dump_browse)
