from functools import wraps, reduce
from inspect import signature, _empty, Signature
from itertools import combinations
from typing import Callable, Any, Mapping

from cytoolz import keyfilter


def get_argnames(func: Callable) -> set[str]:
    """reads the names of the arguments the function will accept"""
    return set(signature(func).parameters.keys())


def get_non_optional_argnames(func: Callable) -> set[str]:
    """reads the names of the arguments the function will accept, filters out any
    arguments set to :Optional in the signature"""
    sig_dict = dict(signature(func).parameters)
    return {key[0] for key in
            filter(lambda item: "Optional" not in str(item[1]), sig_dict.items())}


def get_all_argnames(*funcs: Callable, nonoptional=False) -> set[str]:
    """reads the names of the arguments the function will accept, can filter out
    :Optional arguments by setting nonoptional=True"""
    if nonoptional is True:
        return reduce(set.union, map(get_non_optional_argnames, funcs))
    return reduce(set.union, map(get_argnames, funcs))


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


# noinspection PyProtectedMember
def sig_union(*funcs):
    """smushes the parameters from multiple function signatures together"""
    params = reduce(set.union, map(sigparams, funcs))
    outparams = set(p for p in params)
    for p1, p2 in combinations(params, r=2):
        # filter duplicate parameter names caused by mismatched type
        # annotations (other causes of mismatches indicate real problems)
        try:
            if p1.name != p2.name:
                continue
            if (p1._annotation == _empty) and (p2._annotation != _empty):
                outparams.remove(p1)
            elif (p1._annotation != _empty) and (p2._annotation == _empty):
                outparams.remove(p2)
            elif (p1._annotation == _empty) and (p2._annotation == _empty):
                outparams.remove(p2)
            elif p1._annotation != p2._annotation:
                raise TypeError(
                    f"{p1.name} and {p2.name} have different annotations in "
                    f"some of {funcs}, suggesting possible type mismatch."
                )
            else:
                outparams.remove(p2)
        except KeyError:
            # we already removed it
            continue
    return Signature(list(outparams))


def specialize(func: Callable, check: Callable[[Any], tuple[bool, Any]]):
    """replaces the common pdr special checks by wrapping a special and non-special
    function together"""
    @wraps(func)
    def preempt_if_special(*args, **kwargs):
        is_special, special_result = call_kwargfiltered(check, *args, **kwargs)
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
    # explanatory variables
    have_args = kwargdict.keys()
    require_args = get_all_argnames(func, *querydict.values(), nonoptional=True)
    args_to_get = require_args.difference(have_args)
    missing = args_to_get.difference(querydict)
    if len(missing) > 0:
        raise TypeError(f"Missing args in querydict: {missing}")
    for qname in querydict:
        if qname not in args_to_get.intersection(querydict):
            continue
        kwargdict[qname] = call_kwargfiltered(querydict[qname], **kwargdict)
    return kwargdict
