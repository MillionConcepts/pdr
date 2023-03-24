from functools import wraps, reduce
from inspect import signature
from typing import Callable, Any, Mapping

from cytoolz import keyfilter


def get_argnames(func: Callable) -> set[str]:
    return set(signature(func).parameters.keys())


def filterkwargs(
    func: Callable, kwargdict: Mapping[str, Any]
) -> dict[str, Any]:
    return keyfilter(lambda k: k in get_argnames(func), kwargdict)


def call_kwargfiltered(func: Callable, *args, **kwargs) -> Any:
    return func(*args, **filterkwargs(func, kwargs))


def sigparams(func):
    return set(signature(func).parameters.values())


def sig_union(*funcs):
    return list(reduce(set.union, map(sigparams, funcs)))


def specialize(func: Callable, check: Callable[[Any], tuple[bool, Any]]):
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
    need_args = get_argnames(func).difference(set(kwargdict.keys()))
    for qname, query in keyfilter(lambda k: k in need_args, querydict).items():
        kwargdict[qname] = call_kwargfiltered(query, **kwargdict)
    return kwargdict
