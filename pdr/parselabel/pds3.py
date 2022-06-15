"""simple parsing utilities for PDS3 labels."""
import warnings
from ast import literal_eval
import re
from operator import eq
from typing import Iterable, Mapping, Optional

from cytoolz import groupby, identity
from dustgoggles.func import constant
from dustgoggles.structures import dig_for_keys
from more_itertools import split_before
from multidict import MultiDict

from pdr.parselabel.utils import trim_label
from pdr.utils import decompress


PVL_BLOCK_INITIALS = ("OBJECT", "GROUP", "BEGIN_OBJECT", "BEGIN_GROUP")
PVL_BLOCK_TERMINALS = ("END",)


def is_an_assignment_line(line):
    """
    pick lines that begin assignment statements.

    in PDS labels, it never (?) seems to be
    the case that people use delimiters to put multiple assignment statements
    on a line

    there is an issue with people who put '=' in text blocks --
    looking for a block of capital letters is usually good enough
    """
    if "=" not in line:
        return False
    if line[:10] != line[:10].upper():
        return False
    return True


def chunk_statements(trimmed_lines: Iterable[str]):
    """chunk trimmed lines from a pvl-text into assignment statements."""
    statements = []
    for statement in split_before(trimmed_lines, is_an_assignment_line):
        assignment = statement[0]
        try:
            parameter, value_head = map(str.strip, assignment.split("="))
        except ValueError:
            # some people like to put extra '='s on assignment lines,, like:
            # MRO:SPECIMEN_DESC      = "MONTMORILLONITE + FEOX, 100 % FECL2 SOL_N, PH=7,
            # i strongly suspect we will never make semantic use of
            # parameters like this and so we will just ignore them for now
            continue
        value_head += " ".join(map(str.strip, statement[1:]))
        statements.append((parameter, value_head))
    return statements


class BlockParser:
    def __init__(self):
        self.names, self.aggregations, self.parameters = [], [MultiDict()], []

    def _step_out(self):
        self.add_statement(self.names.pop(), self.aggregations.pop())

    def _step_in(self, name):
        self.names.append(name)
        self.aggregations.append(MultiDict())

    def add_statement(self, parameter, value):
        self.aggregations[-1].add(parameter, value)
        self.parameters.append(parameter)

    def parse_statements(self, statements):
        for parameter, value in statements:
            if parameter in PVL_BLOCK_INITIALS:
                self._step_in(value)
            elif parameter.startswith(PVL_BLOCK_TERMINALS):
                # not bothering with aggregation name verification
                self._step_out()
            else:
                self.add_statement(parameter, value)
        return self.aggregations[0], self.parameters


def read_pvl_label(filename):
    label = trim_label(decompress(filename)).decode('utf-8')
    uncommented_label = re.sub(r"/\*.*?(\*/|$)", "", label)
    trimmed_lines = filter(
        None, map(lambda line: line.strip(), uncommented_label.split("\n"))
    )
    statements = chunk_statements(trimmed_lines)
    return BlockParser().parse_statements(statements)


def parse_pvl_quantity_object(obj):
    return {
        'value': literalize_pvl(re.search(r"(\d|\.|-)+", obj).group()),
        'units': literalize_pvl(re.search(r"<(.*)>", obj).group(1))
    }


def parse_pvl_quantity_statement(statement):
    """
    parse pvl statements including quantities. returns quantities as mappings.
    this will also handle statements that do not consist entirely of
    quantities, notably including tuples of the form
    ("SOMETHING.DAT", 1000 <BYTES>) that are commonly used to specify offsets
    within files for data objects
    """
    objects = statement.strip("()").split(",")
    output = []
    for obj in objects:
        if ("<" in obj) and (">" in obj):
            output.append(parse_pvl_quantity_object(obj))
        else:
            output.append(literalize_pvl(obj))
    if len(output) == 1:
        return output[0]
    return tuple(output)


def multidict_dig_and_edit(
    input_multidict,
    target,
    input_object=None,
    predicate=eq,
    value_set_function=None
):
    output_multidict = MultiDict()
    if value_set_function is None:
        value_set_function = constant(input_object)
    for key, value in input_multidict.items():
        if isinstance(value, MultiDict):
            edited_multidict = multidict_dig_and_edit(
                value, target, input_object, predicate, value_set_function
            )
            output_multidict.add(key, edited_multidict)
            continue
        if not predicate(key, target):
            continue
        output_multidict.add(key, value_set_function(input_object, value))
    return output_multidict


def literalize_pvl(obj):
    if isinstance(obj, Mapping):
        return literalize_pvl_block(obj)
    try:
        return literal_eval(obj)
    except (SyntaxError, ValueError):
        # note: this is probably too permissive. if it causes problems we
        # can replace it with a regex check.
        if ("<" in obj) and (">" in obj):
            return parse_pvl_quantity_statement(obj)
        return obj


def literalize_pvl_block(block):
    literalized = multidict_dig_and_edit(
        block,
        None,
        predicate=lambda x, y: True,
        value_set_function=lambda _, obj: literalize_pvl(obj)
    )
    return literalized


def get_pds3_pointers(
    label: Optional[MultiDict] = None,
) -> tuple:
    """
    attempt to get all PDS3 "pointers" -- PVL parameters starting with "^" --
    from a MultiDict generated from a PDS3 label
    """
    return dig_for_keys(
        label, lambda k, _: k.startswith("^"), mtypes=(dict, MultiDict)
    )


def pointerize(string: str) -> str:
    """make a string start with ^ if it didn't already"""
    return string if string.startswith("^") else "^" + string


def depointerize(string: str) -> str:
    """prevent a string from starting with ^"""
    return string[1:] if string.startswith("^") else string


def filter_duplicate_pointers(pointers):
    if pointers is None:
        return None
    # noinspection PyTypeChecker
    pt_groups = groupby(identity, pointers)
    filtered_pointers = []
    for pointer, group in pt_groups.items():
        if (
            (len(group) > 1)
            and (pointer not in ("^STRUCTURE", "^DESCRIPTION"))
        ):
            # don't waste anyone's time mentioning, that the label
            # references both ODL.TXT and VICAR2.TXT, etc.
            warnings.warn(
                f"Duplicate handling for {pointer} not yet "
                f"implemented, ignoring"
            )
        else:
            filtered_pointers.append(group[0])
    return filtered_pointers

