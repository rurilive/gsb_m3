"""archlite 块格式的唯一事实来源：布局常量、校验和与头部编解码。

读写两层都从这里取偏移/长度，新增头部字段（如版本号）只需改这一处。
头部布局（512 字节）：
0-4   魔数 MAGIC ("ARCL")
4-68  名字（utf-8，NUL 补齐，最长 NAME_MAX 字节）
68-76 数据长度（大端 u64）
76-80 校验和（大端 u32，校验和字段置零后的整个头部按字节求和）
80-   全零填充
"""

import struct

BLOCK_SIZE = 512
MAGIC = b"ARCL"

MAGIC_OFFSET = 0
MAGIC_SIZE = 4
NAME_OFFSET = 4
NAME_SIZE = 64
NAME_MAX = 64
SIZE_OFFSET = 68
SIZE_SIZE = 8
CHECKSUM_OFFSET = 76
CHECKSUM_SIZE = 4
HEADER_SIZE = BLOCK_SIZE
END_BLOCKS = 2

_CHECKSUM_MASK = 0xFFFFFFFF


def header_checksum(head):
    """对校验和字段（76:80）视为 0 的整个头部按字节求和。"""
    return (
        sum(head[:CHECKSUM_OFFSET])
        + sum(head[CHECKSUM_OFFSET + CHECKSUM_SIZE:])
    ) & _CHECKSUM_MASK


def build_header(name_bytes, data_size):
    """拼装一个 512 字节头（调用方需已完成条目校验）。"""
    head = bytearray(HEADER_SIZE)
    head[MAGIC_OFFSET:MAGIC_OFFSET + MAGIC_SIZE] = MAGIC
    head[NAME_OFFSET:NAME_OFFSET + len(name_bytes)] = name_bytes
    head[SIZE_OFFSET:SIZE_OFFSET + SIZE_SIZE] = struct.pack(">Q", data_size)
    head[CHECKSUM_OFFSET:CHECKSUM_OFFSET + CHECKSUM_SIZE] = struct.pack(
        ">I", header_checksum(head)
    )
    return bytes(head)


def parse_header(blk, index):
    """校验并解析一个 512 字节头，返回 (name, data_size)。

    校验顺序与错误文案为历史锁定口径，逐字不变：
    魔数 -> 校验和 -> 名字解码（UnicodeDecodeError 原样向上抛）-> 长度。
    """
    magic = bytes(blk[MAGIC_OFFSET:MAGIC_OFFSET + MAGIC_SIZE])
    if magic != MAGIC:
        raise ValueError("not an archlite archive: magic=%r" % magic)
    stored = struct.unpack(
        ">I", blk[CHECKSUM_OFFSET:CHECKSUM_OFFSET + CHECKSUM_SIZE]
    )[0]
    if header_checksum(blk) != stored:
        raise ValueError("header checksum mismatch at entry %d" % index)
    raw = bytes(blk[NAME_OFFSET:NAME_OFFSET + NAME_SIZE]).split(b"\x00", 1)[0]
    name = raw.decode("utf-8")
    data_size = struct.unpack(
        ">Q", blk[SIZE_OFFSET:SIZE_OFFSET + SIZE_SIZE]
    )[0]
    return name, data_size
