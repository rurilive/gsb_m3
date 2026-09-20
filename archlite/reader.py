"""读层：从块流解析归档。

核心 _read_entries 只面向二进制流（文件对象或 BytesIO），
unpack_bytes / read_archive 是两种来源的薄封装，解析与校验不再各写一份。

错误路径分类（对外类型与文案历史锁定，逐字不变）：
- 归档损坏（魔数/校验和/数据截断）-> ValueError，由 format.parse_header
  与本模块抛出；find_entry 统一吞掉 ValueError 并返回 None
- 名字非 utf-8 -> UnicodeDecodeError（ValueError 子类，find_entry 同样吞掉）
- 入参类型错误 -> TypeError，仅 unpack_bytes 在入口检查
- 文件不存在等 IO 错误 -> 原样向上传播
- 中部/尾部不足一块的字节与结束块之后的字节一律忽略（不报错）
"""

import io

from archlite import format
from archlite.entry import ArchiveEntry

_ZERO_BLOCK = b"\x00" * format.BLOCK_SIZE


def _read_entries(stream):
    """按块顺序解析一个已打开的二进制流，返回 ArchiveEntry 列表。"""
    entries = []
    index = 0
    read_block = stream.read
    while True:
        blk = read_block(format.BLOCK_SIZE)
        if len(blk) < format.BLOCK_SIZE:
            break
        if blk == _ZERO_BLOCK:
            break
        name, size = format.parse_header(blk, index)
        body = read_block(size)
        if len(body) < size:
            raise ValueError(
                "truncated data for %r: expected %d bytes, got %d"
                % (name, size, len(body))
            )
        padding = (-size) % format.BLOCK_SIZE
        if padding:
            read_block(padding)
        entries.append(ArchiveEntry(name, body))
        index += 1
    return entries


def unpack_bytes(blob):
    """解析内存中的归档字节；首块不足 512 按截断头部报错。"""
    if not isinstance(blob, (bytes, bytearray)):
        raise TypeError("expected bytes")
    if len(blob) < format.HEADER_SIZE:
        raise ValueError("truncated header: got %d bytes" % len(blob))
    with io.BytesIO(bytes(blob)) as stream:
        return _read_entries(stream)


def read_archive(path):
    """从文件流式读取归档；IO 错误（如文件不存在）原样向上传播。"""
    with open(path, "rb") as stream:
        return _read_entries(stream)


def find_entry(blob, name):
    """按名查找第一个同名条目；找不到或归档损坏一律返回 None（恢复工具依赖）。"""
    try:
        entries = unpack_bytes(blob)
    except ValueError:
        return None
    for entry in entries:
        if entry.name == name:
            return entry
    return None
