import enum
import io
import os
from pathlib import Path
import struct
from typing import Tuple, Optional

import numpy as np

# CONSTANTS FOR ALL FORMATS
NONE = 0x00
XPRED = 0x01
YPRED = 0x02

# PREDICTIVE DECOMPRESSION CONSTANTS
LEFT = 0x01
RIGHT = 0x02
SYNC = 0x04
ZERO_FLAG = 1 << 0
ONE_FLAG = 1 << 1

# TRANSFORM DECOMPRESSION CONSTANTS
# The transform block size -msss
BLOCKSIZE = 256
# The log (base 2) of the block size (used to avoid calculation overflow) -msss
LOGBLOCKSIZE = 8
# The size of the image block in the x and y direction -msss
BLOCKDIMENSION = 16
# The maximum number of encoding tables -msss
MAXCODES = 8
LARGE_NEGATIVE = 0x1000000
LARGE_POSITIVE = 0x2000000


def mgs_moc_comp_image_loader(filename: str) -> np.ndarray:
    """
    Read in an MGS MOC SDP .imq file, decode header, collect fragments, and
    send them to the proper decompressor.

    There are 3 formats:
    1) PRED: predicitve decompression
    2) RAW: not compressed, formats the data.
    3) XFORM: transform decompression

    The decompressed image is returned as an array.
    """
    print("made it to the reader")
    infile = open(filename, 'rb')

    total = 0  # track location fragment to fragment
    first_loop = True

    while True:
        # we iterate through fragments in the file, reading their headers and
        # either decompressing fragment by fragment (RAW / XFORM) or adding
        # fragments to a buffer until last fragment (PRED) and then
        # decompressing at once

        infile.seek(total + 2048,
                    0)  # 2048 is the length of the PDS label at top

        header_data = infile.read(MSDPHeader.HEADER_SIZE)

        if len(header_data) < MSDPHeader.HEADER_SIZE:
            # give a useful error message here
            break

        h = MSDPHeader(header_data)

        if h.length == 0:
            # no data in this fragment
            break

        print(f"Processing fragment {h.fragment}, len {h.length}")

        if (h.compression[0] & 3) == 1:
            # PRED / predictive decompression
            if first_loop:
                # could initiate outside the loop, but we only need it
                # if the image is pred compression
                collected_frags = bytearray()
                first_loop = False

            indat = infile.read(h.length)
            collected_frags.extend(indat)

            if h.status & 2:
                # indicates all fragments have been collected
                image = make_pred_image(h, collected_frags)
                infile.close()
                return image

        elif (h.compression[0] >> 2) & 3 != 0:
            # XFORM / transform
            if first_loop:
                image = []
                first_loop = False
            indat = infile.read(h.length)
            imagepart = decompress_transform_image(h, indat)
            print(np.shape(imagepart))
            image.append(imagepart.copy())

        elif ((h.compression[0] >> 2) & 3 == 1) & (
                (h.compression[0] & 3) == 1):
            raise ValueError("Error: Both pcomp and xcomp compression set.")

        else:
            # RAW / not compressed
            indat = infile.read(h.length)
            image = read_raw_image(h, indat)
            break

        infile.seek(1, 1)  # skip checksum byte, seems useless atp
        total = total + MSDPHeader.HEADER_SIZE + h.length + 1

    infile.close()
    # transform compressed images are a list of images
    return np.vstack(image)


"""
CLASSES USED BY ALL FORMATS 
"""


class MSDPHeader:
    HEADER_SIZE = 62

    def __init__(self, data: bytes):
        self.id = make_short(data[0:2])
        self.fragment = make_short(data[2:4])
        self.down_offset = make_short(data[4:6])
        self.down_length = make_short(data[6:8])
        self.time = data[8:13]
        self.status = data[13]
        self.cmd = data[14:31]
        self.context = data[31:36]
        self.gain = data[36]
        self.offset = data[37]
        self.gain_count = make_short(data[38:40])
        self.down_total = make_short(data[40:42])
        self.edit_start = data[42]
        self.edit_length = data[43]
        self.compression = data[44:52]
        self.sensors = make_short(data[52:54])
        self.other = data[54:58]
        self.length = make_long(data[58:62])


def make_short(byte_array: bytes) -> int:
    return byte_array[0] | (byte_array[1] << 8)


def make_long(byte_array: bytes) -> int:
    if len(byte_array) < 4:
        return 0
    return (byte_array[0] | (byte_array[1] << 8) |
            (byte_array[2] << 16) | (byte_array[3] << 24))


class BitStruct:
    def __init__(self, data: bytes):
        # self.bit_queue = 0
        self.bit_count = 0
        self.byte_count = 0
        self.byte_queue = data
        self.queue_size = len(data)
        self.output = 0
        self.data = data
        self.bit_queue = data[0] if len(data) > 0 else 0


"""
PREDICTIVE DECOMPRESSION
"""


def make_pred_image(h: MSDPHeader, collected_frags: bytearray) -> np.ndarray:
    """
    Manage decompression of buffer of all fragment data and return image.
    """
    huffman_table_id = h.compression[1] & 0x0f

    code, left, right = make_huffman_tree(huffman_table_id)

    image_data, height = pred_decode(h, collected_frags, code, left, right)

    if len(image_data) == 0:
        raise ValueError("No image data decompressed")

    image_array = np.frombuffer(image_data, dtype=np.uint32)

    width = h.edit_length * 16
    actual_height = len(image_array) // width

    if width > 0 and height > 0:
        image_array = image_array[:actual_height * width].reshape(
            actual_height, width)

    return image_array


def pred_decode(
        h: MSDPHeader,
        data: bytearray,
        code: bytearray,
        left: bytearray,
        right: bytearray
):
    """
    Combined implementation of decode and predictive_decomp_main from moc_sun.
    """

    height = h.down_total * 16
    width = h.edit_length * 16
    length = width * height

    prev_line = bytearray(width)
    for i in range(width):
        prev_line[i] = 0
    cur_line = bytearray(width)
    result = bytearray(height * width)

    pcomp = h.compression[0] & 3
    xpred = pcomp & 1
    ypred = (pcomp & 2) >> 1
    comp_type = 0

    if xpred:
        comp_type |= XPRED
    if ypred:
        comp_type |= YPRED

    bit_stuff = BitStruct(data)

    last_sync_pos = 0
    sync = 0xf0ca

    for y in range(height):
        # we are automatically doing sync, was optional in moc_sun
        if y % 128 == 0:
            # looking for sync & relocating to it, then decompressing that line
            if bit_stuff.bit_count != 0:
                bit_stuff.bit_count = 0
                bit_stuff.output += 1
            if (bit_stuff.output & 0x1) == 0x1:
                bit_stuff.output += 1
            if bit_stuff.output + 1 >= len(data):
                return bytes(result[:y * width]), y
            if bit_stuff.output + 1 < len(data):
                got_sync = data[bit_stuff.output] | (
                        data[bit_stuff.output + 1] << 8)
                if got_sync != sync:
                    search_start = last_sync_pos
                    search_len = length - search_start
                    found_offset = find_sync(data[search_start:], search_len,
                                             sync)
                    if found_offset is None:
                        return bytes(result[:y * width]), y
                    else:
                        bit_stuff.output = search_start + found_offset
                else:
                    last_sync_pos = bit_stuff.output

            pred_line_decompressor(cur_line,
                                   prev_line,
                                   width,
                                   comp_type | SYNC,
                                   code,
                                   left,
                                   right,
                                   sync,
                                   bit_stuff)
        else:
            pred_line_decompressor(cur_line,
                                   prev_line,
                                   width,
                                   comp_type,
                                   code,
                                   left,
                                   right,
                                   sync,
                                   bit_stuff)

        result[y * width:(y + 1) * width] = cur_line
        prev_line[:] = cur_line

    got_height = height

    return bytes(result), got_height


def pred_line_decompressor(cur_line: bytearray,
                           prev_line: bytearray,
                           width: int,
                           comp_type: int,
                           code_table: bytearray,
                           left_table: bytearray,
                           right_table: bytearray,
                           sync: int,
                           bit_stuff: BitStruct) -> None:
    """
    Send each line to correct decompression 'node' (xpred, ypred etc)
    """

    if comp_type == NONE:
        decomp_none(cur_line, width, code_table, left_table, right_table,
                    bit_stuff)
    elif comp_type == XPRED:
        decomp_xpred(cur_line, width, code_table, left_table, right_table,
                     bit_stuff)
    elif comp_type == YPRED:
        decomp_ypred(cur_line, prev_line, width, code_table, left_table,
                     right_table, bit_stuff)
    elif comp_type == (XPRED | YPRED):
        decomp_xpred_ypred(cur_line, prev_line, width, code_table, left_table,
                           right_table, bit_stuff)
    elif comp_type in [SYNC, XPRED | SYNC, YPRED | SYNC, XPRED | YPRED | SYNC]:
        decomp_sync(cur_line, prev_line, width, bit_stuff)


def delta_ok(data: bytes, offset: int, max_delta: int = 64) -> bool:
    md = 0
    for i in range(1, 32):
        if offset + i + 1 >= len(data):
            return False
        delta = abs(data[offset + i] - data[offset + i + 1])
        if delta > md:
            md = delta
    return md <= max_delta


def find_sync(data: bytes, length: int, sync: int) -> Optional[int]:
    if length < 2:
        return None
    offset = 2
    remaining = length - 2
    while remaining > 0:
        if offset + 1 >= len(data):
            break
        s = data[offset] | (data[offset + 1] << 8)
        if s == sync and delta_ok(data, offset + 2):
            return offset
        offset += 1
        remaining -= 1
    return None


def next_value(code_table: bytearray,
               left_table: bytearray,
               right_table: bytearray,
               bit_stuff: BitStruct,
               ) -> int:

    index = 0

    while True:
        if (bit_stuff.bit_queue & 0x1) == 0x0:
            if (code_table[index] & LEFT) == 0:
                value = left_table[index]
                break
            else:
                index = left_table[index]
        else:
            if (code_table[index] & RIGHT) == 0:
                value = right_table[index]
                break
            else:
                index = right_table[index]

        bit_stuff.bit_count += 1

        if bit_stuff.bit_count > 7:
            bit_stuff.bit_count = 0
            bit_stuff.output += 1
            if bit_stuff.output < len(bit_stuff.data):
                bit_stuff.bit_queue = bit_stuff.data[bit_stuff.output]
            else:
                bit_stuff.bit_queue = 0
        else:
            bit_stuff.bit_queue >>= 1

    bit_stuff.bit_count += 1

    if bit_stuff.bit_count > 7:
        bit_stuff.bit_count = 0
        bit_stuff.output += 1
        if bit_stuff.output < len(bit_stuff.data):
            bit_stuff.bit_queue = bit_stuff.data[bit_stuff.output]
        else:
            bit_stuff.bit_queue = 0
    else:
        bit_stuff.bit_queue >>= 1

    return value


def decomp_none(cur_line: bytearray,
                size: int,
                code_table: bytearray,
                left_table: bytearray,
                right_table: bytearray,
                bit_stuff: BitStruct,
                ) -> None:
    for i in range(size):
        cur_line[i] = next_value(code_table, left_table, right_table,
                                 bit_stuff)


def decomp_xpred(cur_line: bytearray,
                 size: int,
                 code_table: bytearray,
                 left_table: bytearray,
                 right_table: bytearray,
                 bit_stuff: BitStruct,
                 ) -> None:
    prev = 0
    for i in range(size):
        residual = next_value(code_table, left_table, right_table, bit_stuff)
        prev = (prev + residual) & 0xFF
        cur_line[i] = prev


def decomp_ypred(cur_line: bytearray,
                 prev_line: bytearray,
                 size: int,
                 code_table: bytearray,
                 left_table: bytearray,
                 right_table: bytearray,
                 bit_stuff: BitStruct,
                 ) -> None:
    for i in range(size):
        residual = next_value(code_table, left_table, right_table, bit_stuff)
        pixel = (residual + prev_line[i]) & 0xFF
        cur_line[i] = pixel
        prev_line[i] = pixel


def decomp_xpred_ypred(cur_line: bytearray,
                       prev_line: bytearray,
                       size: int,
                       code_table: bytearray,
                       left_table: bytearray,
                       right_table: bytearray,
                       bit_stuff: BitStruct,
                       ) -> None:
    prev_diff = 0
    for i in range(size):
        residual = next_value(code_table, left_table, right_table, bit_stuff)
        prev_diff = (prev_diff + residual) & 0xFF
        pixel = (prev_line[i] + prev_diff) & 0xFF
        cur_line[i] = pixel
        prev_line[i] = pixel


def decomp_sync(cur_line: bytearray,
                prev_line: bytearray,
                size: int,
                bit_stuff: BitStruct,
                ) -> None:
    bit_stuff.output += 2
    for i in range(size):
        if bit_stuff.output < len(bit_stuff.data):
            pixel = bit_stuff.data[bit_stuff.output]
            bit_stuff.output += 1
            cur_line[i] = pixel
            prev_line[i] = pixel
        else:
            cur_line[i] = 0
            prev_line[i] = 0
    bit_stuff.bit_count = 0
    if bit_stuff.output < len(bit_stuff.data):
        bit_stuff.bit_queue = bit_stuff.data[bit_stuff.output]


class HuffmanNode:
    def __init__(self):
        self.value = 0
        self.zero = None
        self.one = None


def ht_insert(root: Optional[HuffmanNode],
              value: int,
              code: int,
              length: int
              ) -> HuffmanNode:
    if root is None:
        root = HuffmanNode()

    if length == 0:
        root.value = value
    else:
        bit = code & 0x1
        if bit == 0:
            if root.zero is None:
                root.zero = HuffmanNode()
            ht_insert(root.zero, value, code >> 1, length - 1)
        else:
            if root.one is None:
                root.one = HuffmanNode()
            ht_insert(root.one, value, code >> 1, length - 1)

    return root


def ht_tablefy(root: HuffmanNode,
               flags: bytearray,
               zero: bytearray,
               one: bytearray,
               index: int
               ) -> int:

    local_index = index

    if root.zero is not None:
        if root.zero.zero is None and root.zero.one is None:
            flags[index] &= ~ZERO_FLAG
            zero[index] = root.zero.value
        else:
            flags[local_index] |= ZERO_FLAG
            index += 1
            zero[local_index] = index
            index = ht_tablefy(root.zero, flags, zero, one, index)

    if root.one is not None:
        if root.one.zero is None and root.one.one is None:
            flags[local_index] &= ~ONE_FLAG
            one[local_index] = root.one.value
        else:
            flags[local_index] |= ONE_FLAG
            index += 1
            one[local_index] = index
            index = ht_tablefy(root.one, flags, zero, one, index)

    return index


