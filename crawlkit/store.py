"""抓取队列的去重门面：标记已入队的 URL、判重、必要时撤销。"""

import struct

from .bloom import BloomFilter
from .cuckoo import CuckooFilter
from .errors import NotSupportedError

MAGIC = b"DDS1"
MAGIC_CUCKOO = b"DDS2"
# magic, marks, queries, duplicates, fp_rate
_HEADER = struct.Struct(">4sQQQd")

BACKENDS = ("bloom", "cuckoo")


class DedupStore:
    """门面层，构造参数透传给底层过滤器。

    mark 记下一条 URL，is_duplicate 回答它之前是否标记过，
    retry 把一条 URL 从集合里撤下来。底层是近似结构，判重会多报不会漏报。

    backend="bloom"（默认）维持老行为：只加不删，落盘字节与存量快照
    兼容；backend="cuckoo" 底层换布谷鸟过滤器，retry 走真删，重试的
    URL 不再被判重复。此时 fp_bits 定指纹位数（默认 12），fp_rate 仅
    作为门面配置随头落盘。
    """

    def __init__(self, capacity, fp_rate=0.01, backend="bloom", fp_bits=12):
        self.capacity = int(capacity)
        self.fp_rate = float(fp_rate)
        self.backend = backend
        if backend == "bloom":
            self._filter = BloomFilter(self.capacity, self.fp_rate)
        elif backend == "cuckoo":
            self.fp_bits = int(fp_bits)
            self._filter = CuckooFilter(self.capacity, self.fp_bits)
        else:
            raise ValueError("unknown backend: %r" % (backend,))
        self._marks = 0
        self._queries = 0
        self._duplicates = 0

    def mark(self, key):
        """记下一条已入队的 URL。"""
        self._filter.add(key)
        self._marks += 1

    def is_duplicate(self, key):
        """这条 URL 之前标记过吗。"""
        self._queries += 1
        if key in self._filter:
            self._duplicates += 1
            return True
        return False

    def retry(self, key):
        """把一条 URL 从去重集合里撤下来，让重试的抓取不再被判成重复。

        布隆后端删不了位，这里没得商量；布谷后端真删，返回是否撤到。
        """
        if self.backend != "cuckoo":
            raise NotSupportedError("current backend cannot remove keys")
        return self._filter.remove(key)

    def stats(self):
        """计数快照，独立 dict，filter 键下是底层过滤器的统计。"""
        return {
            "marks": self._marks,
            "queries": self._queries,
            "duplicates": self._duplicates,
            "filter": self._filter.stats(),
        }

    def to_bytes(self):
        head = _HEADER.pack(MAGIC, self._marks, self._queries, self._duplicates, self.fp_rate)
        if self.backend == "cuckoo":
            head = _HEADER.pack(
                MAGIC_CUCKOO, self._marks, self._queries, self._duplicates, self.fp_rate
            )
        return head + self._filter.to_bytes()

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, marks, queries, duplicates, fp_rate = _HEADER.unpack(blob[:_HEADER.size])
        if magic == MAGIC:
            backend = "bloom"
        elif magic == MAGIC_CUCKOO:
            backend = "cuckoo"
        else:
            raise ValueError("bad magic: %r" % (magic,))
        filter_cls = CuckooFilter if backend == "cuckoo" else BloomFilter
        obj = cls.__new__(cls)
        obj._filter = filter_cls.from_bytes(blob[_HEADER.size:])
        obj.capacity = obj._filter.capacity
        obj.fp_rate = fp_rate
        obj.backend = backend
        if backend == "cuckoo":
            obj.fp_bits = obj._filter.fp_bits
        obj._marks = marks
        obj._queries = queries
        obj._duplicates = duplicates
        return obj
