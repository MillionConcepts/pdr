"""simple parsing utilities for PDS3 labels."""
from ast import literal_eval
import re
from operator import eq
from pathlib import Path
from typing import Iterable, Mapping, Optional
import warnings

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

    in PDS labels, it never (?) seems to be the case that people use
    delimiters to put multiple assignment statements on a line

    there is an issue with people who put '=' in text blocks --
    looking for a block of capital letters is usually good enough
    """
    if "=" not in line:
        if line.startswith("END_OBJECT"):
            return True
        return False
    start = line[:8]
    if start != start.upper():
        return False
    return True


def chunk_statements(trimmed_lines: Iterable[str]):
    """chunk trimmed lines from a pvl-text into assignment statements."""
    statements = []
    for statement in split_before(trimmed_lines, is_an_assignment_line):
        assignment = statement[0]
        if assignment.startswith("END_OBJECT"):
            statements.append(("END_OBJECT", ""))
            continue
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
            elif (
                # ignore invalid end block statements at top level
                parameter.startswith(PVL_BLOCK_TERMINALS)
                and len(self.names) > 0
            ):
                # not bothering with aggregation name verification
                self._step_out()
            else:
                self.add_statement(parameter, value)
        return self.aggregations[0], self.parameters


def read_pvl_label(filename, deduplicate_pointers=True):
    with decompress(filename) as stream:
        if Path(filename).suffix.lower() in (".lbl", ".fmt"):
            label = trim_label(stream).decode('utf-8', errors='replace')
        else:
            label = trim_label(stream).decode('utf-8')
    uncommented_label = re.sub(r"/\*.*?(\*/|$)", "", label)
    trimmed_lines = filter(
        None, map(lambda line: line.strip(), uncommented_label.split("\n"))
    )
    statements = chunk_statements(trimmed_lines)
    mapping, params = BlockParser().parse_statements(statements)
    if deduplicate_pointers:
        pointers = get_pds3_pointers(mapping)
        mapping, params = index_duplicate_pointers(pointers, mapping, params)
    return mapping, params


def parse_pvl_quantity_object(obj):
    return {
        "value": literalize_pvl(
            re.search(r"((\d|\.|-)+|NULL|UNK|N/A)", obj).group()
        ),
        "units": literalize_pvl(re.search(r"<(.*)>", obj).group(1)),
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
        # TODO, maybe: a bit redundant
        if ("<" in obj) and (">" in obj):
            try:
                output.append(parse_pvl_quantity_object(obj))
            except AttributeError:
                # not actually-matched brackets
                output.append(obj)
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
    setter_function=None,
    key_editor=False,
    keep_values=True,
):
    """
    This function searches through a multidict's items, recursively continuing
    into any children that are themselves multidicts, looking for keys that
    match "target".
    If "key_editor" is False, the function changes the values associated with
    those keys. if it is True, the function changes the key names themselves.

    If "setter_function" is not None, it replaces those keys/values with the
    output of "setter function", executed with "input_object" and the original
    key/value as arguments. If it is None, it will simply replace them with
    "input_object".

    If "keep_values" is not True, the output_multidict will contain _only_
    edited values, causing this to also act as a filtering function.
    """
    output_multidict = MultiDict()
    if setter_function is None:
        setter_function = constant(input_object)
    for key, value in input_multidict.items():
        if isinstance(value, MultiDict):
            edited_multidict = multidict_dig_and_edit(
                value,
                target,
                input_object,
                predicate,
                setter_function,
                key_editor,
                keep_values,
            )
            if not predicate(key, target) or not key_editor:
                output_multidict.add(key, edited_multidict)
            else:
                output_multidict.add(
                    setter_function(input_object, key), edited_multidict
                )
            continue
        if not predicate(key, target):
            if keep_values:
                output_multidict.add(key, value)
            continue
        if not key_editor:
            output_multidict.add(key, setter_function(input_object, value))
        else:
            output_multidict.add(setter_function(input_object, key), value)
    return output_multidict


def literalize_pvl(obj):
    if isinstance(obj, Mapping):
        return literalize_pvl_block(obj)
    try:
        # with warnings.catch_warnings(record=True) as w:
        # warnings.simplefilter("always")
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            return literal_eval(obj)
    except (SyntaxError, ValueError):
        # note: this is very permissive, and handled downstream with a simple
        #  exception catch that should work for most cases.
        if ("<" in obj) and (">" in obj):
            return parse_pvl_quantity_statement(obj)
        return obj
        # TODO, maybe: handle sequences/sets containing unquoted character
        #  strings


def literalize_pvl_block(block):
    literalized = multidict_dig_and_edit(
        block,
        None,
        predicate=lambda x, y: True,
        setter_function=lambda _, obj: literalize_pvl(obj),
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


def index_duplicate_pointers(pointers, mapping, params):
    if pointers is None:
        return mapping, params
    # noinspection PyTypeChecker
    pt_groups = groupby(identity, pointers)
    for pointer, group in pt_groups.items():
        if (len(group) > 1) and (
            pointer not in ("^STRUCTURE", "^DESCRIPTION", "^PDS_OBJECT")
        ):
            # don't waste anyone's time mentioning, that the label
            # references both ODL.TXT and VICAR2.TXT, etc.
            warnings.warn(
                f"Duplicated {pointer}, indexing with integers after each "
                f"entry (e.g.: {pointer}_0)"
            )
            for ix in range(len(group)):
                depointer = depointerize(pointer)
                indexed_pointer = f"{pointer}_{ix}"
                indexed_depointer = f"{depointer}_{ix}"
                mapping = multidict_dig_and_edit(
                    input_multidict=mapping,
                    target=pointer,
                    input_object=list(range(len(group))),
                    setter_function=set_key_index,
                    key_editor=True,
                    keep_values=True,
                )
                mapping = multidict_dig_and_edit(
                    input_multidict=mapping,
                    target=depointer,
                    input_object=list(range(len(group))),
                    setter_function=set_key_index,
                    key_editor=True,
                    keep_values=True,
                )
                params.append(indexed_pointer)
                params.append(indexed_depointer)
                params.remove(pointer)
                params.remove(depointer)
    return mapping, params


def set_key_index(pointer_range: list, key: str) -> str:
    indexed_key = f"{key}_{pointer_range[0]}"
    pointer_range.pop(0)
    return indexed_key
