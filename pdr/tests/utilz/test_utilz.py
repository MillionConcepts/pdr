import json
import logging
import os
from functools import cache
from hashlib import md5
from pathlib import Path
from typing import Callable, Mapping, Sequence
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import pvl
import requests
from dustgoggles.func import disjoint, intersection
from dustgoggles.pivot import pdstr

import pdr
from pdr.tests.definitions.datasets import DATASET_TESTING_RULES
from pdr.utils import get_pds3_pointers

REF_ROOT = Path(Path(__file__).parent.parent, "reference")
DATA_ROOT = Path(Path(__file__).parent.parent, "data")

pdrtestlog = logging.getLogger()
pdrtestlog.addHandler(logging.FileHandler("pdrtests.log"))
pdrtestlog.setLevel("INFO")


@cache
def read_csv_cached(fn: str, *args, **kwargs) -> pd.DataFrame:
    return pd.read_csv(fn, *args, **kwargs)


def record_mismatches(results, absent, novel):
    for key in absent:
        results[key] = "missing from output"
    for key in novel:
        results[key] = "not found in reference"
    return results


def make_hash_reference(hash_path: str) -> Callable[[str, Mapping], dict]:
    reference_hash_table = read_csv_cached(hash_path)
    reference_hash_table.index = reference_hash_table["product_id"]

    def compare_hashes(product_id: str, test_hashes: Mapping):
        reference_hashes = json.loads(
            reference_hash_table.loc[product_id]["hashes"]
        )
        problems = {}
        missing_keys, new_keys = disjoint(reference_hashes, test_hashes)
        # note keys that are completely new or missing
        if len(new_keys + missing_keys):
            problems |= record_mismatches(problems, missing_keys, new_keys)
        # do comparisons between others
        for key in intersection(test_hashes, reference_hashes):
            if test_hashes[key] != reference_hashes[key]:
                problems[key] = (
                    f"mismatched hatches; test: "
                    f"{test_hashes[key]}, reference: "
                    f"{reference_hashes[key]}"
                )
        return problems

    return compare_hashes


def find_ref_paths(dataset, mission, rules):
    ref_paths = {}
    for ref_type in ["hash", "index"]:
        if ref_type in rules.keys():
            stem = rules[ref_type]
        # TODO: why am I making these defaults different?
        #  is it because hashing is more expensive and i want it
        #  split by default? huh
        elif ref_type == "index":
            stem = f"{mission.lower()}.csv"
        else:
            stem = f"{mission.lower()}_{dataset.lower()}.csv"
        ref_paths[ref_type] = str(Path(REF_ROOT, ref_type, stem))
    ref_paths["data"] = Path(DATA_ROOT, mission, dataset)
    if not ref_paths["data"].exists():
        os.makedirs(ref_paths["data"])
    ref_paths["local_contents"] = os.listdir(ref_paths["data"])
    return ref_paths


def filter_products(file_table, filt):
    """
    select only those products from a product index whose ids match a passed
    predicate. predicates should map themselves across series. strings are
    taken to be "product id contains".

    this could be made _much_ more sophisticated; we could have a whole little
    DSL here.
    """
    if isinstance(filt, Callable):
        predicate = filt
    else:
        predicate = pdstr("contains", filt)
    file_table = file_table.loc[
        predicate(file_table["url_stem"] + file_table["label_file"])
    ].reset_index(drop=True)
    return file_table


def make_hash_comparison(compare_hashes_to_reference: Callable):
    def hash_and_check(data):
        hashes = {key: checksum_object(data[key]) for key in data.keys()}
        if "PRODUCT_ID" in data.LABEL.keys():
            nominal_product_id = data.LABEL["PRODUCT_ID"]
        else:
            nominal_product_id = Path(data.filename).stem
        problems = compare_hashes_to_reference(nominal_product_id, hashes)
        # TODO: log this more usefully
        if problems:
            raise ValueError(problems)

    return hash_and_check


# TODO, maybe: special case handling would go somewhere in here as a wrapper,
#  although it might be better dealt with by entirely separate
#  lists or filters, to the extent it's necessary at all -- perhaps
#  there's not even such a thing as a special case for testing because we
#  expect them to always be appropriately handled upstream, and files that
#  we know to be out of scope or corrupt are simply not placed in our testing
#  indices
def read_test_rules(
    mission: str, dataset: str
) -> tuple[pd.DataFrame, dict, Sequence[Callable]]:
    rules = DATASET_TESTING_RULES[mission][dataset]
    products, references = find_test_paths(dataset, mission, rules)
    checks = []
    if "nohash" not in rules.keys():
        hash_reference_checker = make_hash_reference(references["hash"])
        checks.append(make_hash_comparison(hash_reference_checker))
    if "extra_checks" in rules.keys():
        checks += rules["extra_checks"]
    return products, references, checks


def find_test_paths(dataset, mission, rules):
    ref_paths = find_ref_paths(dataset, mission, rules)
    product_table = read_csv_cached(ref_paths["index"])
    if "filter" in rules.keys():
        product_table = filter_products(product_table, rules["filter"])
    return product_table, ref_paths


# TODO: this can eventually be have options to do something other
#  than bang lists of urls...many options here. or we could just mount
#  buckets w/s3fs for cloud testing. If we _do_ want to just bang lists of
#  urls, maybe integrate with get function in pdr.__init__