def ht_tree_gen(table_index: int,
                code_bits_vec: list,
                code_len_vec: list,
                code_requant_vec: list,
                ) -> HuffmanNode:
    tree = None

    code_bits = code_bits_vec[table_index]
    length = code_len_vec[table_index]
    requant = code_requant_vec[table_index]

    tree = ht_insert(tree, requant[0], code_bits[0], length[0])

    for i in range(1, 128):
        if requant[i] != requant[i - 1]:
            tree = ht_insert(tree, requant[i], code_bits[i], length[i])

    tree = ht_insert(tree, requant[255], code_bits[255], length[255])

    for i in range(254, 127, -1):
        if requant[i] != requant[i + 1]:
            tree = ht_insert(tree, requant[i], code_bits[i], length[i])

    return tree


def make_huffman_tree(huff_id: int) -> Tuple[bytearray, bytearray, bytearray]:
    """
    Make huffman tables, original code had the option to load your own,
    but that is not really applicable to PDR.
    """
    code = bytearray(256)
    left = bytearray(256)
    right = bytearray(256)

    # below lists reference tables copied directly from moc_sun in the PDS
    code_bits_vec = [code0_bits, code1_bits, code2_bits, code3_bits,
                     code4_bits, code5_bits, code6_bits, code7_bits]

    code_len_vec = [code0_len, code1_len, code2_len, code3_len,
                    code4_len, code5_len, code6_len, code7_len]

    code_requant_vec = [code_ident_requant, code_ident_requant,
                        code_ident_requant, code_ident_requant,
                        code_ident_requant, code_ident_requant,
                        code_ident_requant, code7_requant]

    tree = ht_tree_gen(huff_id,
                       code_bits_vec,
                       code_len_vec,
                       code_requant_vec)

    flags = bytearray(256)
    zero_arr = bytearray(256)
    one_arr = bytearray(256)

    ht_tablefy(tree, flags, zero_arr, one_arr, 0)

    code[:] = flags
    left[:] = zero_arr
    right[:] = one_arr

    return code, left, right


"""
TRANSFORM DECOMPRESSION 
"""


def decompress_transform_image(h: MSDPHeader, indat: bytearray) -> np.ndarray:
    transformer = TransformDecompressor()

    width = h.edit_length * 16
    height = h.down_length * 16
    xcomp = (h.compression[0] >> 2) & 3
    spacing = h.compression[4] | (h.compression[5] << 8)
    num_levels = (h.compression[1] >> 5) + 1
    transform = xcomp - 1

    image = transformer.decompress(
        indat,
        width,
        height,
        transform,
        spacing,
        num_levels,
    )

    return image


class BitTree:
    def __init__(self):
        self.value = 0
        self.count = 0
        self.code = 0
        self.zero = None
        self.one = None


class TransformDecompressor:
    def __init__(self):
        self.encode_trees = init_block(sizes, counts, encodings)

    def decompress(self, data, width, height, transform, spacing, num_levels):
        """
        From the c version in moc_sun:
        MOC transform decompressor main routine
        Mike Caplinger, MOC GDS Design Scientist
        SCCS @(#)main.c	1.2 1/5/94

        Adapted from a version by Terry Ligocki with SCCS
        @(#)decompress.c (decompress.c) 1.6
        """
        x_size = width
        y_size = height

        bit_stuff = BitStruct(data)
        image = np.zeros(x_size * y_size, dtype=np.uint8)
        occ = np.zeros(num_levels, dtype=np.uint32)

        num_blocks = (x_size * y_size) >> 8

        groups = read_groups(num_blocks, bit_stuff)

        for block in range(num_blocks):
            if groups[block] >= num_levels:
                print(f"Group lvl too large: {groups[block]}"
                      f" > {num_levels - 1}")
                return image.reshape(height, width)
            occ[groups[block]] += 1

        for level in range(num_levels):
            if occ[level] != 0:
                min_dc = read_bits(16, bit_stuff)
                max_dc = read_bits(16, bit_stuff)
                range_dc = max_dc - min_dc

                var = np.zeros(256, dtype=np.uint32)
                var[0] = 0
                for i in range(1, 256):
                    var[i] = read_bits(3, bit_stuff)

                block_idx = 0
                for x in range(0, x_size, 16):
                    for y in range(0, y_size, 16):
                        if groups[block_idx] == level:
                            read_block(
                                transform,
                                spacing,
                                min_dc,
                                range_dc,
                                var,
                                x,
                                y,
                                x_size,
                                image,
                                bit_stuff,
                                self.encode_trees
                            )
                        block_idx += 1
        # they had a check for how much of the data was decompressed, comparing
        # byte_count to input dat length, which we haven't passed in here
        return image.reshape(height, width)


def bit_reverse(num: int) -> int:
    # different method than og code but works
    # the same, this is faster
    return int(f"{num:032b}"[::-1], 2)


def read_bits(bit_count: int, bit_stuff: BitStruct):
    """Read specified number of bits from bit stream"""
    if bit_count > 24:
        raise ValueError(f"Asked for more than 24 bits: {bit_count}")

    bit_queue = bit_stuff.bit_queue
    bit_queue_count = bit_stuff.bit_count

    if bit_count > bit_queue_count:
        byte_count = bit_stuff.byte_count
        byte_queue = bit_stuff.byte_queue
        queue_size = bit_stuff.queue_size

        while bit_queue_count < 24:
            if byte_count == queue_size:
                if bit_queue_count >= bit_count:
                    byte_count = 0
                    break
                else:
                    raise ValueError(f"Unable to read bits: {bit_count}")

            bit_queue |= byte_queue[byte_count] << bit_queue_count
            byte_count += 1
            bit_queue_count += 8

        bit_stuff.byte_count = byte_count

    bits = bit_queue & (0xFFFFFFFF >> (32 - bit_count))
    bit_queue >>= bit_count
    bit_queue_count -= bit_count

    bit_stuff.bit_queue = bit_queue
    bit_stuff.bit_count = bit_queue_count

    return bits


def make_tree(trees, start_idx, size, bit):
    if size == 1:
        return trees[start_idx]
    count = 0
    for i in range(size):
        if (trees[start_idx + i].code & bit) == 0:
            count += 1
        else:
            break
    # internal node
    cur = BitTree()
    cur.value = 0
    cur.zero = make_tree(trees, start_idx, count, bit << 1)
    cur.one = make_tree(trees, start_idx + count, size - count, bit << 1)
    return cur


def init_block(sizes, counts, encodings):
    encode_trees = []
    for which in range(MAXCODES):
        size = int(sizes[which])
        count = counts[which]
        encoding = encodings[which]

        trees = []
        for n in range(size):
            tree = BitTree()
            if n == 0:
                tree.value = LARGE_NEGATIVE
            elif n == size - 1:
                tree.value = LARGE_POSITIVE
            else:
                tree.value = int(n) - int(size) // 2

            tree.count = count[n]
            tree.code = bit_reverse(int(encoding[n]))
            # tree.zero and tree.one are null here
            trees.append(tree)

        trees.sort(key=lambda x: x.code)

        for tree in trees:
            tree.code = bit_reverse(tree.code)

        # encode_trees[which]
        encode_trees.append(make_tree(trees, 0, size, 0x1))
    return encode_trees


def read_coef(encoding, bit_stuff):
    # traverse tree until it hits a leaf node
    while encoding.zero is not None:
        if read_bits(1, bit_stuff) == 0:
            encoding = encoding.zero
        else:
            encoding = encoding.one

    # leaf node
    value = encoding.value

    if value == LARGE_NEGATIVE:
        coef = read_bits(15, bit_stuff)
        coef |= 0x8000
        if coef & 0x8000:
            coef = coef - 0x10000
    elif value == LARGE_POSITIVE:
        coef = read_bits(15, bit_stuff)
        coef &= 0x7FFF
    else:
        coef = value
    return np.int32(coef)


def reorder(block):
    # much simpler way of writing this than what they had!
    temp = np.zeros(256, dtype=np.int32)
    for i in range(256):
        temp[i] = block[trans[i]]
    block[:] = temp


def dct_inv16_double(inp, out):
    tmp = np.zeros(16, dtype=np.float64)

    tmp[0] = inp[0]
    tmp[1] = inp[8]
    tmp[2] = inp[4]
    tmp[3] = inp[12]
    tmp[4] = inp[2]
    tmp[5] = inp[10]
    tmp[6] = inp[6]
    tmp[7] = inp[14]

    tmp[8] = inp[1] * cosineDouble[15] - inp[15] * cosineDouble[1]
    tmp[9] = inp[9] * cosineDouble[7] - inp[7] * cosineDouble[9]
    tmp[10] = inp[5] * cosineDouble[11] - inp[11] * cosineDouble[5]
    tmp[11] = inp[13] * cosineDouble[3] - inp[3] * cosineDouble[13]
    tmp[12] = inp[3] * cosineDouble[3] + inp[13] * cosineDouble[13]
    tmp[13] = inp[11] * cosineDouble[11] + inp[5] * cosineDouble[5]
    tmp[14] = inp[7] * cosineDouble[7] + inp[9] * cosineDouble[9]
    tmp[15] = inp[15] * cosineDouble[15] + inp[1] * cosineDouble[1]

    out[0] = tmp[0]
    out[1] = tmp[1]
    out[2] = tmp[2]
    out[3] = tmp[3]
    out[4] = tmp[4] * cosineDouble[14] - tmp[7] * cosineDouble[2]
    out[5] = tmp[5] * cosineDouble[6] - tmp[6] * cosineDouble[10]
    out[6] = tmp[6] * cosineDouble[6] + tmp[5] * cosineDouble[10]
    out[7] = tmp[7] * cosineDouble[14] + tmp[4] * cosineDouble[2]
    out[8] = tmp[8] + tmp[9]
    out[9] = -tmp[9] + tmp[8]
    out[10] = -tmp[10] + tmp[11]
    out[11] = tmp[11] + tmp[10]
    out[12] = tmp[12] + tmp[13]
    out[13] = -tmp[13] + tmp[12]
    out[14] = -tmp[14] + tmp[15]
    out[15] = tmp[15] + tmp[14]

    tmp1 = out[0] + out[1]
    tmp[0] = tmp1 * cosineDouble[8]
    tmp1 = -out[1] + out[0]
    tmp[1] = tmp1 * cosineDouble[8]
    tmp[2] = out[2] * cosineDouble[12] - out[3] * cosineDouble[4]
    tmp[3] = out[3] * cosineDouble[12] + out[2] * cosineDouble[4]
    tmp[4] = out[4] + out[5]
    tmp[5] = -out[5] + out[4]
    tmp[6] = -out[6] + out[7]
    tmp[7] = out[7] + out[6]
    tmp[8] = out[8]
    tmp[9] = -out[9] * cosineDouble[4] + out[14] * cosineDouble[12]
    tmp[10] = -out[10] * cosineDouble[12] - out[13] * cosineDouble[4]
    tmp[11] = out[11]
    tmp[12] = out[12]
    tmp[13] = out[13] * cosineDouble[12] - out[10] * cosineDouble[4]
    tmp[14] = out[14] * cosineDouble[4] + out[9] * cosineDouble[12]
    tmp[15] = out[15]

    out[0] = tmp[0] + tmp[3]
    out[1] = tmp[1] + tmp[2]
    out[2] = -tmp[2] + tmp[1]
    out[3] = -tmp[3] + tmp[0]
    out[4] = tmp[4]
    tmp1 = -tmp[5] + tmp[6]
    out[5] = tmp1 * cosineDouble[8]
    tmp1 = tmp[6] + tmp[5]
    out[6] = tmp1 * cosineDouble[8]
    out[7] = tmp[7]
    out[8] = tmp[8] + tmp[11]
    out[9] = tmp[9] + tmp[10]
    out[10] = -tmp[10] + tmp[9]
    out[11] = -tmp[11] + tmp[8]
    out[12] = -tmp[12] + tmp[15]
    out[13] = -tmp[13] + tmp[14]
    out[14] = tmp[14] + tmp[13]
    out[15] = tmp[15] + tmp[12]

    tmp[0] = out[0] + out[7]
    tmp[1] = out[1] + out[6]
    tmp[2] = out[2] + out[5]
    tmp[3] = out[3] + out[4]
    tmp[4] = -out[4] + out[3]
    tmp[5] = -out[5] + out[2]
    tmp[6] = -out[6] + out[1]
    tmp[7] = -out[7] + out[0]
    tmp[8] = out[8]
    tmp[9] = out[9]
    tmp1 = -out[10] + out[13]
    tmp[10] = tmp1 * cosineDouble[8]
    tmp1 = -out[11] + out[12]
    tmp[11] = tmp1 * cosineDouble[8]
    tmp1 = out[12] + out[11]
    tmp[12] = tmp1 * cosineDouble[8]
    tmp1 = out[13] + out[10]
    tmp[13] = tmp1 * cosineDouble[8]
    tmp[14] = out[14]
    tmp[15] = out[15]

    out[0] = tmp[0] + tmp[15]
    out[1] = tmp[1] + tmp[14]
    out[2] = tmp[2] + tmp[13]
    out[3] = tmp[3] + tmp[12]
    out[4] = tmp[4] + tmp[11]
    out[5] = tmp[5] + tmp[10]
    out[6] = tmp[6] + tmp[9]
    out[7] = tmp[7] + tmp[8]
    out[8] = -tmp[8] + tmp[7]
    out[9] = -tmp[9] + tmp[6]
    out[10] = -tmp[10] + tmp[5]
    out[11] = -tmp[11] + tmp[4]
    out[12] = -tmp[12] + tmp[3]
    out[13] = -tmp[13] + tmp[2]
    out[14] = -tmp[14] + tmp[1]
    out[15] = -tmp[15] + tmp[0]


def inv_fdct_16x16(inp, out):
    data = np.zeros(256, dtype=np.float64)

    data[0] = np.uint16(inp[0])
    for i in range(1, 256):
        data[i] = inp[i]

    for i in range(16):
        row = data[i * 16:(i + 1) * 16]
        dct_inv16_double(row, row)
        data[i * 16:(i + 1) * 16] = row

    data = data.reshape(16, 16).T.flatten()

    for i in range(16):
        row = data[i * 16:(i + 1) * 16]
        dct_inv16_double(row, row)
        data[i * 16:(i + 1) * 16] = row

    data = data.reshape(16, 16).T.flatten()

    for i in range(256):
        cur = int(data[i] / 127.0 + 0.5)
        cur = max(0, min(255, cur))
        out[i] = cur


