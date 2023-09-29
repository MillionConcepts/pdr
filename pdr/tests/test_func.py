from typing import Optional

from dustgoggles.tracker import TrivialTracker

from pdr.func import (
    call_kwargfiltered,
    filterkwargs,
    get_argnames,
    get_all_argnames,
    get_non_optional_argnames,
    sigparams,
    sig_union,
    softquery,
    specialize,
)
from pdr.tests.objects import takes_a_few_things, takes_x_only


def test_filterkwargs():
    assert filterkwargs(
        takes_a_few_things,
        {"b": 1, "e": 2, "irrelevant": "now is the winter of our..."},
    ) == {"b": 1, "e": 2}


def test_call_kwargfiltered():
    assert call_kwargfiltered(takes_x_only, **{"x": 1, "y": 2}) == 2


def test_sigparams():
    sig1 = sigparams(takes_x_only)
    sig2 = sigparams(takes_a_few_things)
    assert {p.name for p in sig1} == {"x"}
    assert {p.name for p in sig2} == {"_", "a", "b", "c", "d", "e"}


def test_sig_union():
    union = sig_union(takes_x_only, takes_a_few_things)
    assert {p.name for p in union.parameters.values()} == {
        "_",
        "a",
        "b",
        "c",
        "d",
        "e",
        "x",
    }

    def dispatch(a, b, c, x, *, d=1, e=5, **_):
        if x < 5:
            return takes_a_few_things(a, b, c, d=d, e=e)
        return takes_x_only(x)

    assert dispatch(1, 2, 3, 4, d=1, e=5) == 12
    assert dispatch(1, 2, 3, 5, d=1, e=5) == 6


def test_specialize():
    def check_big(a):
        if a > 5:
            return True, a / 2
        return False, None

    ifbig = specialize(takes_a_few_things, check_big)
    # NOTE: this function cannot filter inappropriate arguments
    #  passed as positional.
    assert ifbig(a=1, b=2, c=3, d=1, e=1) == 8
    assert ifbig(a=8, b=2, c=3, d=1, e=1) == 4


def test_get_argnames():
    assert get_argnames(takes_x_only) == {"x"}


def test_get_non_optional_argnames():
    assert get_non_optional_argnames(takes_a_few_things) == {
        "a",
        "b",
        "c",
        "e",
    }


def test_get_all_argnames():
    assert get_all_argnames(takes_x_only, takes_a_few_things) == {
        "a",
        "b",
        "c",
        "d",
        "e",
        "x",
        "_",
    }
    assert get_all_argnames(
        takes_x_only, takes_a_few_things, nonoptional=True
    ) == {"a", "b", "c", "e", "x"}


def test_softquery():
    def b_gen(a):
        return a + 1

    def c_gen(a, b, nothing_really: Optional[int] = None):
        return a + b

    def f_gen(a, b, c, d, e):
        return a + b + c + d + e

    def target(a, b, c, d, e, f, tracker):
        tracker.track()
        return a * b * c * d * e * f

    querydict = {'b': b_gen, 'c': c_gen, 'f': f_gen}
    kwargdict = {'a': 5, 'd': 100, 'tracker': TrivialTracker()}
    try:
        # this should fail because the pipeline doesn't generate an 'e' and we
        # don''t have one in kwargdict
        softquery(target, querydict, kwargdict)
        raise TypeError
    except TypeError:
        pass
    kwargdict['e'] = 20
    # result should be:
    # b = a + 1 == 5 + 1 == 6
    # c = a + b == 5 + 6 == 11
    # f = a + b + c + d + e == 5 + 6 + 11 + 100 + 20 == 142
    # then: a * b * c * d * e * f == 5 * 6 * 11 * 100 * 20 * 142 == 93720000
    assert target(**softquery(target, querydict, kwargdict)) == 93720000