# TODO: decide if we actually want file discovery to work like this...it could
#  plausibly be more productive to change flow to always infer from the
#  label, or...idk. that's why i'm not consolidating with url lister for now
def collect_files(product, references, local_only=False):
    files = json.loads(product["files"])
    absent = [
        file for file in files if file not in references["local_contents"]
    ]
    if absent and local_only:
        raise OSError("file not found and not allowed to try to download it")
    for file in absent:
        try:
            response = requests.get(f"{product['url_stem']}/{file}")
            if response.status_code == 404:
                pdrtestlog.warning(
                    f"404 result on {product['url_stem']}/{file}"
                )
                continue
            with open(Path(references["data"], file), "wb") as local_file:
                local_file.write(response.content)
        except requests.exceptions.RequestException as e:
            pdrtestlog.warning(e)
            continue


def checksum_object(obj, hasher=md5):
    """
    make stable byte array from python object. the general case of this is,
    I think, impossible, or at least implementation-dependent, so I am
    attempting to cover the specific cases we have...this is a first pass.
    """
    if isinstance(obj, np.ndarray):
        bytestr = obj.tobytes()
    else:
        # TODO: determine when this is and is not actually stable...we'll
        #  find out!
        bytestr = obj.__repr__().encode("utf-8")
    return hasher(bytestr).hexdigest()


def check_product(product, references, checks, local_only=False):
    try:
        collect_files(product, references, local_only)
    except OSError:
        pdrtestlog.warning(
            "file not present and I couldn't download it or something"
        )
        return
    data = pdr.read(str(Path(references["data"], product["label_file"])))
    check_results = []
    for check in checks:
        result = check(data)
        if result is not None:
            check_results.append(check(data))
    return check_results


def just_hash(data):
    return {key: checksum_object(data[key]) for key in data.keys()}


def perform_dataset_test(mission: str, dataset: str, local_only=False):
    products, references, checks = read_test_rules(mission, dataset)
    results = {}
    for _, product in products.iterrows():
        test_results = check_product(product, references, checks, local_only)
        if not test_results:
            result_message = "successful"
        else:
            result_message = str(test_results)
        pdrtestlog.info(f"{product['product_id']}: {result_message}")
        results[product["product_id"]] = test_results
    return results


def get_nodelist(xmlfile):
    return ET.parse(xmlfile).getroot().findall(".//*")


def make_pds4_row(xmlfile):
    nodelist = get_nodelist(xmlfile)
    return {
        "product_id": next(
            node for node in nodelist if "logical_identifier" in node.tag
        ).text,
        "files": json.dumps(
            [node.text for node in nodelist if "file_name" in node.tag]
            + [str(xmlfile)]
        ),
    }


def make_pds3_row(local_path):
    label = pvl.load(local_path)
    pointer_targets = get_pds3_pointers(label)
    targets = [pt[1] for pt in pointer_targets]
    files = [local_path.name]
    for target in targets:
        if isinstance(target, str):
            files.append(target)
        elif isinstance(target, Sequence):
            files.append(target[0])
        elif isinstance(target, int):
            continue
        else:
            raise TypeError("what is this?")
    files = list(set(files))
    row = {
        "label_file": local_path.name,
        "files": json.dumps(files),
    }
    if "PRODUCT_ID" in label.keys():
        row["product_id"] = label["PRODUCT_ID"]
    else:
        row["product_id"] = local_path.stem
    return row


def get_product_row(data_path, local_only, url):
    local_path = Path(data_path, Path(url).name)
    if not local_path.exists():
        if local_only is True:
            pdrtestlog.warning(f"{local_path} not here and local_only=True")
            return {}
        label_response = requests.get(url)
        with open(local_path, "wb") as file:
            file.write(label_response.content)
    if local_path.suffix == ".xml":
        row = make_pds4_row(local_path)
    else:
        row = make_pds3_row(local_path)
    row["url_stem"] = os.path.dirname(url)
    return row


def label_urls_to_test_index(label_urls, local_only=False):
    """warning: actually downloads labels if you let it"""
    data_path = Path(REF_ROOT, "temp", "index_label_cache")
    if not data_path.exists():
        os.makedirs(data_path)
    rows = []
    for url in label_urls:
        rows.append(get_product_row(data_path, local_only, url))
    return pd.DataFrame(rows)


def regenerate_test_hashes(mission, dataset, write=True):
    rules = DATASET_TESTING_RULES[mission][dataset]
    products, references = find_test_paths(dataset, mission, rules)
    if len(products) == 0:
        pdrtestlog.warning(f"no products found for {mission} {dataset}")
        return None
    results = {}
    for _, product in products.iterrows():
        results[product["product_id"]] = check_product(
            product, references, [just_hash]
        )[0]
        pdrtestlog.info(f"hashed {product['product_id']}")
    serial = {
        product_id: json.dumps(hashes)
        for product_id, hashes in results.items()
    }
    serialframe = pd.DataFrame.from_dict(serial, orient="index")
    serialframe.columns = ["hashes"]
    serialframe["product_id"] = serialframe.index
    if write:
        hash_path = Path(REF_ROOT, "temp", "hash", f"{mission}_{dataset}.csv")
        os.makedirs(hash_path.parent, exist_ok=True)
        serialframe.to_csv(hash_path, index=None)
    return serialframe
