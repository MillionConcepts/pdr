from typing import Sequence, Iterable

from more_itertools import split_before
import multidict

from pdr.utils import trim_label, decompress

PVL_BLOCK_INITIALS = ("OBJECT", "GROUP", "BEGIN_OBJECT", "BEGIN_GROUP")
PVL_BLOCK_TERMINALS = ("END",)


def prune_pvl_lines(line):
    """remove comments and blank lines from a pvl-text"""
    stripped = line.strip()
    if ("/*" in line) or ("*/" in line):
        return ""
    return stripped


def is_an_assignment_line(line):
    """
    pick lines that begin assignment statements.

    in PDS labels, it never (?) seems to be
    the case that people use delimiters to put multiple assignment statements
    on a line

    there is an issue with people who put '=' in text blocks --
    looking for a block of capital letters is usually good enough
    but some people like to actually put them on the assignment line, like
    MRO:SPECIMEN_DESC      = "MONTMORILLONITE + FEOX, 100 % FECL2 SOL_N, PH=7,
    i strongly suspect we will never make semantic use of parameters like this
    and so we will just ignore them for now
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
            print(f"this line is terrible: {assignment}")
            continue
        value_head += " ".join(map(str.strip, statement[1:]))
        statements.append((parameter, value_head))
    return statements


class BlockParser:
    def __init__(self, on_dupe=None):
        self.names, self.aggregations = [], [multidict.MultiDict()]
        self.on_dupe = on_dupe

    def _step_out(self):
        # name, aggregation = self.names.pop(), self.aggregations.pop()
        # self.add_statement(name, aggregation)
        self.add_statement(self.names.pop(), self.aggregations.pop())

    def _step_in(self, name):
        self.names.append(name)
        self.aggregations.append(multidict.MultiDict())

    def add_statement(self, parameter, value):
        if self.on_dupe is not None:
            pass  # TODO: implement
        self.aggregations[-1][parameter] = value

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
    trimmed_lines = filter(None, map(prune_pvl_lines, label.split("\n")))
    statements = chunk_statements(trimmed_lines)
    return BlockParser().parse_statements(statements)
