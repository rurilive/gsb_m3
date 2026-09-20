"""写层：把条目序列确定性地编码成 archlite 块流。

pack_bytes（内存）与 write_archive（文件）共用 iter_blocks，
头部拼装只走 format.build_header 一处。
"""

from archlite import format
from archlite.entry import check_entry


def iter_blocks(entries):
    """逐条产出 头部块 + 补零后的数据块，最后产出两个全零结束块。"""
    for entry in entries:
        name_bytes = check_entry(entry)
        yield format.build_header(name_bytes, len(entry.data))
        yield entry.data
        yield b"\x00" * ((-len(entry.data)) % format.BLOCK_SIZE)
    yield b"\x00" * (format.END_BLOCKS * format.BLOCK_SIZE)


def pack_bytes(entries):
    """把条目打成完整归档字节（字节级确定，无易变字段）。"""
    return b"".join(iter_blocks(entries))


def write_archive(path, entries):
    """把归档流式写入 path 指向的文件。"""
    with open(path, "wb") as f:
        for chunk in iter_blocks(entries):
            f.write(chunk)
