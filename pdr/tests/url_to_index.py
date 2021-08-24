import pandas as pd

from pdr.tests.utilz.test_utilz import label_urls_to_test_index

test_case = "msl"

label_urls = pd.read_csv(
    f"reference/url_lists/{test_case}.csv", header=None
).iloc[:, 0]
results = label_urls_to_test_index(label_urls)
results.to_csv(f"reference/index/{test_case}.csv", index=None)
