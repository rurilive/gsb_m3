"""walog 的现状实现：一个朴素的内存追加列表。

Log 只按追加次序把条目放进一个列表，append 在末尾落一条负载，read 按位置
读回负载，配一个长度与清空。没有序号，没有检查点，没有截断，也没有校验和
与重放，这些留待在这个基础上补齐。
"""

from .errors import InvalidLsn


class Log:
    """一个把条目按追加次序存下来的内存列表。

    条目只是不透明的负载，本类不感知序号、检查点、截断与校验，也不做重放。
    """

    def __init__(self):
        self._items = []

    def append(self, payload):
        """在末尾追加一条负载，返回它在列表里的位置（从 0 开始）。"""
        self._items.append(payload)
        return len(self._items) - 1

    def read(self, pos):
        """按位置读回一条负载，位置越界即报错。"""
        if isinstance(pos, bool) or not isinstance(pos, int):
            raise InvalidLsn("位置必须是整数，收到 %r" % (pos,))
        if pos < 0 or pos >= len(self._items):
            raise InvalidLsn("位置越界，收到 %r，当前长度 %d" % (pos, len(self._items)))
        return self._items[pos]

    def __len__(self):
        """当前条目数。"""
        return len(self._items)

    def reset(self):
        """清空全部条目。"""
        self._items = []
