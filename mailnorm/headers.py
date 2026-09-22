"""头部块的解析：一行一个字段，名字不区分大小写。

现有口径：字段行按第一个冒号切，值取冒号右边去首尾空白。折叠（以空白
开头的续行）还没做，碰到续行按没有冒号的行报错。
"""

from .errors import MailParseError

_WS = " \t"


def split_header_lines(block):
    """把头部块拆成 (name, value) 列表，顺序保留。

    值取冒号右边去首尾空白；空行跳过；没有冒号的非空行报错。
    """
    pairs = []
    offset = 0
    for chunk in block.splitlines(True):
        line = chunk.rstrip("\r\n")
        if line.strip() == "":
            offset += len(chunk)
            continue
        if ":" not in line:
            raise MailParseError(
                "header line has no colon", offset=offset, text=block
            )
        name, _, value = line.partition(":")
        if name == "" or name != name.strip() or any(c in _WS for c in name):
            raise MailParseError(
                "bad header field name %r" % name, offset=offset, text=block
            )
        pairs.append((name, value.strip()))
        offset += len(chunk)
    return pairs


class Headers:
    """保序的头部表，按名字取值时不区分大小写。"""

    def __init__(self, pairs=()):
        self._pairs = list(pairs)
        self._index = {}
        for name, value in self._pairs:
            self._index.setdefault(name.lower(), []).append(value)

    def get(self, name, default=None):
        """第一个同名字段的值，没有给 default。"""
        values = self._index.get(name.lower())
        return values[0] if values else default

    def get_all(self, name):
        """同名字段的全部值，按出现顺序。"""
        return list(self._index.get(name.lower(), ()))

    def __contains__(self, name):
        return name.lower() in self._index

    def __getitem__(self, name):
        value = self.get(name)
        if value is None:
            raise KeyError(name)
        return value

    def __iter__(self):
        return iter(self._pairs)

    def __len__(self):
        return len(self._pairs)

    def items(self):
        """全部 (name, value)，含重复字段，按原始顺序。"""
        return list(self._pairs)

    def names(self):
        """名字按首次出现排，不重复，保留原始大小写。"""
        seen = set()
        out = []
        for name, _ in self._pairs:
            key = name.lower()
            if key not in seen:
                seen.add(key)
                out.append(name)
        return out

    def __repr__(self):
        return "Headers(%r)" % (self._pairs,)


def parse_headers(block):
    """头部块到 Headers，空块给空表。"""
    return Headers(split_header_lines(block))


def split_addresses(value):
    """按逗号把地址列表切开，只做简单去空白。

    显示名里带引号逗号、或者地址后面挂括号注释的情况还没认，会切坏。
    """
    out = []
    for piece in value.split(","):
        piece = piece.strip()
        if piece:
            out.append(piece)
    return out
