from __future__ import annotations

import enum
import io
import os
from pathlib import Path
import struct
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from numpy import ndarray


# constants
HEADER_MAGIC0 = 0xff00f0ca
HEADER_MAGIC1 = 0x1010cc28
JPEG_SOI = b'\xff\xd8'

# file type translations stored in .DAT in-file header
# this number determines how the image is decompanded

class DATFiletype(enum.Enum):
    RAW = 0
    PRED = 1
    JPEG = 2

MISSING_CONSTANT = 0  # for truncated data

DEBUG = 0  # kind of a relic atp

# for lossless compressed images
PREDSYNC = 0xffff0000


def edr_offset(_data, _name):
    """
    We need a start byte value for the ReadImage wrapper to work correctly,
    and usually the image does start after 64 bytes. start_byte is used by
     read_image, which these EDRs should never go to anyways because they
     are redirected to msl_edr_image_loader by specialize() in ReadImage.
    HITS
    * msl_mst_edr
        * all
    * msl_mhl_edr
        * all
    * msl_mrd
        * all
    """
    return True, 64


def msl_msss_edr_prefix_fn(data):
    """
    The compressed image info is stored in a .dat file, not .img. We
    only want this for the IMAGE object, not MODEL_DESC.
    HITS
    * msl_mst_edr
        * all
    * msl_mhl_edr
        * all
    * msl_mrd
        * all
    """
    target = data.filename
    target = target.replace(".img", ".dat")
    target = target.replace(".IMG", ".DAT")
    target = target.replace(".lbl", ".dat")
    target = target.replace(".LBL", ".DAT")
    return True, target


def get_special_block(data, name):
    """
    Fix for metadata not written in the label but added in dat2img.
    Is the same for all MSL EDR products produced by dat2img, specifically
    for the decompanded "image" objects. If you allow this to run for labels,
    it breaks. Necessary for show() to work correctly.

    HITS
    * msl_mst_edr
        * all
    * msl_mhl_edr
        * all
    * msl_mrd
        * all
    """

    block = data.metablock_(name)
    # metadata below copied exactly from dat2img
    block["INTERCHANGE_FORMAT"] = "BINARY"
    block["SAMPLE_TYPE"] = "UNSIGNED_INTEGER"
    block["BAND_STORAGE_TYPE"] = "BAND_SEQUENTIAL"
    block["CHECKSUM"] = "N/A"
    block["INVALID_CONSTANT"] = 0.0
    block["MISSING_CONSTANT"] = 0.0
    block["SAMPLE_BIT_MASK"] = "2#11111111#"
    return block


"""
Most everything below is rewritten in Python from the original C code for the
program dat2img to allow PDR to read MSL Mastcam Experiment Data Record (EDR)
.dat files into images. The original program decompressed an image and wrote 
to an .img alongside a new label. It has been modified to return only a numpy
array of the image to be PDR compatible. Currently it does not return the 
header info used in decompanding and stored in the .dat file, although it does 
decode it. 

dat2img was originally written by Malin Space Science Systems (MSSS) with 
contributions by Tobias Thierer and Michael Caplinger. It was then archived 
alongside MSL mission data in the PDS. The contents below are from dat2img.c,
the main decompression code, and pdecom_msl.c, for decompressing "lossless" 
compressed images. 

Some comments are carried over verbatim from the original C code. These are 
marked with "-msss".  

Most function names are the same.

Some of the functions retain MSSS debugging hooks, but this isn't wired into 
PDR right now. 
"""


class Header:
    """
    Class for storing header info decoded from the first ~64
    bytes of the image .dat file.
    This was called header_t in dat2img.
    """
    def __init__(self):
        self.width = 0
        self.height = 0
        self.col_offset = 0
        self.row_offset = 0
        self.bits_per_element = 0
        self.depth = 0
        self.bands = 0
        self.thumbnail = 0
        self.image_type = DATFiletype.RAW


