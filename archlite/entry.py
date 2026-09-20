"""ArchiveEntry 及写侧条目校验（错误文案历史锁定，逐字不变）。"""

from archlite import format


class ArchiveEntry(object):
    """归档里的一个条目。"""

    def __init__(self, name, data):
        if not isinstance(name, str):
            raise TypeError("entry name must be str")
        if not isinstance(data, bytes):
            raise TypeError("entry data must be bytes")
        self.name = name
        self.data = data

    def __eq__(self, other):
        if not isinstance(other, ArchiveEntry):
            return NotImplemented
        return self.name == other.name and self.data == other.data

    def __repr__(self):
        return "ArchiveEntry(name=%r, data=%d bytes)" % (self.name, len(self.data))


def check_entry(entry):
    """校验一个条目，返回 utf-8 编码后的名字字节。"""
    if not isinstance(entry, ArchiveEntry):
        raise TypeError("expected ArchiveEntry, got %s" % type(entry).__name__)
    if entry.name == "":
        raise ValueError("entry name must not be empty")
    if "\x00" in entry.name:
        raise ValueError("entry name must not contain NUL")
    name_bytes = entry.name.encode("utf-8")
    if len(name_bytes) > format.NAME_MAX:
        raise ValueError(
            "entry name too long: %d > %d bytes"
            % (len(name_bytes), format.NAME_MAX)
        )
    return name_bytes