"""
* 	This module calculates a "sequency" ordered, two dimensional
* 	inverse Walsh-Hadamard transform (WHT) on 16 x 16 blocks of
* 	data.  It is done as two one dimensional transforms (one of the
* 	rows followed by one of the columns).  Each one dimensional
* 	transform is implemented as a 16 point, 4 stage "butterfly".
"""


def butterfly4(inp, ii, i0, i1, i2, i3, out, oi, o0, o1, o2, o3):
    t0 = inp[ii * i0]
    t1 = inp[ii * i1]
    t2 = inp[ii * i2]
    t3 = inp[ii * i3]

    t4 = t0 + t1
    t0 = t0 - t1
    t1 = t2 + t3
    t2 = t2 - t3

    t3 = t4 + t1
    t4 = t4 - t1
    t1 = t0 + t2
    t0 = t0 - t2

    out[oi * o0] = t3
    out[oi * o1] = t1
    out[oi * o2] = t4
    out[oi * o3] = t0


def inv_fwht16_row(inp, out):
    data = np.zeros(32, dtype=np.int32)

    butterfly4(inp, 1, 0, 1, 2, 3, data, 1, 0, 1, 2, 3)
    butterfly4(inp, 1, 4, 5, 6, 7, data, 1, 4, 5, 6, 7)
    butterfly4(inp, 1, 8, 9, 10, 11, data, 1, 8, 9, 10, 11)
    butterfly4(inp, 1, 12, 13, 14, 15, data, 1, 12, 13, 14, 15)

    butterfly4(data, 1, 0, 4, 8, 12, out, 1, 0, 3, 1, 2)
    butterfly4(data, 1, 1, 5, 9, 13, out, 1, 15, 12, 14, 13)
    butterfly4(data, 1, 2, 6, 10, 14, out, 1, 7, 4, 6, 5)
    butterfly4(data, 1, 3, 7, 11, 15, out, 1, 8, 11, 9, 10)


def inv_fwht16_col(inp, out):
    data = np.zeros(16, dtype=np.int32)

    butterfly4(inp, 16, 0, 1, 2, 3, data, 1, 0, 1, 2, 3)
    butterfly4(inp, 16, 4, 5, 6, 7, data, 1, 4, 5, 6, 7)
    butterfly4(inp, 16, 8, 9, 10, 11, data, 1, 8, 9, 10, 11)
    butterfly4(inp, 16, 12, 13, 14, 15, data, 1, 12, 13, 14, 15)

    butterfly4(data, 1, 0, 4, 8, 12, out, 16, 0, 3, 1, 2)
    butterfly4(data, 1, 1, 5, 9, 13, out, 16, 15, 12, 14, 13)
    butterfly4(data, 1, 2, 6, 10, 14, out, 16, 7, 4, 6, 5)
    butterfly4(data, 1, 3, 7, 11, 15, out, 16, 8, 11, 9, 10)


def inv_fwht_16x16(inp, out):
    data = np.zeros(256, dtype=np.int32)

    data[0] = np.uint16(inp[0])
    for i in range(1, 256):
        data[i] = inp[i]

    for i in range(16):
        row = data[i * 16:(i + 1) * 16]
        inv_fwht16_row(row, row)
        data[i * 16:(i + 1) * 16] = row

    for i in range(16):
        col = data[i::16]
        inv_fwht16_col(data[i:], data[i:])

    for i in range(256):
        cur = data[i] >> 8
        cur = max(0, min(255, cur))
        out[i] = cur


def read_groups(num_blocks, bit_stuff):
    groups = np.zeros(num_blocks, dtype=np.uint32)
    for block in range(num_blocks):
        groups[block] = read_bits(3, bit_stuff)
    return groups


def read_block(transform, spacing, min_dc, range_dc, var, x, y, x_size, image,
               bit_stuff, encode_trees):
    block = np.zeros(256, dtype=np.int32)

    dc = read_bits(8, bit_stuff)
    block[0] = int(dc * range_dc / 255.0 + min_dc)

    num_zeros = read_bits(8, bit_stuff)

    last_coef_idx = 255 - num_zeros
    for i in range(1, last_coef_idx + 1):
        block[i] = read_coef(encode_trees[var[i]], bit_stuff) * spacing

    reorder(block)

    if transform == 0:
        inv_fwht_16x16(block, block)
    elif transform == 1:
        inv_fdct_16x16(block, block)

    for y0 in range(16):
        for x0 in range(16):
            image[(y + y0) * x_size + (x + x0)] = block[y0 * 16 + x0]


"""
PREDICTIVE COMPRESSION TABLES 
"""

# /* IDENTITY; NO COMPRESSION -- dumped from 'default.code' */
code0_bits = [
    0x0000, 0x0001, 0x0002, 0x0003, 0x0004, 0x0005, 0x0006, 0x0007,
    0x0008, 0x0009, 0x000a, 0x000b, 0x000c, 0x000d, 0x000e, 0x000f,
    0x0010, 0x0011, 0x0012, 0x0013, 0x0014, 0x0015, 0x0016, 0x0017,
    0x0018, 0x0019, 0x001a, 0x001b, 0x001c, 0x001d, 0x001e, 0x001f,
    0x0020, 0x0021, 0x0022, 0x0023, 0x0024, 0x0025, 0x0026, 0x0027,
    0x0028, 0x0029, 0x002a, 0x002b, 0x002c, 0x002d, 0x002e, 0x002f,
    0x0030, 0x0031, 0x0032, 0x0033, 0x0034, 0x0035, 0x0036, 0x0037,
    0x0038, 0x0039, 0x003a, 0x003b, 0x003c, 0x003d, 0x003e, 0x003f,
    0x0040, 0x0041, 0x0042, 0x0043, 0x0044, 0x0045, 0x0046, 0x0047,
    0x0048, 0x0049, 0x004a, 0x004b, 0x004c, 0x004d, 0x004e, 0x004f,
    0x0050, 0x0051, 0x0052, 0x0053, 0x0054, 0x0055, 0x0056, 0x0057,
    0x0058, 0x0059, 0x005a, 0x005b, 0x005c, 0x005d, 0x005e, 0x005f,
    0x0060, 0x0061, 0x0062, 0x0063, 0x0064, 0x0065, 0x0066, 0x0067,
    0x0068, 0x0069, 0x006a, 0x006b, 0x006c, 0x006d, 0x006e, 0x006f,
    0x0070, 0x0071, 0x0072, 0x0073, 0x0074, 0x0075, 0x0076, 0x0077,
    0x0078, 0x0079, 0x007a, 0x007b, 0x007c, 0x007d, 0x007e, 0x007f,
    0x0080, 0x0081, 0x0082, 0x0083, 0x0084, 0x0085, 0x0086, 0x0087,
    0x0088, 0x0089, 0x008a, 0x008b, 0x008c, 0x008d, 0x008e, 0x008f,
    0x0090, 0x0091, 0x0092, 0x0093, 0x0094, 0x0095, 0x0096, 0x0097,
    0x0098, 0x0099, 0x009a, 0x009b, 0x009c, 0x009d, 0x009e, 0x009f,
    0x00a0, 0x00a1, 0x00a2, 0x00a3, 0x00a4, 0x00a5, 0x00a6, 0x00a7,
    0x00a8, 0x00a9, 0x00aa, 0x00ab, 0x00ac, 0x00ad, 0x00ae, 0x00af,
    0x00b0, 0x00b1, 0x00b2, 0x00b3, 0x00b4, 0x00b5, 0x00b6, 0x00b7,
    0x00b8, 0x00b9, 0x00ba, 0x00bb, 0x00bc, 0x00bd, 0x00be, 0x00bf,
    0x00c0, 0x00c1, 0x00c2, 0x00c3, 0x00c4, 0x00c5, 0x00c6, 0x00c7,
    0x00c8, 0x00c9, 0x00ca, 0x00cb, 0x00cc, 0x00cd, 0x00ce, 0x00cf,
    0x00d0, 0x00d1, 0x00d2, 0x00d3, 0x00d4, 0x00d5, 0x00d6, 0x00d7,
    0x00d8, 0x00d9, 0x00da, 0x00db, 0x00dc, 0x00dd, 0x00de, 0x00df,
    0x00e0, 0x00e1, 0x00e2, 0x00e3, 0x00e4, 0x00e5, 0x00e6, 0x00e7,
    0x00e8, 0x00e9, 0x00ea, 0x00eb, 0x00ec, 0x00ed, 0x00ee, 0x00ef,
    0x00f0, 0x00f1, 0x00f2, 0x00f3, 0x00f4, 0x00f5, 0x00f6, 0x00f7,
    0x00f8, 0x00f9, 0x00fa, 0x00fb, 0x00fc, 0x00fd, 0x00fe, 0x00ff,
]

code0_len = [
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, 8, ]

# /* dumped from 'exp01.code' */
code1_bits = [
    0x0000, 0x0001, 0x000d, 0x0055, 0x00f5, 0x0375, 0x0135, 0x1135,
    0x5a75, 0x1a75, 0x6a75, 0x2a75, 0x4a75, 0x0a75, 0x7275, 0x3275,
    0x5275, 0x1275, 0x6275, 0x2275, 0x4275, 0x0275, 0x7c75, 0x3c75,
    0x5c75, 0x1c75, 0x6c75, 0x2c75, 0x4c75, 0x0c75, 0x7475, 0x3475,
    0x5475, 0x1475, 0x6475, 0x2475, 0x4475, 0x0475, 0x7875, 0x3875,
    0x5875, 0x1875, 0x6875, 0x2875, 0x4875, 0x0875, 0x7075, 0x3075,
    0x5075, 0x1075, 0x6075, 0x2075, 0x4075, 0x0075, 0x7fb5, 0x3fb5,
    0x5fb5, 0x1fb5, 0x6fb5, 0x2fb5, 0x4fb5, 0x0fb5, 0x77b5, 0x37b5,
    0x57b5, 0x17b5, 0x67b5, 0x27b5, 0x47b5, 0x07b5, 0x7bb5, 0x3bb5,
    0x5bb5, 0x1bb5, 0x6bb5, 0x2bb5, 0x4bb5, 0x0bb5, 0x73b5, 0x33b5,
    0x53b5, 0x13b5, 0x63b5, 0x23b5, 0x43b5, 0x03b5, 0x7db5, 0x3db5,
    0x5db5, 0x1db5, 0x6db5, 0x2db5, 0x4db5, 0x0db5, 0x75b5, 0x35b5,
    0x55b5, 0x15b5, 0x65b5, 0x25b5, 0x45b5, 0x05b5, 0x79b5, 0x39b5,
    0x59b5, 0x19b5, 0x69b5, 0x29b5, 0x49b5, 0x09b5, 0x71b5, 0x31b5,
    0x51b5, 0x11b5, 0x61b5, 0x21b5, 0x41b5, 0x01b5, 0x7eb5, 0x3eb5,
    0x5eb5, 0x1eb5, 0x3a75, 0x2eb5, 0x4eb5, 0x6eb5, 0x6675, 0x1675,
    0x5675, 0x16b5, 0x66b5, 0x26b5, 0x46b5, 0x06b5, 0x7ab5, 0x3ab5,
    0x5ab5, 0x1ab5, 0x6ab5, 0x2ab5, 0x4ab5, 0x0ab5, 0x72b5, 0x32b5,
    0x52b5, 0x12b5, 0x62b5, 0x22b5, 0x42b5, 0x02b5, 0x7cb5, 0x3cb5,
    0x5cb5, 0x1cb5, 0x6cb5, 0x2cb5, 0x4cb5, 0x0cb5, 0x74b5, 0x34b5,
    0x54b5, 0x14b5, 0x64b5, 0x24b5, 0x44b5, 0x04b5, 0x78b5, 0x38b5,
    0x58b5, 0x18b5, 0x68b5, 0x28b5, 0x48b5, 0x08b5, 0x70b5, 0x30b5,
    0x50b5, 0x10b5, 0x60b5, 0x20b5, 0x40b5, 0x00b5, 0x0eb5, 0x3f35,
    0x7f35, 0x1f35, 0x6f35, 0x2f35, 0x4f35, 0x0f35, 0x7735, 0x3735,
    0x5735, 0x1735, 0x6735, 0x2735, 0x4735, 0x0735, 0x7b35, 0x3b35,
    0x5b35, 0x1b35, 0x6b35, 0x2b35, 0x4b35, 0x0b35, 0x7335, 0x3335,
    0x5335, 0x1335, 0x6335, 0x2335, 0x5f35, 0x4335, 0x7d35, 0x3d35,
    0x5d35, 0x1d35, 0x6d35, 0x2d35, 0x4d35, 0x0d35, 0x7535, 0x3535,
    0x5535, 0x1535, 0x6535, 0x0335, 0x2535, 0x0535, 0x7935, 0x3935,
    0x5935, 0x1935, 0x6935, 0x4535, 0x2935, 0x0935, 0x7135, 0x4935,
    0x5135, 0x3135, 0x56b5, 0x36b5, 0x76b5, 0x7a75, 0x0675, 0x4675,
    0x2675, 0x3675, 0x0e75, 0x0175, 0x0035, 0x0015, 0x0005, 0x0003, ]

code1_len = [
    1, 3, 4, 7, 8, 10, 13, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 14, 12, 10, 9, 7, 5, 2, ]

