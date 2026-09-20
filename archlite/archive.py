"""兼容层：历史上全部实现都在 archlite.archive，现拆到
entry / format / writer / reader 四个模块，这里仅重新导出，
保证 ``from archlite.archive import ...`` 的旧调用方不受影响。
"""

from archlite.entry import ArchiveEntry, check_entry
from archlite.format import MAGIC
from archlite.reader import find_entry, read_archive, unpack_bytes
from archlite.writer import pack_bytes, write_archive

__all__ = [
    "MAGIC",
    "ArchiveEntry",
    "check_entry",
    "pack_bytes",
    "unpack_bytes",
    "write_archive",
    "read_archive",
    "find_entry",
]