def read_header(fd: int) -> list[int] | None:
    """
    Search for magic number in first 1000 bytes -msss.
    Beginning will be marked by "HEADER_MAGIC1".
    """
    for offset in range(1000):
        os.lseek(fd, offset, os.SEEK_SET)
        header = os.read(fd, 64)
        if not header or len(header) < 64:
            # if we hit the end of the file
            # then it's probably not valid
            return None
        # what htonl did in C
        raw_hdr = list(struct.unpack(">16I", header))
        # if last thing in list is header magic,
        # we have found a valid header
        if raw_hdr[15] == HEADER_MAGIC1:
            return raw_hdr
    return None


def decode_dat_header(fd: int):
    """
    Find header and decode raw header format, putting
    important info about the file in a Header object.
    """
    raw_hdr = read_header(fd)
    if raw_hdr is None:
        os.close(fd)
        return None

    # make a Header object and fill in the important info
    # the rest is pretty much identical to the C code
    hdr = Header()
    hdr.width = ((raw_hdr[5] >> 8) & 0xff) * 8
    if hdr.width == 0:
        hdr.width = 1648
    hdr.height = (raw_hdr[5] & 0xff) * 8
    if hdr.height == 0:
        hdr.height = 1200
    hdr.col_offset = ((raw_hdr[5] >> 24) & 0xff) * 8
    hdr.row_offset = ((raw_hdr[5] >> 16) & 0xff) * 8
    if (raw_hdr[8] & 0xff) == 0:
        if raw_hdr[8] & 0xff00:
            hdr.image_type = DATFiletype.PRED
        else:
            hdr.image_type = DATFiletype.RAW
    else:
        hdr.image_type = DATFiletype.JPEG
    hdr.thumbnail = (raw_hdr[0] >> 24) & 0x8
    hdr.bands = 1
    if hdr.image_type != DATFiletype.JPEG and raw_hdr[9] == 255:
        hdr.bits_per_element = 16
        hdr.depth = 2
    elif hdr.image_type == DATFiletype.JPEG and (raw_hdr[8] & 0xff00):
        hdr.bits_per_element = 8
        hdr.depth = 1
        hdr.bands = 3
    else:
        hdr.bits_per_element = 8
        hdr.depth = 1
    return hdr


def read_raw_image(
    fd: int, dat_hdr: Header, max_image_bytes: int
) -> "ndarray":
    """
    Read in a raw / uncompressed file and return numpy array.
    """
    import numpy as np

    # there is always a single image in raw image file -msss
    image_bytes = dat_hdr.width * dat_hdr.height * dat_hdr.depth
    os.lseek(fd, 64, os.SEEK_SET)
    raw = os.read(fd, max_image_bytes)
    bytes_read = len(raw)
    outbuf = bytearray(raw)
    if dat_hdr.depth == 2:
        # neet to swap bytes -msss
        # (og code said neet not need)
        for i in range(0, bytes_read - 1, 2):
            outbuf[i], outbuf[i+1] = outbuf[i+1], outbuf[i]
    # If the image is a raw thumbnail, the height and width in the header may
    # not match the actual image (since the stored values have been divided
    # by eight). Try to find height and width that match the data. -msss
    if bytes_read != image_bytes and dat_hdr.thumbnail:
        # Another complication.  There is extra padding in the IMG to a
        # complete record size (64 bytes). These are the two cases we have
        # found so far. -msss
        test_1 = bytes_read - 32
        test_2 = bytes_read - 56
        fixed = False  # was 0 in C
        for h in range(dat_hdr.height, dat_hdr.height + 8):
            for w in range(dat_hdr.width, dat_hdr.width + 8):
                check_size = h*w*dat_hdr.depth
                if check_size == test_1 or check_size == test_2:
                    dat_hdr.height = h
                    dat_hdr.width = w
                    image_bytes = check_size
                    fixed = True
                    break
            if fixed:
                break
        if not fixed:
            # if unable to determine image size, uses these values
            # why? unclear, it's what msss did.
            dat_hdr.height = 150
            dat_hdr.width = 206
            image_bytes = 150 * 206
    # if we read less than we're expecting, fill with MISSING_CONSTANT, 0
    if bytes_read < image_bytes:
        outbuf.extend([MISSING_CONSTANT] * (image_bytes - bytes_read))
    if len(outbuf) > image_bytes:
        # not written in this part of the code in dat2img because it was
        # structured slightly differently
        outbuf = outbuf[:image_bytes]
    dtype = np.uint16 if dat_hdr.depth == 2 else np.uint8
    arr = np.frombuffer(outbuf, dtype=dtype)
    arr = arr.reshape((dat_hdr.height, dat_hdr.width, dat_hdr.bands))
    return arr