# /* dumped from 'exp02.code' */
code2_bits = [
    0x0002, 0x0000, 0x0005, 0x000c, 0x0011, 0x003c, 0x00fc, 0x0101,
    0x0081, 0x0181, 0x0d81, 0x0dc1, 0x09c1, 0x0ec1, 0x76c1, 0x36c1,
    0x56c1, 0x16c1, 0x66c1, 0x26c1, 0x46c1, 0x06c1, 0x7ac1, 0x3ac1,
    0x5ac1, 0x1ac1, 0x6ac1, 0x2ac1, 0x4ac1, 0x0ac1, 0x72c1, 0x32c1,
    0x52c1, 0x12c1, 0x62c1, 0x22c1, 0x42c1, 0x02c1, 0x7cc1, 0x3cc1,
    0x5cc1, 0x1cc1, 0x6cc1, 0x2cc1, 0x4cc1, 0x0cc1, 0x74c1, 0x34c1,
    0x54c1, 0x14c1, 0x64c1, 0x24c1, 0x44c1, 0x04c1, 0x78c1, 0x38c1,
    0x58c1, 0x18c1, 0x68c1, 0x28c1, 0x48c1, 0x08c1, 0x70c1, 0x30c1,
    0x50c1, 0x10c1, 0x60c1, 0x20c1, 0x40c1, 0x00c1, 0x7f41, 0x3f41,
    0x5f41, 0x1f41, 0x6f41, 0x2f41, 0x4f41, 0x0f41, 0x7741, 0x3741,
    0x5741, 0x1741, 0x6741, 0x2741, 0x4741, 0x0741, 0x7b41, 0x3b41,
    0x5b41, 0x1b41, 0x6b41, 0x2b41, 0x4b41, 0x0b41, 0x7341, 0x3341,
    0x5341, 0x1341, 0x6341, 0x2341, 0x4341, 0x0341, 0x7d41, 0x3d41,
    0x5d41, 0x1d41, 0x6d41, 0x2d41, 0x4d41, 0x0d41, 0x7541, 0x3541,
    0x5541, 0x1541, 0x6541, 0x2541, 0x4541, 0x0541, 0x7941, 0x3941,
    0x7ec1, 0x6ec1, 0x21c1, 0x41c1, 0x4ec1, 0x5941, 0x61c1, 0x11c1,
    0x51c1, 0x1141, 0x6141, 0x2141, 0x4141, 0x0141, 0x7e41, 0x3e41,
    0x5e41, 0x1e41, 0x6e41, 0x2e41, 0x4e41, 0x0e41, 0x7641, 0x3641,
    0x5641, 0x1641, 0x6641, 0x2641, 0x4641, 0x0641, 0x7a41, 0x3a41,
    0x5a41, 0x1a41, 0x6a41, 0x2a41, 0x4a41, 0x0a41, 0x7241, 0x3241,
    0x5241, 0x1241, 0x6241, 0x2241, 0x4241, 0x0241, 0x7c41, 0x3c41,
    0x5c41, 0x1c41, 0x6c41, 0x2c41, 0x4c41, 0x0c41, 0x7441, 0x3441,
    0x5441, 0x1441, 0x1941, 0x2941, 0x4941, 0x0441, 0x7841, 0x3841,
    0x5841, 0x1841, 0x6841, 0x2841, 0x4841, 0x0841, 0x7041, 0x3041,
    0x5041, 0x1041, 0x6041, 0x2041, 0x4041, 0x0041, 0x7f81, 0x3f81,
    0x5f81, 0x1f81, 0x6f81, 0x2f81, 0x4f81, 0x2441, 0x0f81, 0x3781,
    0x5781, 0x1781, 0x6781, 0x2781, 0x4781, 0x0781, 0x7b81, 0x3b81,
    0x5b81, 0x1b81, 0x6b81, 0x7781, 0x2b81, 0x0b81, 0x7381, 0x3381,
    0x5381, 0x1381, 0x4b81, 0x6381, 0x4381, 0x2381, 0x0381, 0x31c1,
    0x4441, 0x6441, 0x7141, 0x0941, 0x2ec1, 0x6941, 0x1ec1, 0x5ec1,
    0x3ec1, 0x01c1, 0x5141, 0x3141, 0x19c1, 0x05c1, 0x0581, 0x03c1,
    0x0281, 0x0001, 0x007c, 0x0021, 0x001c, 0x0009, 0x0004, 0x0003, ]

code2_len = [
    2, 3, 3, 5, 5, 7, 8, 9, 10, 11, 12, 12, 13, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 14, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 13, 12, 12, 10, 10, 9, 8, 6, 6, 4, 4, 2, ]

# /* dumped from 'exp04.code' */
code3_bits = [
    0x0004, 0x0006, 0x0007, 0x0005, 0x000b, 0x000d, 0x0018, 0x001d,
    0x0038, 0x007d, 0x00f8, 0x0003, 0x0001, 0x0183, 0x01c3, 0x0343,
    0x02c3, 0x0683, 0x0e81, 0x08c3, 0x0181, 0x0c83, 0x1181, 0x04c3,
    0x5f41, 0x1f41, 0x6f41, 0x2f41, 0x4f41, 0x0f41, 0x7741, 0x3741,
    0x5741, 0x1741, 0x6741, 0x2741, 0x4741, 0x0741, 0x7b41, 0x3b41,
    0x5b41, 0x1b41, 0x6b41, 0x2b41, 0x4b41, 0x0b41, 0x7341, 0x3341,
    0x5341, 0x1341, 0x6341, 0x2341, 0x4341, 0x0341, 0x7d41, 0x3d41,
    0x5d41, 0x1d41, 0x6d41, 0x2d41, 0x4d41, 0x0d41, 0x7541, 0x3541,
    0x5541, 0x1541, 0x6541, 0x2541, 0x4541, 0x0541, 0x7941, 0x3941,
    0x5941, 0x1941, 0x6941, 0x2941, 0x4941, 0x0941, 0x7141, 0x3141,
    0x5141, 0x1141, 0x6141, 0x2141, 0x4141, 0x0141, 0x7e41, 0x3e41,
    0x5e41, 0x1e41, 0x6e41, 0x2e41, 0x4e41, 0x0e41, 0x7641, 0x3641,
    0x5641, 0x1641, 0x6641, 0x2641, 0x4641, 0x0641, 0x7a41, 0x3a41,
    0x5a41, 0x1a41, 0x6a41, 0x2a41, 0x4a41, 0x0a41, 0x7241, 0x4883,
    0x7f41, 0x5883, 0x1883, 0x0483, 0x7883, 0x3f41, 0x3241, 0x3c41,
    0x5c41, 0x1c41, 0x2483, 0x4483, 0x4c41, 0x0c41, 0x6483, 0x1483,
    0x5483, 0x1441, 0x6441, 0x2441, 0x4441, 0x0441, 0x7841, 0x3841,
    0x5841, 0x1841, 0x6841, 0x2841, 0x4841, 0x0841, 0x7041, 0x3041,
    0x5041, 0x1041, 0x6041, 0x2041, 0x4041, 0x0041, 0x7f81, 0x3f81,
    0x5f81, 0x1f81, 0x6f81, 0x2f81, 0x4f81, 0x0f81, 0x7781, 0x3781,
    0x5781, 0x1781, 0x5241, 0x0241, 0x4781, 0x7c41, 0x6781, 0x3b81,
    0x5b81, 0x1b81, 0x6b81, 0x2b81, 0x4b81, 0x0b81, 0x7381, 0x3381,
    0x5381, 0x1381, 0x6381, 0x2381, 0x4381, 0x0381, 0x7d81, 0x3d81,
    0x5d81, 0x1d81, 0x6d81, 0x2781, 0x0781, 0x7b81, 0x2d81, 0x3581,
    0x5581, 0x1581, 0x6581, 0x2581, 0x4581, 0x0581, 0x7981, 0x7581,
    0x4d81, 0x1981, 0x6981, 0x2981, 0x4981, 0x5981, 0x0981, 0x3181,
    0x7181, 0x24c3, 0x3981, 0x0d81, 0x2241, 0x6241, 0x1241, 0x0083,
    0x4083, 0x2083, 0x6083, 0x2883, 0x4241, 0x6883, 0x1083, 0x5083,
    0x3083, 0x3883, 0x5441, 0x3441, 0x7441, 0x2c41, 0x6c41, 0x7083,
    0x0883, 0x3483, 0x14c3, 0x1c83, 0x0cc3, 0x00c3, 0x0681, 0x0283,
    0x0281, 0x0143, 0x0081, 0x0043, 0x0101, 0x00c1, 0x0078, 0x003d,
    0x0023, 0x0021, 0x0013, 0x0011, 0x0008, 0x0009, 0x0000, 0x0002,
]

code3_len = [
    3, 3, 3, 4, 4, 5, 6, 6, 7, 7, 8, 8, 9, 9, 9, 10,
    10, 11, 12, 12, 13, 13, 14, 14, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 14, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 14, 13, 13, 12, 12, 12, 11,
    11, 10, 10, 9, 9, 8, 8, 7, 6, 6, 5, 5, 5, 4, 4, 3,
]

# /* dumped from 'exp06.code' */
code4_bits = [
    0x0005, 0x0007, 0x0004, 0x0001, 0x0010, 0x000a, 0x0009, 0x0018,
    0x001a, 0x0019, 0x0038, 0x003a, 0x0039, 0x0078, 0x007a, 0x0000,
    0x0002, 0x0006, 0x0300, 0x0102, 0x0306, 0x0480, 0x0482, 0x0486,
    0x0280, 0x0282, 0x0682, 0x0a80, 0x1680, 0x1d46, 0x0b46, 0x3e80,
    0x2d46, 0x2680, 0x0680, 0x3646, 0x5646, 0x1646, 0x6646, 0x2646,
    0x4646, 0x0646, 0x7a46, 0x3a46, 0x5a46, 0x1a46, 0x6a46, 0x2a46,
    0x4a46, 0x0a46, 0x7246, 0x3246, 0x5246, 0x1246, 0x6246, 0x2246,
    0x4246, 0x0246, 0x7c46, 0x3c46, 0x5c46, 0x1c46, 0x6c46, 0x2c46,
    0x4c46, 0x0c46, 0x7446, 0x3446, 0x5446, 0x1446, 0x6446, 0x2446,
    0x4446, 0x0446, 0x7846, 0x3846, 0x5846, 0x1846, 0x6846, 0x2846,
    0x4846, 0x0846, 0x7046, 0x3046, 0x5046, 0x1046, 0x6046, 0x2046,
    0x4046, 0x0046, 0x7f86, 0x3f86, 0x5f86, 0x1f86, 0x6f86, 0x2f86,
    0x4f86, 0x0f86, 0x7786, 0x0546, 0x2546, 0x4546, 0x6786, 0x2786,
    0x4786, 0x0786, 0x7b86, 0x3b86, 0x5b86, 0x1b86, 0x6b86, 0x2b86,
    0x7646, 0x3786, 0x7386, 0x1546, 0x6546, 0x1386, 0x6386, 0x2386,
    0x4386, 0x0386, 0x3546, 0x5546, 0x5d86, 0x1d86, 0x7546, 0x0d46,
    0x4d46, 0x0d86, 0x7586, 0x3586, 0x5586, 0x1586, 0x6586, 0x2586,
    0x4586, 0x0586, 0x7986, 0x3986, 0x5986, 0x1986, 0x6986, 0x2986,
    0x4986, 0x5786, 0x4b86, 0x3186, 0x5186, 0x1186, 0x6186, 0x0b86,
    0x0986, 0x0186, 0x7e86, 0x3e86, 0x5e86, 0x1e86, 0x6e86, 0x2e86,
    0x4e86, 0x0e86, 0x7686, 0x3686, 0x5686, 0x1686, 0x6686, 0x2686,
    0x7186, 0x2186, 0x7a86, 0x4186, 0x4686, 0x1a86, 0x6a86, 0x2a86,
    0x4a86, 0x0a86, 0x7286, 0x0686, 0x3a86, 0x5a86, 0x3286, 0x2286,
    0x4286, 0x5286, 0x6680, 0x0286, 0x6286, 0x1286, 0x1786, 0x0e46,
    0x4e46, 0x2e46, 0x4d86, 0x2d86, 0x6d86, 0x3d86, 0x7d86, 0x5386,
    0x3386, 0x6e46, 0x1e46, 0x5e46, 0x3e46, 0x7e46, 0x0146, 0x4146,
    0x2146, 0x6146, 0x1146, 0x5146, 0x3146, 0x7146, 0x0946, 0x4946,
    0x2946, 0x6946, 0x1946, 0x5946, 0x3946, 0x7946, 0x3346, 0x4680,
    0x1346, 0x1e80, 0x1b46, 0x0346, 0x0e80, 0x1a80, 0x0e82, 0x0a82,
    0x0746, 0x0086, 0x0082, 0x0080, 0x0106, 0x0302, 0x0100, 0x0182,
    0x0180, 0x00c6, 0x00fa, 0x00f8, 0x0079, 0x0042, 0x0040, 0x0026,
    0x0022, 0x0020, 0x0016, 0x0012, 0x0008, 0x000e, 0x000c, 0x0003, ]

code4_len = [
    3, 3, 4, 4, 5, 5, 5, 6, 6, 6, 7, 7, 7, 8, 8, 9,
    9, 9, 10, 10, 10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 13, 14,
    14, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 14, 15,
    14, 14, 13, 13, 13, 13, 12, 12, 11, 11, 11, 11, 10, 10, 10, 9,
    9, 8, 8, 8, 7, 7, 7, 6, 6, 6, 5, 5, 5, 4, 4, 3, ]

