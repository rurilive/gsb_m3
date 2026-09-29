"""最朴素的全量同步：一次把整张键值表原样发给对端，对端整体覆盖。

只有键值表本身，没有摘要、没有差集、没有版本，也没有冲突合并。同步就是
把本地全部条目打包送出，接收方用它整体替换自己的表。
"""


class FullSync:
    """全量同步器：同步时把本地整张表原样发出，对端整体覆盖。"""

    def __init__(self, items=None):
        if items is None:
            items = {}
        self._items = dict(items)
        self.sent_entries = 0

    def set(self, key, value):
        """写入或覆盖一个键值。"""
        self._items[key] = value

    def get(self, key, default=None):
        """读一个键的值，缺失时返回默认值。"""
        return self._items.get(key, default)

    def __contains__(self, key):
        return key in self._items

    def __len__(self):
        return len(self._items)

    def keys(self):
        """按键排序后列出全部键。"""
        return sorted(self._items)

    def items(self):
        """整张表的独立副本。"""
        return dict(self._items)

    def snapshot(self):
        """整张表的独立副本，用于整表发送。"""
        return dict(self._items)

    def sync_to(self, peer):
        """把整张表原样发给对端，返回本次发出的条目数。"""
        payload = self.snapshot()
        self.sent_entries += len(payload)
        peer.receive(payload)
        return len(payload)

    def receive(self, payload):
        """收到整表就用它整体覆盖本地，不做任何合并或摘要比较。"""
        self._items = dict(payload)

    def __repr__(self):
        return "FullSync(%d)" % len(self._items)
