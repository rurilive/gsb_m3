"""读层：tar-lite 字节块 -> 条目。

头部解析与校验集中在本模块；字节串与文件两个驱动只负责取块/取数据。
"""

import struct

from archlite.entry import ArchiveEntry
from archlite.format import (
    BLOCK_SIZE,
    CHECKSUM_LEN,
    CHECKSUM_OFF,
    MAGIC,
    MAGIC_LEN,
    NAME_LEN,
    NAME_OFF,
    SIZE_LEN,
    SIZE_OFF,
    ZERO_BLOCK,
    header_checksum,
)


# --- 错误归类：所有归档损坏错误都在这里构造，文案逐字锁定（见测试） ---------

def _err_truncated_header(got):
    return ValueError("truncated header: got %d bytes" % got)


def _err_bad_magic(blk):
    return ValueError("not an archlite archive: magic=%r" % bytes(blk[:MAGIC_LEN]))


def _err_checksum(idx):
    return ValueError("header checksum mismatch at entry %d" % idx)


def _err_truncated_data(name, size, got):
    return ValueError(
        "truncated data for %r: expected %d bytes, got %d" % (name, size, got)
    )


# --- 头部解析：一个 512 字节块 -> (name, size) ------------------------------

def _parse_header(blk, idx):
    """校验魔数/校验和并解析名字与长度；坏块抛 ValueError，坏 utf-8 原样上抛。"""
    if blk[:MAGIC_LEN] != MAGIC:
        raise _err_bad_magic(blk)
    stored = struct.unpack(
        ">I", blk[CHECKSUM_OFF:CHECKSUM_OFF + CHECKSUM_LEN]
    )[0]
    if header_checksum(blk) != stored:
        raise _err_checksum(idx)
    name = blk[NAME_OFF:NAME_OFF + NAME_LEN].split(b"\x00", 1)[0].decode("utf-8")
    size = struct.unpack(">Q", blk[SIZE_OFF:SIZE_OFF + SIZE_LEN])[0]
    return name, size


# --- 两个驱动：字节串 / 文件 -------------------------------------------------

def unpack_bytes(blob):
    """解析归档字节串。不足一块的尾部字节与结束块之后的字节一律忽略。"""
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("expected bytes")
    blob = bytes(blob)
    if len(blob) < BLOCK_SIZE:
        raise _err_truncated_header(len(blob))
    entries = []
    off = 0
    idx = 0
    while True:
        blk = blob[off:off + BLOCK_SIZE]
        if len(blk) < BLOCK_SIZE:
            break
        if blk == ZERO_BLOCK:
            break
        name, size = _parse_header(blk, idx)
        body = blob[off + BLOCK_SIZE:off + BLOCK_SIZE + size]
        if len(body) < size:
            raise _err_truncated_data(name, size, len(body))
        entries.append(ArchiveEntry(name, body))
        off = off + BLOCK_SIZE + ((size + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
        idx += 1
        if off >= len(blob):
            break
    return entries


def read_archive(path):
    """流式读取 path（rb）。不足一块的尾部字节一律忽略。"""
    entries = []
    with open(path, "rb") as f:
        idx = 0
        while True:
            blk = f.read(BLOCK_SIZE)
            if len(blk) < BLOCK_SIZE:
                break
            if blk == ZERO_BLOCK:
                break
            name, size = _parse_header(blk, idx)
            body = f.read(size)
            if len(body) < size:
                raise _err_truncated_data(name, size, len(body))
            entries.append(ArchiveEntry(name, body))
            pad = (-size) % BLOCK_SIZE
            if pad:
                f.read(pad)
            idx += 1
    return entries


def find_entry(blob, name):
    """按名字找第一个条目；找不到或归档损坏一律返回 None（恢复工具依赖）。"""
    try:
        entries = unpack_bytes(blob)
    except ValueError:
        return None
    for entry in entries:
        if entry.name == name:
            return entry
    return None