# /* dumped from 'exp08.code' */
code5_bits = [
    0x0008, 0x000c, 0x0006, 0x000d, 0x0007, 0x0012, 0x0009, 0x000b,
    0x0010, 0x001a, 0x0019, 0x001b, 0x0040, 0x004a, 0x0041, 0x007b,
    0x00f0, 0x00fa, 0x0003, 0x00c3, 0x000a, 0x0001, 0x0083, 0x0100,
    0x010a, 0x028a, 0x0183, 0x0300, 0x030a, 0x0301, 0x0043, 0x0480,
    0x008a, 0x0081, 0x0a43, 0x1080, 0x048a, 0x0679, 0x0643, 0x1e43,
    0x148a, 0x3a79, 0x0c80, 0x1643, 0x4079, 0x0079, 0x7f81, 0x3f81,
    0x5f81, 0x1f81, 0x6f81, 0x2f81, 0x4f81, 0x0f81, 0x7781, 0x3781,
    0x5781, 0x1781, 0x6781, 0x2781, 0x4781, 0x0781, 0x7b81, 0x3b81,
    0x5b81, 0x1b81, 0x6b81, 0x2b81, 0x4b81, 0x0b81, 0x7381, 0x3381,
    0x5381, 0x1381, 0x6381, 0x2381, 0x4381, 0x0381, 0x7d81, 0x3d81,
    0x5d81, 0x1d81, 0x6d81, 0x2d81, 0x4d81, 0x0d81, 0x7581, 0x3581,
    0x5581, 0x1581, 0x6581, 0x2581, 0x4581, 0x0581, 0x6c79, 0x6079,
    0x7c79, 0x3c79, 0x6279, 0x2279, 0x3279, 0x5279, 0x7181, 0x3181,
    0x5181, 0x1181, 0x6181, 0x2079, 0x7981, 0x0181, 0x7e81, 0x3e81,
    0x5e81, 0x1e81, 0x6e81, 0x0a79, 0x7279, 0x0e81, 0x7681, 0x3681,
    0x5681, 0x1681, 0x2a79, 0x4a79, 0x4681, 0x0681, 0x6a79, 0x1a79,
    0x5a79, 0x1a81, 0x6a81, 0x2a81, 0x4a81, 0x3981, 0x2181, 0x3281,
    0x5281, 0x1281, 0x6281, 0x2281, 0x4181, 0x0a81, 0x7c81, 0x3c81,
    0x5c81, 0x1c81, 0x6c81, 0x2c81, 0x4c81, 0x0c81, 0x7481, 0x3481,
    0x5481, 0x7281, 0x4281, 0x2481, 0x0281, 0x1481, 0x7881, 0x3881,
    0x5881, 0x1881, 0x6881, 0x6481, 0x4481, 0x2881, 0x748a, 0x4881,
    0x0881, 0x4c80, 0x348a, 0x0481, 0x6981, 0x1981, 0x5981, 0x1079,
    0x5079, 0x3079, 0x7079, 0x1c79, 0x4981, 0x2981, 0x5c79, 0x0879,
    0x4879, 0x2879, 0x6879, 0x0279, 0x0981, 0x4279, 0x1879, 0x5879,
    0x3879, 0x1279, 0x5a81, 0x3a81, 0x7a81, 0x2681, 0x6681, 0x4e81,
    0x2e81, 0x7879, 0x0479, 0x4479, 0x2479, 0x6479, 0x1479, 0x5479,
    0x3479, 0x7479, 0x0c79, 0x4c79, 0x2c79, 0x3643, 0x2e79, 0x0e79,
    0x2c80, 0x0e43, 0x1e79, 0x1679, 0x1c80, 0x0080, 0x0243, 0x0c8a,
    0x088a, 0x0880, 0x0443, 0x0701, 0x070a, 0x0700, 0x0383, 0x0101,
    0x0280, 0x0143, 0x0179, 0x018a, 0x0180, 0x0000, 0x00f9, 0x007a,
    0x0070, 0x003b, 0x0039, 0x003a, 0x0030, 0x0023, 0x0021, 0x002a,
    0x0020, 0x0013, 0x0011, 0x0002, 0x000f, 0x0005, 0x000e, 0x0004, ]

code5_len = [
    4, 4, 4, 4, 4, 5, 5, 5, 6, 6, 6, 6, 7, 7, 7, 7,
    8, 8, 8, 8, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 11, 12,
    12, 12, 12, 13, 13, 13, 13, 13, 14, 14, 15, 14, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 14, 14, 14, 14, 13, 13, 13, 13, 13, 12, 12,
    12, 12, 11, 11, 11, 11, 10, 10, 10, 9, 9, 9, 9, 9, 8, 8,
    8, 7, 7, 7, 7, 6, 6, 6, 6, 5, 5, 5, 4, 4, 4, 4, ]

# /* dumped from 'exp10.code' */
code6_bits = [
    0x000a, 0x000e, 0x0005, 0x000f, 0x0008, 0x001c, 0x0011, 0x000b,
    0x0010, 0x0014, 0x0012, 0x0019, 0x0023, 0x0040, 0x0044, 0x0032,
    0x0039, 0x003b, 0x0070, 0x0084, 0x0072, 0x00f9, 0x00fb, 0x01f0,
    0x01f4, 0x00f2, 0x0103, 0x0000, 0x0204, 0x0002, 0x0009, 0x0183,
    0x0500, 0x0304, 0x0302, 0x0509, 0x0383, 0x0900, 0x0f04, 0x0702,
    0x0003, 0x0f83, 0x0004, 0x0804, 0x1f02, 0x1789, 0x1783, 0x0f00,
    0x2102, 0x0102, 0x1803, 0x3100, 0x1100, 0x3803, 0x6e89, 0x2e89,
    0x4e89, 0x0e89, 0x7689, 0x3689, 0x5689, 0x1689, 0x6689, 0x2689,
    0x4689, 0x0689, 0x7a89, 0x3a89, 0x5a89, 0x1a89, 0x6a89, 0x2a89,
    0x4a89, 0x0a89, 0x7289, 0x3289, 0x5289, 0x1289, 0x6289, 0x2289,
    0x4289, 0x0289, 0x7c89, 0x3c89, 0x5c89, 0x1c89, 0x6c89, 0x2c89,
    0x4c89, 0x0c89, 0x7589, 0x3589, 0x6d89, 0x2d89, 0x7d89, 0x3d89,
    0x6389, 0x2389, 0x7389, 0x3389, 0x2b89, 0x4b89, 0x6889, 0x3e89,
    0x5e89, 0x0889, 0x7089, 0x3089, 0x5089, 0x1089, 0x6089, 0x2089,
    0x4089, 0x0089, 0x7f09, 0x1b89, 0x6b89, 0x1f09, 0x6f09, 0x2f09,
    0x4f09, 0x0f09, 0x3b89, 0x5b89, 0x5709, 0x1709, 0x7b89, 0x0789,
    0x4789, 0x7709, 0x7b09, 0x3b09, 0x5b09, 0x1b09, 0x6b09, 0x2b09,
    0x4b09, 0x3709, 0x4709, 0x3309, 0x0709, 0x0b09, 0x6309, 0x2309,
    0x4309, 0x7309, 0x5309, 0x0309, 0x7102, 0x3102, 0x5804, 0x1309,
    0x5489, 0x1e89, 0x7489, 0x1489, 0x6489, 0x7e89, 0x5589, 0x0189,
    0x4189, 0x2189, 0x6189, 0x0d89, 0x4489, 0x2489, 0x4d89, 0x1189,
    0x5189, 0x3189, 0x7189, 0x1d89, 0x7889, 0x0489, 0x5d89, 0x0989,
    0x4989, 0x2989, 0x6989, 0x0389, 0x5889, 0x3889, 0x4389, 0x1989,
    0x5989, 0x3989, 0x7989, 0x1389, 0x1889, 0x5389, 0x0589, 0x4589,
    0x2589, 0x0b89, 0x4889, 0x2709, 0x6709, 0x2889, 0x3489, 0x5f09,
    0x3f09, 0x6589, 0x1589, 0x5100, 0x1804, 0x7100, 0x2789, 0x3804,
    0x1102, 0x2f00, 0x0783, 0x0803, 0x0f02, 0x1004, 0x1f00, 0x0100,
    0x0f89, 0x0902, 0x0704, 0x0700, 0x0403, 0x0109, 0x0502, 0x0404,
    0x0300, 0x0203, 0x0209, 0x0202, 0x0104, 0x0200, 0x0083, 0x01f2,
    0x00f4, 0x00f0, 0x007b, 0x0079, 0x0082, 0x0074, 0x0080, 0x0043,
    0x0049, 0x0042, 0x0034, 0x0030, 0x001b, 0x0029, 0x0022, 0x0024,
    0x0020, 0x0013, 0x0001, 0x000c, 0x0018, 0x0007, 0x000d, 0x0006,
]

code6_len = [
    4, 4, 4, 4, 5, 5, 5, 5, 6, 6, 6, 6, 6, 7, 7, 7,
    7, 7, 8, 8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 10,
    11, 11, 11, 11, 11, 12, 12, 12, 12, 12, 13, 13, 13, 13, 13, 14,
    14, 14, 14, 15, 15, 14, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 14, 14,
    14, 14, 13, 13, 13, 13, 13, 13, 12, 12, 12, 12, 11, 11, 11, 11,
    11, 10, 10, 10, 10, 10, 9, 9, 9, 9, 8, 8, 8, 8, 8, 7,
    7, 7, 7, 7, 6, 6, 6, 6, 6, 5, 5, 5, 5, 4, 4, 4,
]

# /* LOSSY -- dumped from 'tmspread10.code' */
code7_bits = [
    0x0005, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000, 0x0001, 0x0001,
    0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001,
    0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001,
    0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001,
    0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001,
    0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001,
    0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001, 0x0001,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d, 0x001d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d, 0x000d,
    0x000d, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003,
    0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003,
    0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003,
    0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003,
    0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003,
    0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003, 0x0003,
    0x0003, 0x0003, 0x0003, 0x0002, 0x0002, 0x0002, 0x0002, 0x0002,
]

code7_len = [
    4, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
    3, 3, 3, 3, 3, 3, 3, 3, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 5, 5, 5, 5, 5, 5, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
    2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
]

# /* dumped from 'tmspread10.requant' */
code7_requant = [
    0, 1, 1, 1, 1, 1, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10, 100, 100, 100, 100, 100, 100, 100, 100,
    100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
    100,
    100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
    100,
    100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
    100,
    100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100, 100,
    100,
    156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156,
    156,
    156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156,
    156,
    156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156,
    156,
    156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156, 156,
    156,
    156, 156, 156, 156, 156, 156, 156, 156, 156, 246, 246, 246, 246, 246, 246,
    246,
    246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246,
    246,
    246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246,
    246,
    246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 246, 255, 255, 255, 255,
    255,
]

# /* dumped from 'default.requant' */
# /* REFINE this could be calculated instead of put into PROM (obviously) */
code_ident_requant = [
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15,
    16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
    32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
    48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63,
    64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79,
    80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91, 92, 93, 94, 95,
    96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111,
    112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126,
    127,
    128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142,
    143,
    144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158,
    159,
    160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174,
    175,
    176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190,
    191,
    192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206,
    207,
    208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222,
    223,
    224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238,
    239,
    240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254,
    255,
]

"""
TRANSFORM DECOMPRESSION TABLES
"""
# Translation table for going from row ordered vector to radially
# order vector -msss
trans = np.array([
    0, 1, 4, 9, 15, 22, 33, 43, 56, 71, 86, 104, 121, 142, 166, 189,
    2, 3, 6, 11, 17, 26, 35, 45, 58, 73, 90, 106, 123, 146, 168, 193,
    5, 7, 8, 13, 20, 28, 37, 50, 62, 75, 92, 108, 129, 150, 170, 195,
    10, 12, 14, 19, 23, 31, 41, 52, 65, 81, 96, 113, 133, 152, 175, 201,
    16, 18, 21, 24, 30, 39, 48, 59, 69, 83, 100, 119, 137, 158, 181, 203,
    25, 27, 29, 32, 40, 46, 54, 67, 79, 94, 109, 127, 143, 164, 185, 210,
    34, 36, 38, 42, 49, 55, 64, 76, 87, 102, 117, 135, 154, 176, 197, 216,
    44, 47, 51, 53, 60, 68, 77, 85, 98, 114, 131, 147, 162, 183, 208, 222,
    57, 61, 63, 66, 70, 80, 88, 99, 112, 124, 140, 159, 179, 199, 214, 227,
    72, 74, 78, 82, 84, 95, 103, 115, 125, 139, 156, 173, 190, 211, 224, 233,
    89, 91, 93, 97, 101, 110, 118, 132, 141, 157, 171, 186, 206, 220, 231, 239,
    105, 107, 111, 116, 120, 128, 136, 148, 160, 174, 187, 205, 218, 229, 237,
    244,
    122, 126, 130, 134, 138, 144, 155, 163, 180, 191, 207, 219, 226, 235, 242,
    248,
    145, 149, 151, 153, 161, 165, 177, 184, 200, 212, 221, 230, 236, 241, 246,
    251,
    167, 169, 172, 178, 182, 188, 198, 209, 215, 225, 232, 238, 243, 247, 250,
    253,
    192, 194, 196, 202, 204, 213, 217, 223, 228, 234, 240, 245, 249, 252, 254,
    255,
], dtype=np.uint8)

# cosine coefficients
cosineDouble = np.array([
    1.00000000000000000000e+00,
    9.95184726672196890000e-01,
    9.80785280403230440000e-01,
    9.56940335732208870000e-01,
    9.23879532511286750000e-01,
    8.81921264348355040000e-01,
    8.31469612302545240000e-01,
    7.73010453362736970000e-01,
    7.07106781186547530000e-01,
    6.34393284163645500000e-01,
    5.55570233019602220000e-01,
    4.71396736825997660000e-01,
    3.82683432365089760000e-01,
    2.90284677254462360000e-01,
    1.95090322016128270000e-01,
    9.80171403295606040000e-02,
])

# Number of valid bits (LSBs) in each entry in "code0" -msss
# uint8 num0[25]
num0 = np.array([
    24, 23, 20, 19, 16, 14, 13, 10,
    8, 6, 5, 3, 1, 2, 4, 7,
    9, 11, 12, 15, 17, 18, 21, 22,
    24,
], dtype=np.uint8)

# Huffman code for encoding scheme 0, zero's code is index 12 -msss
# uint32 code0[25]
code0 = np.array([
    0xffffff, 0x3fffff, 0x07ffff, 0x03ffff, 0x007fff, 0x001fff, 0x000fff,
    0x0001ff,
    0x00007f, 0x00001f, 0x00000f, 0x000003, 0x000000, 0x000001, 0x000007,
    0x00003f,
    0x0000ff, 0x0003ff, 0x0007ff, 0x003fff, 0x00ffff, 0x01ffff, 0x0fffff,
    0x1fffff,
    0x7fffff,
], dtype=np.uint32)

# Number of valid bits (LSBs) in each entry in "code1" -msss
# uint8 num1[47]
num1 = np.array([
    24, 24, 23, 22, 21, 20, 19, 18,
    17, 16, 15, 14, 13, 12, 11, 10,
    9, 8, 7, 6, 5, 4, 2, 2,
    2, 4, 5, 6, 7, 8, 9, 10,
    11, 12, 13, 14, 15, 16, 17, 18,
    19, 20, 21, 22, 23, 24, 24,
], dtype=np.uint8)

# Huffman code for encoding scheme 1, zero's code is index 23 -msss
# uint32 code1[47]
code1 = np.array([
    0xffffff, 0xbfffff, 0x5fffff, 0x2fffff, 0x17ffff, 0x0bffff, 0x05ffff,
    0x02ffff,
    0x017fff, 0x00bfff, 0x005fff, 0x002fff, 0x0017ff, 0x000bff, 0x0005ff,
    0x0002ff,
    0x00017f, 0x0000bf, 0x00005f, 0x00002f, 0x000017, 0x00000b, 0x000002,
    0x000001,
    0x000000, 0x000003, 0x000007, 0x00000f, 0x00001f, 0x00003f, 0x00007f,
    0x0000ff,
    0x0001ff, 0x0003ff, 0x0007ff, 0x000fff, 0x001fff, 0x003fff, 0x007fff,
    0x00ffff,
    0x01ffff, 0x03ffff, 0x07ffff, 0x0fffff, 0x1fffff, 0x3fffff, 0x7fffff,
], dtype=np.uint32)