def read_jpeg_image(fp, dat_hdr) -> tuple["ndarray", int, int]:
    """
    Decompress jpeg image and return array.
    Was called "jpeg_decom" in C code.
    """
    try:
        from PIL import Image, ImageFile
    except ImportError:
        raise ImportError(
            "The 'pillow' library is required to open JPEG-based MSL EDRs. "
            "Please install this library and try again."
        )
    import numpy as np

    fp.seek(64)
    save_pos = fp.tell()  # save beginning of image -msss
    jpeg_data = fp.read()
    # they don't really do this in the OG code explicitly, but we have to
    # find the starting bytes after the header and then use pillow for
    # loading truncated images (where there are multiple images)
    soi = jpeg_data.find(JPEG_SOI)
    if soi == -1:
        raise ValueError("Could not find JPEG start or end markers.")
    jpeg_bytes = jpeg_data[soi:]
    ImageFile.LOAD_TRUNCATED_IMAGES = True
    img = Image.open(io.BytesIO(jpeg_bytes))
    bands = len(img.getbands())
    if bands != dat_hdr.bands:
        # when there's a mismatch between number of bands in header and the
        # image we use the number in the image
        dat_hdr.bands = bands
    # changes to pixel interleaved or L / grayscale for 1 band
    img = img.convert('RGB') if bands == 3 else img.convert('L')
    arr = np.array(img)
    if bands == 1:
        arr = arr[:, :, np.newaxis]
    # look for more images -msss
    # what do we then do with them?
    more_imgs = 0
    fp.seek(save_pos + 2)
    while True:
        pos = fp.tell()
        two_bytes = fp.read(2)
        if len(two_bytes) < 2:
            break
        if int.from_bytes(two_bytes, 'big') == JPEG_SOI:
            fp.seek(pos)
            more_imgs = 1
            break
    return arr, dat_hdr.bands, more_imgs


"""
   Below code rewritten from pdecom_msl.c in dat2img. 
   MSL DEA ground software, predictive decompression
   Michael Caplinger, Malin Space Science Systems

   This is a highly preliminary version of the predictive decompressor,
   without much error checking or resync capability, for initial
   FSW testing.  Use at your own risk. -msss
"""


class InputBits:
    # was InputBits_t
    def __init__(self, fd):
        self.fd = fd  # original class didn't save fd
        self.p = 0
        self.bit = 0
        # file length -msss
        self.length = os.lseek(self.fd, 0, os.SEEK_END)
        # and reset to the beginning of the file -msss
        os.lseek(self.fd, 0, os.SEEK_SET)
        raw = os.read(self.fd, 1)
        self.byte = raw[0] if raw else 0  # from read(fd, &s->byte, 1);


def next_bit(s: InputBits) -> int:
    """
    return the next bit from the input -msss
    """
    if s.p >= s.length:
        return -1
    cbit = (s.byte >> (7 - s.bit)) & 1
    s.bit += 1
    if s.bit == 8:
        s.p += 1
        s.bit = 0
        raw = os.read(s.fd, 1)
        s.byte = raw[0] if raw else 0
    return cbit


def rewind_bytes(s: InputBits, n_bytes: int):
    """
    back up by x bytes and reset s -msss
    """
    s.p = max(0, s.p - n_bytes)
    # we read from beginning of file each time with SEEK_SET
    # instead of SEEK_CUR
    os.lseek(s.fd, s.p, os.SEEK_SET)
    s.bit = 0
    raw = os.read(s.fd, 1)
    s.byte = raw[0] if raw else 0


