from functools import wraps, reduce
# noinspection PyProtectedMember,PyUnresolvedReferences
from inspect import signature, _empty, Signature, Parameter
from itertools import combinations, chain
from typing import Callable, Any, Mapping, Optional, Collection

from cytoolz import keyfilter
from cytoolz.curried import valfilter
from dustgoggles.tracker import TrivialTracker


def get_argnames(func: Callable) -> set[str]:
    """return names of all parameters of a function"""
    return set(signature(func).parameters.keys())


def not_optional(param: Parameter) -> bool:
    """
    is this Parameter flagged as not required according to the conventions of
    this module?
    """
    if "Optional" in str(param):
        return False
    if param.name in ("_", "__"):
        return False
    return True


def get_non_optional_argnames(func: Callable) -> set[str]:
    """
    determine names of arguments a function must receive by filtering out
    arguments explicitly annotated as Optional or named "_" or "__". Note that
    "nonoptional" here describes a _convention of this module_, not a Python
    typing requirement.
    """
    sig_dict = valfilter(not_optional, dict(signature(func).parameters))
    return set(sig_dict.keys())


# noinspection PyTypeChecker
def get_all_argnames(*funcs: Callable, nonoptional=False) -> set[str]:
    """
    return all parameter names found in the signatures of funcs. if nonoptional
    is True, don't include parameters marked as optional according to the
    conventions of this module (explicitly type-annotated as Optional or named
    _ or __)
    """
    if nonoptional is True:
        return reduce(set.union, map(get_non_optional_argnames, funcs))
    return reduce(set.union, map(get_argnames, funcs))


def filterkwargs(
    func: Callable, kwargdict: Mapping[str, Any]
) -> dict[str, Any]:
    """
    return a copy of kwargdict, discarding all keys that are not argument
    names of func.
    """
    return keyfilter(lambda k: k in get_argnames(func), kwargdict)


def call_kwargfiltered(func: Callable, *args, **kwargs) -> Any:
    """
    call a function, filtering out any keyword arguments it doesn't actually
    accept. intended to help unify signatures to call functions in a
    dispatched or sequenced fashion. NOTE: will not fix attempts to pass
    positional-only arguments by name.
    """
    # TODO: Maybe rewrite as decorator
    return func(*args, **filterkwargs(func, kwargs))


def sigparams(func: Callable) -> set[Parameter]:
    """
    examine a function and extract a set of inspect.Parameter objects from its
    signature
    """
    return set(signature(func).parameters.values())


def paramsort(params: Collection[Parameter]) -> list[Parameter]:
    """sorts signature parameters into legal order"""
    bins = {
        'POSITIONAL_ONLY': [],
        'POSITIONAL_OR_KEYWORD': [],
        'VAR_POSITIONAL': [],
        'KEYWORD_ONLY': [],
        'VAR_KEYWORD': []
    }
    for p in params:
        bins[p.kind.name].append(p)
    # noinspection PyTypeChecker
    return list(chain.from_iterable(bins.values()))


# noinspection PyProtectedMember
def sig_union(*funcs: Callable) -> Signature:
    """
    examine multiple functions and produce a Signature object describing the
    union of the parameters of all functions  -- i.e., the expected
    signature of a function that routes all its arguments to the appropriate
    elements of funcs and calls them in a dispatched, sequenced, or parallel
    fashion, rather than composed)
    """
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
    return Signature(paramsort(outparams))


def specialize(
    func: Callable,
    check: Callable[..., tuple[bool, Any]],
    error: Optional[Callable[[Exception], str]] = None,
    tracker: TrivialTracker = TrivialTracker(),
) -> Callable:
    """
    function decorator that permits dispatch of calls to func to an arbitrary
    set of special-case functions defined in check.
    replaces the pre-1.0 pdr special case checks.
    """

    @wraps(func)
    def preempt_if_special(*args, **kwargs):
        try:
            # TODO: if we want to catch the _name_ of the special case at this
            #  level, we need to change the default signature of special case
            #  checks to return the name of the special case, or do more
            #  digging into deeper levels than I like
            is_special, special_result = call_kwargfiltered(
                check, *args, **kwargs
            )
            tracker.track(check, is_special=is_special)
            if is_special is True:
                return special_result
            return call_kwargfiltered(func, *args, **kwargs)
        except Exception as ex:
            if error is None:
                raise
            return error(ex)

    preempt_if_special.__signature__ = sig_union(func, check)
    return preempt_if_special


def softquery(
    func: Callable,
    querydict: Mapping[str, Callable],
    kwargdict: dict[str, Any],
) -> dict[str, Any]:
    """
    implements a pipeline that accumulates 'information' -- more literally a
    dictionary of named parameters (kwargdict). querydict describes the
    sequence of functions to call and the parameter names they will populate
    in kwargdict. a function in querydict may use information gathered by
    preceding functions or passed explicitly to softquery in kwargdict,
    so long as the keys of kwargdict / querydict correspond to the parameter
    names of that function.
    """
    # explanatory variables
    have_args = kwargdict.keys()
    require_args = get_all_argnames(
        func, *querydict.values(), nonoptional=True
    )
    args_to_get = require_args.difference(have_args)
    missing = args_to_get.difference(querydict)
    if len(missing) > 0:
        raise TypeError(f"Missing args in querydict: {missing}")
    for qname in querydict:
        if qname not in args_to_get.intersection(querydict):
            continue
        kwargdict["tracker"].track(querydict[qname])
        kwargdict[qname] = call_kwargfiltered(querydict[qname], **kwargdict)
    return kwargdict