# Number of valid bits (LSBs) in each entry in "code2" -msss
# uint8 num2[69]
num2 = np.array([

    24, 24, 23, 23, 22, 22, 21, 20,
    19, 19, 18, 17, 17, 16, 16, 15,
    14, 14, 13, 12, 11, 11, 10, 9,
    9, 8, 7, 7, 6, 6, 5, 4,
    4, 3, 2, 3, 3, 4, 5, 5,
    6, 7, 8, 8, 9, 10, 10, 11,
    12, 12, 13, 13, 14, 15, 15, 16,
    17, 18, 18, 19, 20, 20, 21, 21,
    22, 23, 23, 24, 24,
], dtype=np.uint8)

# Huffman code for encoding scheme 2, zero's code is index 34 -msss
# uint32 code2[69]
code2 = np.array([
    0xffffff, 0xfffffd, 0x7ffffe, 0x3ffffd, 0x1ffffe, 0x1fffff, 0x0fffff,
    0x07fffe,
    0x03fffe, 0x03ffff, 0x01fffd, 0x00fffe, 0x00ffff, 0x007ffe, 0x007fff,
    0x003fff,
    0x001ffe, 0x001fff, 0x000fff, 0x0007fe, 0x0003fe, 0x0003ff, 0x0001fe,
    0x0000fe,
    0x0000ff, 0x00007d, 0x00003e, 0x00003d, 0x00001d, 0x00001f, 0x00000d,
    0x000005,
    0x000007, 0x000001, 0x000000, 0x000003, 0x000002, 0x000006, 0x00000f,
    0x00000e,
    0x00001e, 0x00003f, 0x00007f, 0x00007e, 0x0000fd, 0x0001ff, 0x0001fd,
    0x0003fd,
    0x0007ff, 0x0007fd, 0x000ffd, 0x000ffe, 0x001ffd, 0x003ffd, 0x003ffe,
    0x007ffd,
    0x00fffd, 0x01ffff, 0x01fffe, 0x03fffd, 0x07ffff, 0x07fffd, 0x0ffffd,
    0x0ffffe,
    0x1ffffd, 0x3fffff, 0x3ffffe, 0x7ffffd, 0x7fffff,
], dtype=np.uint32)

# Number of valid bits (LSBs) in each entry in "code3" -msss
# uint8 num3[109] = {
num3 = np.array([
    23, 24, 24, 23, 23, 22, 22, 22,
    21, 21, 21, 20, 20, 19, 19, 18,
    18, 18, 17, 17, 16, 16, 16, 15,
    15, 14, 14, 14, 13, 13, 13, 12,
    12, 11, 11, 10, 10, 10, 9, 9,
    9, 8, 8, 7, 7, 6, 6, 6,
    5, 5, 4, 4, 4, 3, 3, 3,
    4, 4, 5, 5, 5, 6, 6, 7,
    7, 7, 8, 8, 8, 9, 9, 10,
    10, 11, 11, 11, 12, 12, 12, 13,
    13, 14, 14, 15, 15, 15, 16, 16,
    17, 17, 17, 18, 18, 19, 19, 19,
    20, 20, 20, 21, 21, 22, 22, 22,
    23, 23, 24, 24, 23,
], dtype=np.uint8)

# Huffman code for encoding scheme 3, zero's code is index 54  -msss
#  uint32 code3[109]
code3 = np.array([
    0x7fffff, 0xfffffd, 0xdfffff, 0x7ffffe, 0x3ffffd, 0x3ffffc, 0x1ffffe,
    0x3ffffb,
    0x0ffffe, 0x0ffffd, 0x0ffffb, 0x07fffd, 0x07ffff, 0x03fffc, 0x03ffff,
    0x01fffc,
    0x01fffe, 0x01ffff, 0x00fffe, 0x00fffd, 0x007ffc, 0x007ffd, 0x007ffb,
    0x003ffc,
    0x003fff, 0x001ffc, 0x001ffd, 0x001fff, 0x000ffc, 0x000ffd, 0x000ffb,
    0x0007fd,
    0x0007fb, 0x0003fe, 0x0003fd, 0x0001fc, 0x0001fd, 0x0001ff, 0x0000fc,
    0x0000ff,
    0x0000fb, 0x00007d, 0x00007b, 0x00003c, 0x00003d, 0x00001c, 0x00001e,
    0x00001b,
    0x00000e, 0x00000f, 0x000004, 0x000006, 0x000003, 0x000002, 0x000001,
    0x000000,
    0x000007, 0x000005, 0x00000b, 0x00000d, 0x00000c, 0x00001f, 0x00001d,
    0x00003b,
    0x00003f, 0x00003e, 0x00007f, 0x00007e, 0x00007c, 0x0000fd, 0x0000fe,
    0x0001fb,
    0x0001fe, 0x0003fb, 0x0003ff, 0x0003fc, 0x0007ff, 0x0007fe, 0x0007fc,
    0x000fff,
    0x000ffe, 0x001ffb, 0x001ffe, 0x003ffb, 0x003ffd, 0x003ffe, 0x007fff,
    0x007ffe,
    0x00fffb, 0x00ffff, 0x00fffc, 0x01fffb, 0x01fffd, 0x03fffb, 0x03fffd,
    0x03fffe,
    0x07fffb, 0x07fffe, 0x07fffc, 0x0fffff, 0x0ffffc, 0x1ffffb, 0x1ffffd,
    0x1ffffc,
    0x1fffff, 0x3ffffe, 0x5fffff, 0x7ffffd, 0x3fffff,
], dtype=np.uint32)

# Number of valid bits (LSBs) in each entry in "code4"  -msss
# num4[169]
num4 = np.array([
    22, 24, 24, 24, 24, 23, 23, 23,
    23, 22, 22, 22, 22, 21, 21, 21,
    21, 20, 20, 20, 20, 19, 19, 19,
    19, 18, 18, 18, 18, 17, 17, 17,
    17, 16, 16, 16, 16, 15, 15, 15,
    15, 14, 14, 14, 14, 13, 13, 13,
    13, 12, 12, 12, 12, 11, 11, 11,
    11, 10, 10, 10, 10, 9, 9, 9,
    9, 8, 8, 8, 8, 7, 7, 7,
    7, 6, 6, 6, 6, 5, 5, 5,
    5, 4, 4, 4, 3, 4, 4, 4,
    5, 5, 5, 5, 6, 6, 6, 6,
    7, 7, 7, 7, 8, 8, 8, 8,
    9, 9, 9, 9, 10, 10, 10, 10,
    11, 11, 11, 11, 12, 12, 12, 12,
    13, 13, 13, 13, 14, 14, 14, 14,
    15, 15, 15, 15, 16, 16, 16, 16,
    17, 17, 17, 17, 18, 18, 18, 18,
    19, 19, 19, 19, 20, 20, 20, 20,
    21, 21, 21, 21, 22, 22, 22, 22,
    23, 23, 23, 23, 24, 24, 24, 24,
    22,
], dtype=np.uint8)

#  Huffman code for encoding scheme 4, zero's code is index 84  -msss
# code4[169]
code4 = np.array([
    0x3fffff, 0xf7ffff, 0xe7ffff, 0xfdffff, 0xfffffe, 0x27ffff, 0x7bffff,
    0x3dffff,
    0x5ffffe, 0x17ffff, 0x1bffff, 0x3ffffc, 0x2ffffe, 0x0bffff, 0x0dffff,
    0x17fffc,
    0x17fffe, 0x03ffff, 0x0ffffd, 0x0bfffc, 0x0bfffe, 0x03fffd, 0x05fffd,
    0x05fffc,
    0x05fffe, 0x02ffff, 0x02fffd, 0x02fffc, 0x02fffe, 0x017fff, 0x017ffd,
    0x017ffc,
    0x017ffe, 0x00bfff, 0x00bffd, 0x00bffc, 0x00bffe, 0x005fff, 0x005ffd,
    0x005ffc,
    0x005ffe, 0x002fff, 0x002ffd, 0x002ffc, 0x002ffe, 0x0017ff, 0x0017fd,
    0x0017fc,
    0x0017fe, 0x000bff, 0x000bfd, 0x000bfc, 0x000bfe, 0x0005ff, 0x0005fd,
    0x0005fc,
    0x0005fe, 0x0002ff, 0x0002fd, 0x0002fc, 0x0002fe, 0x00017f, 0x00017d,
    0x00017c,
    0x00017e, 0x0000bf, 0x0000bd, 0x0000bc, 0x0000be, 0x00005f, 0x00005d,
    0x00005c,
    0x00005e, 0x00002f, 0x00002d, 0x00002c, 0x00002e, 0x000017, 0x000015,
    0x000014,
    0x000016, 0x000009, 0x000008, 0x00000a, 0x000003, 0x000002, 0x000000,
    0x000001,
    0x000006, 0x000004, 0x000005, 0x000007, 0x00000e, 0x00000c, 0x00000d,
    0x00000f,
    0x00001e, 0x00001c, 0x00001d, 0x00001f, 0x00003e, 0x00003c, 0x00003d,
    0x00003f,
    0x00007e, 0x00007c, 0x00007d, 0x00007f, 0x0000fe, 0x0000fc, 0x0000fd,
    0x0000ff,
    0x0001fe, 0x0001fc, 0x0001fd, 0x0001ff, 0x0003fe, 0x0003fc, 0x0003fd,
    0x0003ff,
    0x0007fe, 0x0007fc, 0x0007fd, 0x0007ff, 0x000ffe, 0x000ffc, 0x000ffd,
    0x000fff,
    0x001ffe, 0x001ffc, 0x001ffd, 0x001fff, 0x003ffe, 0x003ffc, 0x003ffd,
    0x003fff,
    0x007ffe, 0x007ffc, 0x007ffd, 0x007fff, 0x00fffe, 0x00fffc, 0x00fffd,
    0x00ffff,
    0x01fffe, 0x01fffc, 0x01fffd, 0x01ffff, 0x03fffe, 0x03fffc, 0x07fffd,
    0x05ffff,
    0x07fffe, 0x07fffc, 0x0ffffc, 0x0fffff, 0x0ffffe, 0x1ffffc, 0x1dffff,
    0x07ffff,
    0x1ffffe, 0x3ffffe, 0x3bffff, 0x37ffff, 0x7ffffe, 0x7dffff, 0x67ffff,
    0x77ffff,
    0x1fffff,
], dtype=np.uint32)

# Number of valid bits (LSBs) in each entry in "code5"  -msss
# num5[247]
num5 = np.array([
    21, 24, 24, 24, 24, 24, 24, 23,
    23, 23, 23, 23, 23, 22, 22, 22,
    22, 22, 22, 22, 21, 21, 21, 21,
    21, 20, 20, 20, 20, 20, 20, 19,
    19, 19, 19, 19, 19, 18, 18, 18,
    18, 18, 18, 17, 17, 17, 17, 17,
    17, 16, 16, 16, 16, 16, 16, 15,
    15, 15, 15, 15, 15, 14, 14, 14,
    14, 14, 14, 13, 13, 13, 13, 13,
    13, 12, 12, 12, 12, 12, 12, 11,
    11, 11, 11, 11, 11, 10, 10, 10,
    10, 10, 10, 9, 9, 9, 9, 9,
    9, 8, 8, 8, 8, 8, 8, 7,
    7, 7, 7, 7, 7, 6, 6, 6,
    6, 6, 6, 5, 5, 5, 5, 5,
    5, 5, 4, 4, 4, 5, 5, 5,
    5, 5, 5, 5, 6, 6, 6, 6,
    6, 6, 7, 7, 7, 7, 7, 7,
    8, 8, 8, 8, 8, 8, 9, 9,
    9, 9, 9, 9, 10, 10, 10, 10,
    10, 10, 11, 11, 11, 11, 11, 11,
    12, 12, 12, 12, 12, 12, 13, 13,
    13, 13, 13, 13, 14, 14, 14, 14,
    14, 14, 15, 15, 15, 15, 15, 15,
    16, 16, 16, 16, 16, 16, 17, 17,
    17, 17, 17, 17, 18, 18, 18, 18,
    18, 18, 19, 19, 19, 19, 19, 19,
    20, 20, 20, 20, 20, 20, 21, 21,
    21, 21, 21, 21, 22, 22, 22, 22,
    22, 22, 23, 23, 23, 23, 23, 23,
    24, 24, 24, 24, 24, 24, 21,
], dtype=np.uint8)

