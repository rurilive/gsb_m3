"""写层：条目 -> tar-lite 字节块。内存打包与流式写文件共用同一份拼装。"""

import struct

from archlite.entry import check_entry
from archlite.format import (
    BLOCK_SIZE,
    CHECKSUM_LEN,
    CHECKSUM_OFF,
    END_BLOCKS,
    MAGIC,
    MAGIC_OFF,
    NAME_OFF,
    SIZE_LEN,
    SIZE_OFF,
    header_checksum,
)


def _build_header(name_bytes, data_len):
    """拼一个 512 字节头：魔数 + 名字 + 长度 + 校验和，余块补零。"""
    head = bytearray(BLOCK_SIZE)
    head[MAGIC_OFF:MAGIC_OFF + len(MAGIC)] = MAGIC
    head[NAME_OFF:NAME_OFF + len(name_bytes)] = name_bytes
    head[SIZE_OFF:SIZE_OFF + SIZE_LEN] = struct.pack(">Q", data_len)
    head[CHECKSUM_OFF:CHECKSUM_OFF + CHECKSUM_LEN] = struct.pack(
        ">I", header_checksum(head)
    )
    return head


def _iter_blocks(entries):
    """逐条产出 头块 + 数据 + 补零，最后产出两个结束块。"""
    for entry in entries:
        name_bytes = check_entry(entry)
        yield bytes(_build_header(name_bytes, len(entry.data)))
        yield entry.data
        yield b"\x00" * ((-len(entry.data)) % BLOCK_SIZE)
    yield END_BLOCKS


def pack_bytes(entries):
    """把条目序列打成确定的归档字节串。"""
    out = bytearray()
    for block in _iter_blocks(entries):
        out += block
    return bytes(out)


def write_archive(path, entries):
    """把条目序列流式写入 path（wb），字节布局与 pack_bytes 完全一致。"""
    with open(path, "wb") as f:
        for block in _iter_blocks(entries):
            f.write(block)
