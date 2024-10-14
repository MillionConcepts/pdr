import re

PDS4_NUMERICAL_DTYPE_PAT = re.compile(
    rf'(?P<cat>(Un)?[Ss]igned|Complex|IEEE754)'
    rf'(?P<order>MSB|LSB)?'
    rf'(?P<size>\d{1, 2}|Byte|BitString|Single|Double)'
)

IDICT = {'Unsigned': 'u', 'Signed': 'i'}
ODICT = {'LSB': '<', 'MSB': '>'}


def sample_types(sample_type: str) -> str:
    """
    Defines a translation from PDS3 physical data types to Python struct or
    numpy dtype format strings, using both the type and byte width specified
    (because the mapping to type alone is not consistent across PDS3).
    """
    parse = PDS4_NUMERICAL_DTYPE_PAT.match(sample_type)
    if parse is None:
        raise NotImplementedError(f"{sample_type} is not yet supported.")
    if parse['cat'] == "IEEE":
        ftype = {'Double': 'd', 'Single': 'f'}[parse['size']]
        return f"{ODICT[parse['order']]}{ftype}"
    if (itype := IDICT.get(parse['cat'])) is not None:
        if parse['size'] == 'Byte':
            return f"{itype}1"
        if parse['size'] == 'BitString':
            # TODO: unclear how to interpret this in the context of an
            #  Element_Array -- there is no width specification! Is this ever
            #  actually used? Need examples.
            raise NotImplementedError(
                'PDS4 integers in bit string representation are not currently '
                'supported'
            )
        return f"{ODICT[parse['order']]}{itype}{parse['size']}"
    if parse['cat'] == 'Complex':
        return f"{ODICT[parse['order']]}c{parse['size']}"
    raise NotImplementedError(f"{sample_type} is not yet supported.")