"""
    These tables represent the Huffman tree.  Each i is a node.  If the
    LEFT bit is set in flags, then left is the index of the next node in
    the tree; if it's clear, left is a leaf and contains the decoded value.
    RIGHT is handled similarly. -msss
"""
tree = bytes([0x03, 0x03, 0x03, 0x01, 0x03, 0x01, 0x01, 0x03, 0x02, 0x02, 0x00, 0x01, 0x01, 0x03, 0x01, 0x00,
              0x02, 0x01, 0x01, 0x00, 0x02, 0x02, 0x00, 0x00, 0x03, 0x03, 0x00, 0x03, 0x01, 0x01, 0x03, 0x02,
              0x02, 0x00, 0x01, 0x01, 0x03, 0x00, 0x01, 0x02, 0x02, 0x00, 0x02, 0x02, 0x00, 0x00, 0x03, 0x03,
              0x03, 0x01, 0x01, 0x01, 0x03, 0x02, 0x02, 0x00, 0x03, 0x03, 0x03, 0x02, 0x03, 0x03, 0x00, 0x00,
              0x03, 0x00, 0x00, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x03,
              0x00, 0x00, 0x03, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x03,
              0x00, 0x00, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00,
              0x00, 0x03, 0x03, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x03,
              0x00, 0x00, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00,
              0x00, 0x03, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00,
              0x00, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00,
              0x02, 0x02, 0x02, 0x01, 0x01, 0x03, 0x03, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03,
              0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03,
              0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03, 0x03, 0x03, 0x00, 0x00, 0x03, 0x00, 0x00, 0x03, 0x03,
              0x00, 0x00, 0x01, 0x00, 0x03, 0x00, 0x01, 0x00, 0x00, 0x03, 0x03, 0x01, 0x01, 0x03, 0x02, 0x02,
              0x00, 0x01, 0x01, 0x03, 0x00, 0x03, 0x00, 0x03, 0x02, 0x00, 0x00, 0x02, 0x02, 0x00, 0x00, 0x01,
              0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0xed, 0x17, 0x1b, 0x0c, 0x0d, 0x0e, 0x0f, 0xdd, 0x1f,
              0x12, 0x13, 0x2a, 0x08, 0xf4, 0xf0, 0xff, 0x19, 0x1a, 0xfb, 0x1c, 0x1d, 0x1e, 0x1f, 0x14, 0x18,
              0x1c, 0x23, 0x24, 0x25, 0x20, 0x27, 0x24, 0x28, 0xaa, 0x09, 0xf3, 0xef, 0x02, 0x2f, 0x30, 0x31,
              0x32, 0x33, 0x34, 0x35, 0x15, 0xe7, 0x1d, 0x39, 0x3a, 0x3b, 0x21, 0x3d, 0x3e, 0xa8, 0xa5, 0x41,
              0xa1, 0x9f, 0x44, 0x45, 0x46, 0xab, 0x9b, 0x49, 0x9d, 0x97, 0x4c, 0x4d, 0x95, 0x93, 0x50, 0x91,
              0x8f, 0x53, 0x54, 0x55, 0x56, 0x9c, 0x8b, 0x59, 0x89, 0x87, 0x5c, 0x5d, 0x8d, 0x83, 0x60, 0x81,
              0xc3, 0x63, 0x64, 0x65, 0x7d, 0xc5, 0x68, 0x79, 0x77, 0x6b, 0x6c, 0x75, 0xc8, 0x6f, 0x71, 0x6f,
              0x72, 0x73, 0x74, 0x75, 0x76, 0x6d, 0x86, 0x79, 0x69, 0x67, 0x7c, 0x7d, 0xbc, 0xb5, 0x80, 0xad,
              0x85, 0x83, 0x84, 0x85, 0x5d, 0x5b, 0x88, 0x59, 0x57, 0x8b, 0x8c, 0x55, 0x53, 0x8f, 0x51, 0x4f,
              0x92, 0x93, 0x94, 0x95, 0x4d, 0x4b, 0x98, 0x49, 0x47, 0x9b, 0x9c, 0x45, 0x43, 0x9f, 0x41, 0x3f,
              0xa2, 0xa3, 0xa4, 0x3d, 0x3b, 0xa7, 0x39, 0x37, 0xaa, 0xab, 0x35, 0x33, 0xae, 0x31, 0x2f, 0x06,
              0x0a, 0xf2, 0xb4, 0xb5, 0xb6, 0xb7, 0xb8, 0xb9, 0xba, 0x2d, 0x6b, 0xbd, 0xaf, 0xb1, 0xc0, 0xc1,
              0xb7, 0xb9, 0xc4, 0xbe, 0xc0, 0xc7, 0xc8, 0xc9, 0xca, 0xcc, 0xcc, 0xce, 0xd0, 0xcf, 0xd0, 0xd2,
              0xd4, 0xd3, 0xb3, 0x61, 0xd6, 0xd7, 0xd8, 0xd9, 0xbb, 0x63, 0xdc, 0xc1, 0x64, 0xdf, 0xe0, 0x73,
              0x7a, 0xe3, 0x7f, 0xe5, 0x25, 0xe7, 0xd7, 0xfd, 0xea, 0xeb, 0xec, 0xed, 0xee, 0x12, 0x16, 0x1a,
              0xf2, 0xf3, 0xf4, 0x1e, 0xf6, 0xde, 0xf8, 0x26, 0x2b, 0xd9, 0x07, 0x0b, 0xf1, 0x04, 0x2e, 0x18,
              0x17, 0x00, 0x14, 0xf8, 0x0c, 0x0b, 0x09, 0x0a, 0xe5, 0xec, 0xe8, 0x10, 0xe1, 0x23, 0x11, 0xdc,
              0xd8, 0xa9, 0x15, 0x16, 0x10, 0x01, 0x2d, 0x1b, 0x05, 0x2a, 0xf7, 0x0d, 0x22, 0x20, 0x21, 0xe4,
              0xeb, 0x19, 0x26, 0xe0, 0xdf, 0x28, 0x29, 0xa6, 0x2b, 0x2c, 0x11, 0xfe, 0xe9, 0xe8, 0xb0, 0xfa,
              0xf6, 0x0e, 0x38, 0x36, 0x37, 0xe3, 0x71, 0x52, 0x43, 0x3c, 0x40, 0x3f, 0xa7, 0xa2, 0x42, 0xa0,
              0x9e, 0x4b, 0x48, 0x47, 0xa4, 0xa3, 0x4a, 0x98, 0x96, 0x4f, 0x4e, 0x94, 0x92, 0x51, 0x90, 0x8e,
              0x62, 0x5b, 0x58, 0x57, 0x9a, 0x8a, 0x5a, 0x88, 0x99, 0x5f, 0x5e, 0x84, 0x82, 0x61, 0xc2, 0xc4,
              0x6a, 0x67, 0x66, 0x7c, 0xc6, 0x69, 0x78, 0x76, 0x6e, 0x6d, 0xc7, 0x72, 0x70, 0x70, 0x6e, 0x91,
              0x82, 0x7b, 0x78, 0x77, 0x8c, 0x6a, 0x7a, 0x68, 0x66, 0x7f, 0x7e, 0xb4, 0xac, 0x81, 0xae, 0x6c,
              0x8a, 0x87, 0x86, 0x5c, 0x5a, 0x89, 0x58, 0x56, 0x8e, 0x8d, 0x54, 0x52, 0x90, 0x50, 0x4e, 0xa1,
              0x9a, 0x97, 0x96, 0x4c, 0x4a, 0x99, 0x48, 0x46, 0x9e, 0x9d, 0x44, 0x42, 0xa0, 0x40, 0x3e, 0xa9,
              0xa6, 0xa5, 0x3c, 0x3a, 0xa8, 0x38, 0x36, 0xad, 0xac, 0x34, 0x32, 0xaf, 0x30, 0x2e, 0xb1, 0xb2,
              0xb3, 0xee, 0xea, 0xd5, 0xc6, 0xbf, 0xbc, 0xbb, 0x2c, 0x5f, 0xbe, 0xb0, 0xb2, 0xc3, 0xc2, 0xb8,
              0xba, 0xc5, 0xbf, 0xc9, 0xce, 0xcb, 0xca, 0xcb, 0xcd, 0xcd, 0xcf, 0xd1, 0xd2, 0xd1, 0xd3, 0x5e,
              0xd4, 0xb6, 0x60, 0xe4, 0xde, 0xdb, 0xda, 0xbd, 0x62, 0xdd, 0x65, 0x74, 0xe2, 0xe1, 0x7b, 0x7e,
              0x29, 0x80, 0xe6, 0xdb, 0xda, 0xd6, 0x03, 0xfe, 0xfb, 0xf9, 0xf5, 0xf1, 0xef, 0xf0, 0xe6, 0x13,
              0xe9, 0xf5, 0xe2, 0xf7, 0x22, 0xfa, 0xf9, 0xd5, 0x27, 0xfc, 0xfd, 0x0f, 0xfc])

