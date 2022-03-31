import re
from ast import literal_eval
from operator import eq
from typing import Sequence, Iterable, Mapping

from dustgoggles.func import constant
from more_itertools import split_before
import multidict
from multidict import MultiDict

from pdr.utils import trim_label, decompress

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
    def __init__(self, on_dupe=None):
        self.names, self.aggregations = [], [multidict.MultiDict()]
        self.on_dupe = on_dupe

    def _step_out(self):
        self.add_statement(self.names.pop(), self.aggregations.pop())

    def _step_in(self, name):
        self.names.append(name)
        self.aggregations.append(multidict.MultiDict())

    def add_statement(self, parameter, value):
        self.aggregations[-1].add(parameter, value)

    def parse_statements(self, statements):
        for parameter, value in statements:
            if parameter in PVL_BLOCK_INITIALS:
                self._step_in(value)
            elif parameter.startswith(PVL_BLOCK_TERMINALS):
                # not bothering with aggregation name verification
                self._step_out()
            else:
                self.add_statement(parameter, value)
        return self.aggregations[0]


def read_pvl_label(filename):
    label = trim_label(decompress(filename)).decode('utf-8')
    uncommented_label = re.sub(r"/\*.*?(\*/|$)", "", label)
    trimmed_lines = filter(
        None, map(lambda line: line.strip(), uncommented_label.split("\n"))
    )
    statements = chunk_statements(trimmed_lines)
    return BlockParser().parse_statements(statements)


def parse_pvl_quantity_tuple(obj):
    name, quantity_string = obj.strip("()").split(",")
    quantity = {
        'value': literalize_pvl(re.search(r"\d+", quantity_string).group()),
        'units': literalize_pvl(re.search(r"<(.*)>", quantity_string).group(1))
    }
    return literalize_pvl(name), quantity


def literalize_pvl(obj):
    if isinstance(obj, Mapping):
        return obj
    try:
        return literal_eval(obj)
    except (SyntaxError, ValueError):
        if ("<" in obj) and (">" in obj):
            return parse_pvl_quantity_tuple(obj)
        return obj


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


def literalize_pvl_block(block):
    literalized = multidict_dig_and_edit(
        block,
        None,
        predicate=lambda x, y: True,
        value_set_function=lambda _, obj: literalize_pvl(obj)
    )
    return literalized
