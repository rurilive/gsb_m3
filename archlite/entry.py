"""ArchiveEntry 及其入包前校验（读写两层共用的条目模型）。"""

from archlite.format import NAME_LEN


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
    """校验待打包条目，返回名字的 utf-8 字节；非法即抛 TypeError/ValueError。"""
    if not isinstance(entry, ArchiveEntry):
        raise TypeError("expected ArchiveEntry, got %s" % type(entry).__name__)
    if entry.name == "":
        raise ValueError("entry name must not be empty")
    if "\x00" in entry.name:
        raise ValueError("entry name must not contain NUL")
    name_bytes = entry.name.encode("utf-8")
    if len(name_bytes) > NAME_LEN:
        raise ValueError(
            "entry name too long: %d > %d bytes" % (len(name_bytes), NAME_LEN)
        )
    return name_bytes