flags = tree[0:]  # points to the start
left = tree[255:]  # points to byte 255 onward
right = tree[255 * 2:]  # points to byte 510 onward

LEFT = 1
RIGHT = 2


def next_value(s: InputBits) -> int:
    node = 0  # start at the root -msss
    while True:
        bit = next_bit(s)
        if bit == -1:
            return -1
        if bit == 0:
            # go left -msss
            if flags[node] & LEFT:
                node = left[node]
            else:
                return left[node]
        else:
            # go right -msss
            if flags[node] & RIGHT:
                node = right[node]
            else:
                return right[node]


def find_sync(s: InputBits, debug: bool = False) -> bool:
    """
    the logic of find_sync was originally part of decode_x (below)
    in dat2img, but that was getting messy
    """
    while True:
        sync = 0
        start_pos = s.p
        for i in range(32):
            bit = next_bit(s)
            if bit == -1:
                return False
            sync |= bit << (31 - i)
        if sync == PREDSYNC:
            if debug:
                print(f"sync at {s.p - 4}")
            return True
        else:
            # back up three bytes, reset and try again to find the sync -msss
            # the og comment says 3 but their code says 4. However, backing up
            # 4 bytes here obviously causes an infinite loop on failed sync
            rewind_bytes(s, 3)
            if debug:
                print(f"bad sync at offset {start_pos}, retrying")


