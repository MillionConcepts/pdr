# TODO: unclear how to interpret bit string types in the context of
#  Element_Array -- there is no width specification! Is this ever
#  actually used? Need examples.
PDS4_DTYPE_MAPPING = {
    "ComplexLSB16": "<c16",
    "ComplexLSB8": "<c8",
    "ComplexMSB16": ">c16",
    "ComplexMSB8": ">c8",
    "IEEE754LSBDouble": "<f8",
    "IEEE754LSBSingle": "<f4",
    "IEEE754MSBDouble": ">f8",
    "IEEE754MSBSingle": ">f4",
    "SignedBitString": None,
    "SignedByte": "i1",
    "SignedLSB2": "<i2",
    "SignedLSB4": "<i4",
    "SignedLSB8": "<i8",
    "SignedMSB2": ">i2",
    "SignedMSB4": ">i4",
    "SignedMSB8": ">i8",
    "UnsignedBitString": None,
    "UnsignedByte": "u1",
    "UnsignedLSB2": "<u2",
    "UnsignedLSB4": "<u4",
    "UnsignedLSB8": "<u8",
    "UnsignedMSB2": ">u2",
    "UnsignedMSB4": ">u4",
    "UnsignedMSB8": ">u8"
}


def sample_types(sample_type: str) -> str:
    code = PDS4_DTYPE_MAPPING.get(sample_type)
    if code is None:
        raise NotImplementedError(f"{sample_type} is not yet supported.")
    return code

# PDS4_NUMERICAL_DTYPE_PAT = re.compile(
#     rf'(?P<cat>(Un)?[Ss]igned|Complex|IEEE754)'
#     rf'(?P<order>MSB|LSB)?'
#     rf'(?P<size>\d{1, 2}|Byte|BitString|Single|Double)'
# )
#
# IDICT = {'Unsigned': 'u', 'Signed': 'i'}
# ODICT = {'LSB': '<', 'MSB': '>'}
