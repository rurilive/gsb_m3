"""布隆过滤器：概率成员判断，允许假阳性、绝无假阴性。

语义约定见 README，本文件与 README 有出入时以 README 为准。
"""

import math
import struct


def _as_bytes(item):
    if isinstance(item, str):
        return item.encode("utf-8")
    if isinstance(item, (bytes, bytearray)):
        return bytes(item)
    raise TypeError("item must be str or bytes")


def _mix(data):
    """djb2 双哈希变体，返回 (h1, h2) 两个 32 位值。"""
    h1 = 5381
    h2 = 52711
    for b in data:
        h1 = ((h1 * 33) ^ b) & 0xFFFFFFFF
        h2 = ((h2 * 31)) & 0xFFFFFFFF
    return h1, h2


_MAGIC = b"BLMX"
_HEADER = struct.Struct("!4sQQQ")


class BloomFilter:
    """布隆过滤器：允许假阳性，绝无假阴性。

    - 构造时按 capacity 与 fp_rate 取最优位数组大小与哈希个数（公式见 README）
    - add(item) / ``item in bf``：元素为 str 或 bytes
    - estimated_fp()：当前理论误判率
    - serialize() / loads(data)：头部 + 位数组，往返等价
    """

    def __init__(self, capacity, fp_rate=0.01):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if not 0.0 < fp_rate < 1.0:
            raise ValueError("fp_rate must be in (0, 1)")
        ln2 = math.log(2)
        self._num_bits = math.ceil(-capacity * math.log(fp_rate) / (ln2 * ln2))
        self._num_hashes = int((self._num_bits / capacity) * math.log10(2))
        self._added = 0
        self._bits = bytearray(0)

    @property
    def num_bits(self):
        return self._num_bits

    @property
    def num_hashes(self):
        return self._num_hashes

    @property
    def num_added(self):
        return self._added

    def add(self, item):
        if not self._bits:
            self._bits = bytearray((self._num_bits + 7) // 8)
        h1, h2 = _mix(_as_bytes(item))
        for i in range(self._num_hashes):
            self._set_bit((h1 + i * h2) % self._num_bits)
        self._added += 1

    def __contains__(self, item):
        h1, h2 = _mix(_as_bytes(item))
        for i in range(self._num_hashes):
            if not self._get_bit((h1 + i * h2) % self._num_bits):
                return False
        return True

    def estimated_fp(self):
        k = self._num_hashes
        return (1.0 - math.exp(-k * self._added / self._num_bits)) ** k

    def serialize(self):
        header = _HEADER.pack(_MAGIC, self._num_bits, self._num_hashes, self._added)
        return header + bytes(self._bits)

    @classmethod
    def loads(cls, data):
        magic, num_hashes, num_bits, added = _HEADER.unpack_from(data, 0)
        if magic != _MAGIC:
            raise ValueError("bad magic, not a bloomx payload")
        obj = cls.__new__(cls)
        obj._num_bits = num_bits
        obj._num_hashes = num_hashes
        obj._added = added
        obj._bits = bytearray(data[_HEADER.size:])
        return obj

    def _set_bit(self, idx):
        self._bits[idx >> 3] |= 0x80 >> (idx & 7)

    def _get_bit(self, idx):
        return self._bits[idx >> 3] & (0x80 >> (idx & 7))
