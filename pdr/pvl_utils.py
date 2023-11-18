"""utilities for working with the `pvl` library."""
from functools import cache

import pvl
import pvl.decoder
import pvl.grammar


class TimelessOmniDecoder(pvl.decoder.OmniDecoder):
    """"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, grammar=pvl.grammar.OmniGrammar(), **kwargs)

    def decode_datetime(self, value: str):
        raise ValueError


@cache
def cached_pvl_load(reference):
    """"""
    import pvl

    return pvl.load(reference, decoder=TimelessOmniDecoder())
