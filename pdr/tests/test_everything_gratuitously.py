from itertools import chain

import pytest

from pdr.tests.utilz.test_utilz import perform_dataset_test
from pdr.tests.definitions.datasets import DATASET_TESTING_RULES

mission_set_pairs = chain.from_iterable(
    [
        [(mission, dataset) for dataset in rules.keys()]
        for mission, rules in DATASET_TESTING_RULES.items()
    ]
)


@pytest.mark.parametrize("mission,dataset", mission_set_pairs)
def test_dataset(mission, dataset):
    perform_dataset_test(mission, dataset)
