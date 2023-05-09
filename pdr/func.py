from functools import wraps, reduce
from inspect import signature
from typing import Callable, Any, Mapping

from cytoolz import keyfilter


def get_argnames(func: Callable) -> set[str]:
    """reads the names of the arguments the function will accept"""
    return set(signature(func).parameters.keys())


def filterkwargs(
    func: Callable, kwargdict: Mapping[str, Any]
) -> dict[str, Any]:
    """throws out all the keys of the dictionary that are not an argument name of the
    function"""
    return keyfilter(lambda k: k in get_argnames(func), kwargdict)


def call_kwargfiltered(func: Callable, *args, **kwargs) -> Any:
    """can use this to call a function with keyword arguments it doesn't actually
    accept (and it will throw out those keywords instead of creating an error)"""
    # TODO: Maybe rewrite as decorator
    return func(*args, **filterkwargs(func, kwargs))


def sigparams(func):
    """gives you the parameters in a specific interface that the inspect module likes for
    a function's signature"""
    return set(signature(func).parameters.values())


def sig_union(*funcs):
    """smushes the parameters from multiple function signatures together"""
    return list(reduce(set.union, map(sigparams, funcs)))


def specialize(func: Callable, check: Callable[[Any], tuple[bool, Any]]):
    """replaces the common pdr special checks by wrapping a special and non-special
    function together"""
    @wraps(func)
    def preempt_if_special(*args, **kwargs):
        is_special, special_result = check(*args, **kwargs)
        if is_special is True:
            return special_result
        return call_kwargfiltered(func, *args, **kwargs)

    preempt_if_special.__signature__ = sig_union(func, check)
    return preempt_if_special


def softquery(
    func: Callable,
    querydict: Mapping[str, Callable],
    kwargdict: dict[str, Any],
) -> dict[str, Any]:
    """accumulating pipeline of information gathering. later functions in the pipeline
    can use information gathered by earlier functions as long as the keys correspond to
    the argument names in the later functions"""
    need_args = get_argnames(func).difference(set(kwargdict.keys()))
    for qname, query in keyfilter(lambda k: k in need_args, querydict).items():
        kwargdict[qname] = call_kwargfiltered(query, **kwargdict)
    return kwargdict