# Huffman code for encoding scheme 5, zero's code is index 123  -msss
# code5[247]
code5 = np.array([
    0x1fffff, 0xfffffd, 0xfffffe, 0xfffffa, 0xff7ffa, 0xfffffc, 0xfffff8,
    0x5ffffd,
    0x3ffffd, 0x7fbffe, 0x3f7ffa, 0x5ffffc, 0x3ffffc, 0x37ffff, 0x3fdffd,
    0x1fbffe,
    0x1f7ffa, 0x2ffffc, 0x2ffff8, 0x1ffff8, 0x0ffffd, 0x0fbffe, 0x0ffffa,
    0x17fffc,
    0x17fff8, 0x0bffff, 0x07fffd, 0x07bffe, 0x077ffa, 0x0bfffc, 0x0bfff8,
    0x05ffff,
    0x03fffd, 0x03fffe, 0x037ffa, 0x05fffc, 0x05fff8, 0x02ffff, 0x01dffd,
    0x01fffe,
    0x017ffa, 0x02fffc, 0x02fff8, 0x017fff, 0x00fffd, 0x00fffe, 0x007ffa,
    0x017ffc,
    0x017ff8, 0x00bfff, 0x005ffd, 0x003ffe, 0x00bffa, 0x00bffc, 0x00bff8,
    0x005fff,
    0x001ffd, 0x005ffe, 0x005ffa, 0x005ffc, 0x005ff8, 0x002fff, 0x002ffd,
    0x002ffe,
    0x002ffa, 0x002ffc, 0x002ff8, 0x0017ff, 0x0017fd, 0x0017fe, 0x0017fa,
    0x0017fc,
    0x0017f8, 0x000bff, 0x000bfd, 0x000bfe, 0x000bfa, 0x000bfc, 0x000bf8,
    0x0005ff,
    0x0005fd, 0x0005fe, 0x0005fa, 0x0005fc, 0x0005f8, 0x0002ff, 0x0002fd,
    0x0002fe,
    0x0002fa, 0x0002fc, 0x0002f8, 0x00017f, 0x00017d, 0x00017e, 0x00017a,
    0x00017c,
    0x000178, 0x0000bf, 0x0000bd, 0x0000be, 0x0000ba, 0x0000bc, 0x0000b8,
    0x00005f,
    0x00005d, 0x00005e, 0x00005a, 0x00005c, 0x000058, 0x00002f, 0x00002d,
    0x00002e,
    0x00002a, 0x00002c, 0x000028, 0x000017, 0x000015, 0x000019, 0x000016,
    0x000012,
    0x000014, 0x000010, 0x00000b, 0x000001, 0x000003, 0x000000, 0x000004,
    0x000002,
    0x000006, 0x000009, 0x000005, 0x000007, 0x000008, 0x00000c, 0x00000a,
    0x00000e,
    0x00000d, 0x00000f, 0x000018, 0x00001c, 0x00001a, 0x00001e, 0x00001d,
    0x00001f,
    0x000038, 0x00003c, 0x00003a, 0x00003e, 0x00003d, 0x00003f, 0x000078,
    0x00007c,
    0x00007a, 0x00007e, 0x00007d, 0x00007f, 0x0000f8, 0x0000fc, 0x0000fa,
    0x0000fe,
    0x0000fd, 0x0000ff, 0x0001f8, 0x0001fc, 0x0001fa, 0x0001fe, 0x0001fd,
    0x0001ff,
    0x0003f8, 0x0003fc, 0x0003fa, 0x0003fe, 0x0003fd, 0x0003ff, 0x0007f8,
    0x0007fc,
    0x0007fa, 0x0007fe, 0x0007fd, 0x0007ff, 0x000ff8, 0x000ffc, 0x000ffa,
    0x000ffe,
    0x000ffd, 0x000fff, 0x001ff8, 0x001ffc, 0x001ffa, 0x001ffe, 0x003ffd,
    0x001fff,
    0x003ff8, 0x003ffc, 0x003ffa, 0x007ffe, 0x007ffd, 0x003fff, 0x007ff8,
    0x007ffc,
    0x00fffa, 0x00bffe, 0x00dffd, 0x007fff, 0x00fff8, 0x00fffc, 0x01fffa,
    0x01bffe,
    0x01fffd, 0x00ffff, 0x01fff8, 0x01fffc, 0x03fffa, 0x03bffe, 0x03dffd,
    0x01ffff,
    0x03fff8, 0x03fffc, 0x07fffa, 0x07fffe, 0x07dffd, 0x03ffff, 0x07fff8,
    0x07fffc,
    0x0f7ffa, 0x0ffffe, 0x0fdffd, 0x07ffff, 0x0ffff8, 0x0ffffc, 0x1ffffa,
    0x1ffffe,
    0x1fdffd, 0x17ffff, 0x3ffff8, 0x1ffffc, 0x3ffffa, 0x3fbffe, 0x3ffffe,
    0x1ffffd,
    0x7ffff8, 0x7ffffc, 0x7f7ffa, 0x7ffffa, 0x7ffffe, 0x7ffffd, 0x0fffff,
], dtype=np.uint32)

# Number of valid bits (LSBs) in each entry in "code6"  -msss
# num6[395]
num6 = np.array([
    21, 24, 24, 24, 24, 24, 24, 24,
    24, 24, 23, 23, 23, 23, 23, 23,
    23, 23, 23, 23, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 21,
    21, 21, 21, 21, 21, 21, 21, 21,
    21, 20, 20, 20, 20, 20, 20, 20,
    20, 20, 20, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 18, 18, 18,
    18, 18, 18, 18, 18, 18, 18, 17,
    17, 17, 17, 17, 17, 17, 17, 17,
    17, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 13,
    13, 13, 13, 13, 13, 13, 13, 13,
    13, 12, 12, 12, 12, 12, 12, 12,
    12, 12, 12, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 9,
    9, 9, 9, 9, 9, 9, 9, 9,
    9, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6,
    5, 5, 5, 5, 5, 5, 5, 5,
    5, 5, 5, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7,
    8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 9, 9, 9, 9, 9, 9,
    9, 9, 9, 9, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11,
    12, 12, 12, 12, 12, 12, 12, 12,
    12, 12, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 17, 17, 17, 17, 17, 17,
    17, 17, 17, 17, 18, 18, 18, 18,
    18, 18, 18, 18, 18, 18, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19,
    20, 20, 20, 20, 20, 20, 20, 20,
    20, 20, 21, 21, 21, 21, 21, 21,
    21, 21, 21, 21, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 23, 23,
    23, 23, 23, 23, 23, 23, 23, 23,
    23, 24, 24, 24, 24, 24, 24, 24,
    24, 24, 21,
], dtype=np.uint8)

# Huffman code for encoding scheme 6, zero's code is index 197  -msss
# code6[395]
code6 = np.array([
    0x1fffff, 0xfffffe, 0xfffffc, 0xfffff8, 0xffbff8, 0xfffffd, 0xfffff9,
    0xfffffb,
    0xfffff3, 0xfffff7, 0x7ffffa, 0x5ffffe, 0x3ffffc, 0x7fdffc, 0x3ffff8,
    0x5ffffd,
    0x3ffffd, 0x6ffffb, 0x3ffffb, 0x5ffff7, 0x1ffffa, 0x3feffa, 0x3fdffe,
    0x1fdffc,
    0x1ffff8, 0x2ffffd, 0x2ffff9, 0x0ffffb, 0x1ffffb, 0x37ffff, 0x3fdff7,
    0x0feffa,
    0x0fdffe, 0x0fdffc, 0x0ffff8, 0x17fffd, 0x17fff9, 0x17fffb, 0x17fff3,
    0x0ffff3,
    0x0ffff7, 0x07effa, 0x07fffe, 0x07fffc, 0x07bff8, 0x0bfffd, 0x0bfff9,
    0x0bfffb,
    0x0bfff3, 0x0bffff, 0x07dff7, 0x03effa, 0x03dffe, 0x03fffc, 0x03bff8,
    0x05fffd,
    0x05fff9, 0x05fffb, 0x05fff3, 0x05ffff, 0x03fff7, 0x01effa, 0x01dffe,
    0x01fffc,
    0x01bff8, 0x02fffd, 0x02fff9, 0x02fffb, 0x02fff3, 0x02ffff, 0x01dff7,
    0x00fffa,
    0x00fffe, 0x00dffc, 0x00bff8, 0x017ffd, 0x017ff9, 0x017ffb, 0x017ff3,
    0x017fff,
    0x00fff7, 0x006ffa, 0x007ffe, 0x007ffc, 0x003ff8, 0x00bffd, 0x00bff9,
    0x00bffb,
    0x00bff3, 0x00bfff, 0x005ff7, 0x003ffa, 0x001ffe, 0x003ffc, 0x005ff8,
    0x005ffd,
    0x005ff9, 0x005ffb, 0x005ff3, 0x005fff, 0x001ff7, 0x001ffa, 0x002ffe,
    0x002ffc,
    0x002ff8, 0x002ffd, 0x002ff9, 0x002ffb, 0x002ff3, 0x002fff, 0x002ff7,
    0x0017fa,
    0x0017fe, 0x0017fc, 0x0017f8, 0x0017fd, 0x0017f9, 0x0017fb, 0x0017f3,
    0x0017ff,
    0x0017f7, 0x000bfa, 0x000bfe, 0x000bfc, 0x000bf8, 0x000bfd, 0x000bf9,
    0x000bfb,
    0x000bf3, 0x000bff, 0x000bf7, 0x0005fa, 0x0005fe, 0x0005fc, 0x0005f8,
    0x0005fd,
    0x0005f9, 0x0005fb, 0x0005f3, 0x0005ff, 0x0005f7, 0x0002fa, 0x0002fe,
    0x0002fc,
    0x0002f8, 0x0002fd, 0x0002f9, 0x0002fb, 0x0002f3, 0x0002ff, 0x0002f7,
    0x00017a,
    0x00017e, 0x00017c, 0x000178, 0x00017d, 0x000179, 0x00017b, 0x000173,
    0x00017f,
    0x000177, 0x0000ba, 0x0000be, 0x0000bc, 0x0000b8, 0x0000bd, 0x0000b9,
    0x0000bb,
    0x0000b3, 0x0000bf, 0x0000b7, 0x00005a, 0x00005e, 0x00005c, 0x000058,
    0x00005d,
    0x000059, 0x00005b, 0x000053, 0x00005f, 0x000057, 0x00002a, 0x00002e,
    0x00002c,
    0x000028, 0x00002d, 0x000029, 0x000031, 0x00002b, 0x000023, 0x00002f,
    0x000027,
    0x000012, 0x000016, 0x000014, 0x000010, 0x000015, 0x000001, 0x000005,
    0x000000,
    0x000004, 0x000006, 0x000002, 0x000007, 0x00000f, 0x000003, 0x00000b,
    0x000011,
    0x000009, 0x00000d, 0x000008, 0x00000c, 0x00000e, 0x00000a, 0x000017,
    0x00001f,
    0x000013, 0x00001b, 0x000019, 0x00001d, 0x000018, 0x00001c, 0x00001e,
    0x00001a,
    0x000037, 0x00003f, 0x000033, 0x00003b, 0x000039, 0x00003d, 0x000038,
    0x00003c,
    0x00003e, 0x00003a, 0x000077, 0x00007f, 0x000073, 0x00007b, 0x000079,
    0x00007d,
    0x000078, 0x00007c, 0x00007e, 0x00007a, 0x0000f7, 0x0000ff, 0x0000f3,
    0x0000fb,
    0x0000f9, 0x0000fd, 0x0000f8, 0x0000fc, 0x0000fe, 0x0000fa, 0x0001f7,
    0x0001ff,
    0x0001f3, 0x0001fb, 0x0001f9, 0x0001fd, 0x0001f8, 0x0001fc, 0x0001fe,
    0x0001fa,
    0x0003f7, 0x0003ff, 0x0003f3, 0x0003fb, 0x0003f9, 0x0003fd, 0x0003f8,
    0x0003fc,
    0x0003fe, 0x0003fa, 0x0007f7, 0x0007ff, 0x0007f3, 0x0007fb, 0x0007f9,
    0x0007fd,
    0x0007f8, 0x0007fc, 0x0007fe, 0x0007fa, 0x000ff7, 0x000fff, 0x000ff3,
    0x000ffb,
    0x000ff9, 0x000ffd, 0x000ff8, 0x000ffc, 0x000ffe, 0x000ffa, 0x003ff7,
    0x001fff,
    0x001ff3, 0x001ffb, 0x001ff9, 0x001ffd, 0x001ff8, 0x001ffc, 0x003ffe,
    0x002ffa,
    0x007ff7, 0x003fff, 0x003ff3, 0x003ffb, 0x003ff9, 0x003ffd, 0x007ff8,
    0x005ffc,
    0x005ffe, 0x007ffa, 0x00dff7, 0x007fff, 0x007ff3, 0x007ffb, 0x007ff9,
    0x007ffd,
    0x00fff8, 0x00fffc, 0x00dffe, 0x00effa, 0x01fff7, 0x00ffff, 0x00fff3,
    0x00fffb,
    0x00fff9, 0x00fffd, 0x01fff8, 0x01dffc, 0x01fffe, 0x01fffa, 0x03dff7,
    0x01ffff,
    0x01fff3, 0x01fffb, 0x01fff9, 0x01fffd, 0x03fff8, 0x03dffc, 0x03fffe,
    0x03fffa,
    0x07fff7, 0x03ffff, 0x03fff3, 0x03fffb, 0x03fff9, 0x03fffd, 0x07fff8,
    0x07dffc,
    0x07dffe, 0x07fffa, 0x0fdff7, 0x07ffff, 0x07fff3, 0x07fffb, 0x07fff9,
    0x07fffd,
    0x0fbff8, 0x0ffffc, 0x0ffffe, 0x0ffffa, 0x1fdff7, 0x17ffff, 0x1ffff3,
    0x1ffff9,
    0x0ffff9, 0x0ffffd, 0x1fbff8, 0x1ffffc, 0x1fdffe, 0x1feffa, 0x3ffff7,
    0x1ffff7,
    0x3ffff3, 0x2ffffb, 0x3ffff9, 0x1ffffd, 0x3fbff8, 0x3fdffc, 0x3ffffe,
    0x1ffffe,
    0x3ffffa, 0x7ffff7, 0x7ffff3, 0x7ffffb, 0x7ffff9, 0x7ffffd, 0x7fbff8,
    0x7ffff8,
    0x7ffffc, 0x7ffffe, 0x0fffff,
], dtype=np.uint32)

# Number of valid bits (LSBs) in each entry in "code7"  -msss
# num7[609]
num7 = np.array([
    20, 24, 24, 24, 24, 24, 24, 24,
    24, 24, 24, 24, 24, 24, 24, 24,
    24, 23, 23, 23, 23, 23, 23, 23,
    23, 23, 23, 23, 23, 23, 23, 23,
    23, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22,
    22, 21, 21, 21, 21, 21, 21, 21,
    21, 21, 21, 21, 21, 21, 21, 21,
    21, 20, 20, 20, 20, 20, 20, 20,
    20, 20, 20, 20, 20, 20, 20, 20,
    20, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19,
    19, 18, 18, 18, 18, 18, 18, 18,
    18, 18, 18, 18, 18, 18, 18, 18,
    18, 17, 17, 17, 17, 17, 17, 17,
    17, 17, 17, 17, 17, 17, 17, 17,
    17, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16,
    16, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14,
    14, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13,
    13, 12, 12, 12, 12, 12, 12, 12,
    12, 12, 12, 12, 12, 12, 12, 12,
    12, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11,
    11, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10,
    10, 9, 9, 9, 9, 9, 9, 9,
    9, 9, 9, 9, 9, 9, 9, 9,
    9, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8,
    8, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7,
    6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6,
    6, 6, 6, 6, 6, 6, 6, 6,
    6, 7, 7, 7, 7, 7, 7, 7,
    7, 7, 7, 7, 7, 7, 7, 7,
    8, 8, 8, 8, 8, 8, 8, 8,
    8, 8, 8, 8, 8, 8, 8, 8,
    9, 9, 9, 9, 9, 9, 9, 9,
    9, 9, 9, 9, 9, 9, 9, 9,
    10, 10, 10, 10, 10, 10, 10, 10,
    10, 10, 10, 10, 10, 10, 10, 10,
    11, 11, 11, 11, 11, 11, 11, 11,
    11, 11, 11, 11, 11, 11, 11, 11,
    12, 12, 12, 12, 12, 12, 12, 12,
    12, 12, 12, 12, 12, 12, 12, 12,
    13, 13, 13, 13, 13, 13, 13, 13,
    13, 13, 13, 13, 13, 13, 13, 13,
    14, 14, 14, 14, 14, 14, 14, 14,
    14, 14, 14, 14, 14, 14, 14, 14,
    15, 15, 15, 15, 15, 15, 15, 15,
    15, 15, 15, 15, 15, 15, 15, 15,
    16, 16, 16, 16, 16, 16, 16, 16,
    16, 16, 16, 16, 16, 16, 16, 16,
    17, 17, 17, 17, 17, 17, 17, 17,
    17, 17, 17, 17, 17, 17, 17, 17,
    18, 18, 18, 18, 18, 18, 18, 18,
    18, 18, 18, 18, 18, 18, 18, 18,
    19, 19, 19, 19, 19, 19, 19, 19,
    19, 19, 19, 19, 19, 19, 19, 19,
    20, 20, 20, 20, 20, 20, 20, 20,
    20, 20, 20, 20, 20, 20, 20, 20,
    21, 21, 21, 21, 21, 21, 21, 21,
    21, 21, 21, 21, 21, 21, 21, 21,
    22, 22, 22, 22, 22, 22, 22, 22,
    22, 22, 22, 22, 22, 22, 22, 22,
    23, 23, 23, 23, 23, 23, 23, 23,
    23, 23, 23, 23, 23, 23, 23, 23,
    24, 24, 24, 24, 24, 24, 24, 24,
    24, 24, 24, 24, 24, 24, 24, 24,
    20,
], dtype=np.uint8)