def decode_x(
    width: int,
    out: bytearray,
    p_offset: int,
    s: InputBits,
    debug: bool = False
):
    if not find_sync(s, debug=debug):
        raise IOError("reached end of file before finding sync")
    prev = 0
    for i in range(width):
        val = next_value(s)
        if val == -1:
            raise IOError("end of file reached during decode_x")
        temp = val & 0xFF
        prev = (prev + temp) & 0xFF
        out[p_offset + i] = prev
    while s.bit > 0:
        next_bit(s)
    while s.p & 3:
        next_bit(s)


def pdecom(fd: int, width: int, height: int, outbuf: bytearray) -> bytearray:
    """
    main lossless decompression function for 'PRED' files.
    """
    # start after header bytes
    os.lseek(fd, 64, os.SEEK_SET)
    block = bytearray(2048*8)
    chunk = bytearray(2048*8)
    bytes_read = 0
    s = InputBits(fd)
    offset = 8*width//4  # used / in the C code
    for j in range(height // 8):
        if os.lseek(fd, 0, os.SEEK_CUR) >= s.length:
            return bytes_read
        # allocate memory
        for i in range(len(block)):
            block[i] = 0
        # p_offset is where to write to in block (which plane)
        # offset is plane size
        # in decode_x block == out
        p_offset = 0
        for i in range(4):
            decode_x(offset, block, p_offset, s)
            p_offset += offset
        # we slice up block here instead of computing pointers
        # like they did in dat2img
        pa = block[0 * offset:1 * offset]
        pb = block[1 * offset:2 * offset]
        pc = block[2 * offset:3 * offset]
        pd = block[3 * offset:4 * offset]
        z = 0

        # a0 b0 a1 b1 a2 b2 ... aN bN -msss
        # c0 d0 c1 d1 c2 d1 ... cN dN -msss
        for y in range(0, 8, 2):
            row_a = y * width
            row_c = (y + 1) * width
            for x in range(0, width, 2):
                chunk[row_a + x] = pa[z]
                chunk[row_a + x + 1] = pb[z]
                chunk[row_c + x] = pc[z]
                chunk[row_c + x + 1] = pd[z]
                z += 1
        # copy results to outbuf, they used memcpy for this
        outbuf[bytes_read:bytes_read + 8 * width] = chunk[0:8 * width]
        bytes_read += 8 * width
    return outbuf[:height * width]


def msl_edr_image_loader(infile: str | Path) -> "ndarray":
    """
    main function for processing .dat file: reads .dat header,
    sends to appropriate decompression method (for jpeg, raw, or pred)
    and then returns numpy array. was called "main" in the original C code,
    but that function also wrote a label file and output an img.

    HITS
    * msl_mst_edr
        * all
    * msl_mhl_edr
        * all
    * msl_mrd
        * all
    """
    fd = os.open(infile, os.O_RDONLY)
    import numpy as np

    try:
        dat_hdr = decode_dat_header(fd)
        if dat_hdr is None:
            raise IOError(f"Unable to decode header for {infile}\n")
        # allocate image buffer. If multiple images in JPEG, they will all have
        # the same size as specified by the header -msss
        # NOTE: unclear if the "multiple image" condition ever actually happens
        image_bytes = (
            dat_hdr.width * dat_hdr.height * dat_hdr.depth * dat_hdr.bands
        )
        max_image_bytes = image_bytes
        # maximum image size may be greater -msss
        if dat_hdr.image_type == DATFiletype.RAW and dat_hdr.thumbnail:
            max_image_bytes = (
                (dat_hdr.width + 7)
                * (dat_hdr.height + 7)
                * dat_hdr.depth
                * dat_hdr.bands
            )
        if dat_hdr.image_type == DATFiletype.RAW:
            # this did not originally have its own function, the processing was
            # all in main
            image = read_raw_image(fd, dat_hdr, max_image_bytes)
        elif dat_hdr.image_type == DATFiletype.JPEG:
            with open(infile, 'rb') as fp:
                # was called jpeg_decom
                image, dat_hdr.bands, _ = read_jpeg_image(fp, dat_hdr)
        elif dat_hdr.image_type == DATFiletype.PRED:
            # always a single image in a pred file -msss
            outbuf = bytearray(dat_hdr.width * dat_hdr.height * dat_hdr.bands)
            # originally in pdecom_msl.c
            pdecom(fd, dat_hdr.width, dat_hdr.height, outbuf)
            dtype = np.uint16 if dat_hdr.depth == 2 else np.uint8
            image = np.frombuffer(outbuf, dtype=dtype)
            if dat_hdr.bands == 1:
                image = image.reshape((dat_hdr.height, dat_hdr.width))
            else:
                image = image.reshape(
                    (dat_hdr.height, dat_hdr.width, dat_hdr.bands,)
                )
            return np.ascontiguousarray(image)
        else:
            raise ValueError(
                f"Unsupported image type {dat_hdr.image_type}. This should "
                f"not be able to happen."
            )
        if image.ndim == 3:
            # really at this point I think they should all have dim 3
            image = np.transpose(image, (2, 0, 1))
            if image.shape[0] == 1:
                # then we want to ditch the first axis if it's only 1
                image = np.squeeze(image, axis=0)
        return np.ascontiguousarray(image)
    finally:
        os.close(fd)

