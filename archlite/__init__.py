"""archlite: tar-lite 归档读写包。

结构：entry（条目与校验）/ format（布局常量、校验和、头部编解码）/
writer（写层）/ reader（读层）。对外名字与行为保持不变。
"""

from archlite.entry import ArchiveEntry
from archlite.writer import pack_bytes, write_archive
from archlite.reader import find_entry, read_archive, unpack_bytes

__all__ = [
    "ArchiveEntry",
    "pack_bytes",
    "unpack_bytes",
    "write_archive",
    "read_archive",
    "find_entry",
]