#  Huffman code for encoding scheme 7, zero's code is index 304  -msss
# code7[609]
code7 = np.array([
    0x0fffff, 0xfffffd, 0xeffffd, 0xfffff5, 0xfffff9, 0xfffff1, 0xfffffb,
    0xfffff3,
    0xfffff7, 0xfdffff, 0xedffff, 0xfffffe, 0xfffffa, 0xfffffc, 0xf7fffc,
    0xfffff8,
    0xfffff0, 0x2ffffd, 0x77fff5, 0x3ffff9, 0x5ffff9, 0x3ffffb, 0x7bfffb,
    0x3ffff7,
    0x5ffff7, 0x2dffff, 0x7bfffe, 0x3ffffe, 0x5ffffa, 0x3ffffc, 0x7ffff4,
    0x3ffff0,
    0x5ffff0, 0x0ffffd, 0x1ffff5, 0x37fff9, 0x3bfff1, 0x1ffffb, 0x1bfffb,
    0x2ffff3,
    0x2ffff7, 0x1dffff, 0x1bfffe, 0x3bfffa, 0x3ffff2, 0x1ffffc, 0x1ffff8,
    0x2ffff8,
    0x2ffff0, 0x17fffd, 0x0ffff5, 0x0ffff9, 0x0bfff1, 0x0bfffb, 0x1bfff3,
    0x1bfff7,
    0x1bffff, 0x1ffff6, 0x0ffffe, 0x0ffffa, 0x0ffff2, 0x0ffff4, 0x17fff4,
    0x17fff8,
    0x17fff0, 0x0bfffd, 0x0bfff5, 0x0bfff9, 0x07fff1, 0x07fffb, 0x07fff3,
    0x03fff7,
    0x03ffff, 0x03fffe, 0x07fffe, 0x07fffa, 0x0bfff2, 0x0bfffc, 0x0bfff4,
    0x0bfff8,
    0x0bfff0, 0x05fffd, 0x05fff5, 0x05fff9, 0x05fff1, 0x05fffb, 0x05fff3,
    0x05fff7,
    0x01ffff, 0x05fff6, 0x05fffe, 0x05fffa, 0x05fff2, 0x05fffc, 0x05fff4,
    0x05fff8,
    0x05fff0, 0x02fffd, 0x02fff5, 0x02fff9, 0x02fff1, 0x02fffb, 0x02fff3,
    0x02fff7,
    0x02ffff, 0x02fff6, 0x02fffe, 0x02fffa, 0x02fff2, 0x02fffc, 0x02fff4,
    0x02fff8,
    0x02fff0, 0x017ffd, 0x017ff5, 0x017ff9, 0x017ff1, 0x017ffb, 0x017ff3,
    0x017ff7,
    0x017fff, 0x017ff6, 0x017ffe, 0x017ffa, 0x017ff2, 0x017ffc, 0x017ff4,
    0x017ff8,
    0x017ff0, 0x00bffd, 0x00bff5, 0x00bff9, 0x00bff1, 0x00bffb, 0x00bff3,
    0x00bff7,
    0x00bfff, 0x00bff6, 0x00bffe, 0x00bffa, 0x00bff2, 0x00bffc, 0x00bff4,
    0x00bff8,
    0x00bff0, 0x005ffd, 0x005ff5, 0x005ff9, 0x005ff1, 0x005ffb, 0x005ff3,
    0x005ff7,
    0x005fff, 0x005ff6, 0x005ffe, 0x005ffa, 0x005ff2, 0x005ffc, 0x005ff4,
    0x005ff8,
    0x005ff0, 0x002ffd, 0x002ff5, 0x002ff9, 0x002ff1, 0x002ffb, 0x002ff3,
    0x002ff7,
    0x002fff, 0x002ff6, 0x002ffe, 0x002ffa, 0x002ff2, 0x002ffc, 0x002ff4,
    0x002ff8,
    0x002ff0, 0x0017fd, 0x0017f5, 0x0017f9, 0x0017f1, 0x0017fb, 0x0017f3,
    0x0017f7,
    0x0017ff, 0x0017f6, 0x0017fe, 0x0017fa, 0x0017f2, 0x0017fc, 0x0017f4,
    0x0017f8,
    0x0017f0, 0x000bfd, 0x000bf5, 0x000bf9, 0x000bf1, 0x000bfb, 0x000bf3,
    0x000bf7,
    0x000bff, 0x000bf6, 0x000bfe, 0x000bfa, 0x000bf2, 0x000bfc, 0x000bf4,
    0x000bf8,
    0x000bf0, 0x0005fd, 0x0005f5, 0x0005f9, 0x0005f1, 0x0005fb, 0x0005f3,
    0x0005f7,
    0x0005ff, 0x0005f6, 0x0005fe, 0x0005fa, 0x0005f2, 0x0005fc, 0x0005f4,
    0x0005f8,
    0x0005f0, 0x0002fd, 0x0002f5, 0x0002f9, 0x0002f1, 0x0002fb, 0x0002f3,
    0x0002f7,
    0x0002ff, 0x0002f6, 0x0002fe, 0x0002fa, 0x0002f2, 0x0002fc, 0x0002f4,
    0x0002f8,
    0x0002f0, 0x00017d, 0x000175, 0x000179, 0x000171, 0x00017b, 0x000173,
    0x000177,
    0x00017f, 0x000176, 0x00017e, 0x00017a, 0x000172, 0x00017c, 0x000174,
    0x000178,
    0x000170, 0x0000bd, 0x0000b5, 0x0000b9, 0x0000b1, 0x0000bb, 0x0000b3,
    0x0000b7,
    0x0000bf, 0x0000b6, 0x0000be, 0x0000ba, 0x0000b2, 0x0000bc, 0x0000b4,
    0x0000b8,
    0x0000b0, 0x00005d, 0x000055, 0x000059, 0x000051, 0x00005b, 0x000053,
    0x000057,
    0x00005f, 0x000056, 0x00005e, 0x00005a, 0x000052, 0x00005c, 0x000054,
    0x000058,
    0x00002d, 0x000025, 0x000029, 0x000021, 0x00002b, 0x000023, 0x000027,
    0x00002f,
    0x000026, 0x00002e, 0x00002a, 0x000022, 0x00002c, 0x000024, 0x000028,
    0x000020,
    0x000010, 0x000000, 0x000008, 0x000004, 0x00000c, 0x000002, 0x00000a,
    0x00000e,
    0x000006, 0x00000f, 0x000007, 0x000003, 0x00000b, 0x000001, 0x000009,
    0x000005,
    0x00000d, 0x000018, 0x000014, 0x00001c, 0x000012, 0x00001a, 0x00001e,
    0x000016,
    0x00001f, 0x000017, 0x000013, 0x00001b, 0x000011, 0x000019, 0x000015,
    0x00001d,
    0x000030, 0x000038, 0x000034, 0x00003c, 0x000032, 0x00003a, 0x00003e,
    0x000036,
    0x00003f, 0x000037, 0x000033, 0x00003b, 0x000031, 0x000039, 0x000035,
    0x00003d,
    0x000070, 0x000078, 0x000074, 0x00007c, 0x000072, 0x00007a, 0x00007e,
    0x000076,
    0x00007f, 0x000077, 0x000073, 0x00007b, 0x000071, 0x000079, 0x000075,
    0x00007d,
    0x0000f0, 0x0000f8, 0x0000f4, 0x0000fc, 0x0000f2, 0x0000fa, 0x0000fe,
    0x0000f6,
    0x0000ff, 0x0000f7, 0x0000f3, 0x0000fb, 0x0000f1, 0x0000f9, 0x0000f5,
    0x0000fd,
    0x0001f0, 0x0001f8, 0x0001f4, 0x0001fc, 0x0001f2, 0x0001fa, 0x0001fe,
    0x0001f6,
    0x0001ff, 0x0001f7, 0x0001f3, 0x0001fb, 0x0001f1, 0x0001f9, 0x0001f5,
    0x0001fd,
    0x0003f0, 0x0003f8, 0x0003f4, 0x0003fc, 0x0003f2, 0x0003fa, 0x0003fe,
    0x0003f6,
    0x0003ff, 0x0003f7, 0x0003f3, 0x0003fb, 0x0003f1, 0x0003f9, 0x0003f5,
    0x0003fd,
    0x0007f0, 0x0007f8, 0x0007f4, 0x0007fc, 0x0007f2, 0x0007fa, 0x0007fe,
    0x0007f6,
    0x0007ff, 0x0007f7, 0x0007f3, 0x0007fb, 0x0007f1, 0x0007f9, 0x0007f5,
    0x0007fd,
    0x000ff0, 0x000ff8, 0x000ff4, 0x000ffc, 0x000ff2, 0x000ffa, 0x000ffe,
    0x000ff6,
    0x000fff, 0x000ff7, 0x000ff3, 0x000ffb, 0x000ff1, 0x000ff9, 0x000ff5,
    0x000ffd,
    0x001ff0, 0x001ff8, 0x001ff4, 0x001ffc, 0x001ff2, 0x001ffa, 0x001ffe,
    0x001ff6,
    0x001fff, 0x001ff7, 0x001ff3, 0x001ffb, 0x001ff1, 0x001ff9, 0x001ff5,
    0x001ffd,
    0x003ff0, 0x003ff8, 0x003ff4, 0x003ffc, 0x003ff2, 0x003ffa, 0x003ffe,
    0x003ff6,
    0x003fff, 0x003ff7, 0x003ff3, 0x003ffb, 0x003ff1, 0x003ff9, 0x003ff5,
    0x003ffd,
    0x007ff0, 0x007ff8, 0x007ff4, 0x007ffc, 0x007ff2, 0x007ffa, 0x007ffe,
    0x007ff6,
    0x007fff, 0x007ff7, 0x007ff3, 0x007ffb, 0x007ff1, 0x007ff9, 0x007ff5,
    0x007ffd,
    0x00fff0, 0x00fff8, 0x00fff4, 0x00fffc, 0x00fff2, 0x00fffa, 0x00fffe,
    0x00fff6,
    0x00ffff, 0x00fff7, 0x00fff3, 0x00fffb, 0x00fff1, 0x00fff9, 0x00fff5,
    0x00fffd,
    0x01fff0, 0x01fff8, 0x01fff4, 0x01fffc, 0x01fff2, 0x01fffa, 0x01fffe,
    0x01fff6,
    0x03fff6, 0x01fff7, 0x01fff3, 0x01fffb, 0x01fff1, 0x01fff9, 0x01fff5,
    0x01fffd,
    0x03fff0, 0x03fff8, 0x03fff4, 0x03fffc, 0x03fff2, 0x07fff2, 0x03fffa,
    0x07fff6,
    0x05ffff, 0x07fff7, 0x03fff3, 0x03fffb, 0x03fff1, 0x03fff9, 0x03fff5,
    0x03fffd,
    0x07fff0, 0x07fff8, 0x07fff4, 0x07fffc, 0x0ffffc, 0x0bfffa, 0x0bfffe,
    0x0ffff6,
    0x0bffff, 0x0bfff7, 0x0bfff3, 0x0ffffb, 0x0ffff1, 0x07fff9, 0x07fff5,
    0x07fffd,
    0x0ffff0, 0x0ffff8, 0x1ffff4, 0x17fffc, 0x1ffff2, 0x1bfffa, 0x1ffffe,
    0x0dffff,
    0x0ffff7, 0x0ffff3, 0x1ffff3, 0x1ffff1, 0x1bfff1, 0x17fff9, 0x17fff5,
    0x1ffffd,
    0x1ffff0, 0x3ffff8, 0x3ffff4, 0x37fffc, 0x1ffffa, 0x3ffffa, 0x3bfffe,
    0x3dffff,
    0x1ffff7, 0x3ffff3, 0x3bfffb, 0x3ffff1, 0x1ffff9, 0x3ffff5, 0x37fff5,
    0x3ffffd,
    0x7ffff0, 0x7ffff8, 0x77fffc, 0x7ffffc, 0x7ffffa, 0x7ffffe, 0x6dffff,
    0x7dffff,
    0x7ffff7, 0x7ffff3, 0x7ffffb, 0x7ffff1, 0x7ffff9, 0x7ffff5, 0x6ffffd,
    0x7ffffd,
    0x07ffff,
], dtype=np.uint32)

# size of each huffman encoding scheme -msss
# was called sizes
sizes = np.array([
    25, 47, 69, 109, 169, 247, 395, 609,
], dtype=np.uint16)
# Array of bit count array pointers for each encoding scheme -msss
counts = np.array([num0, num1, num2, num3, num4, num5, num6, num7],
                  dtype=object)

# Array of Huffman code array pointers for each encoding scheme  -msss
encodings = np.array([code0, code1, code2, code3, code4, code5, code6, code7],
                     dtype=object)
