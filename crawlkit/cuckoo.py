"""标准库布谷鸟过滤器：指纹加双桶踢出，能加能删，踢不动就扩容重排。"""

import math
import struct
import sys
from array import array

from .hashing import fingerprint, hash_pair

MAGIC = b"DCK1"
# magic, num_buckets, bucket_size, fp_bits, capacity, added
_HEADER = struct.Struct(">4sIIIIQ")

_MASK64 = (1 << 64) - 1
_MAX_KICKS = 500
_TARGET_LOAD = 0.9


def _mix64(x):
    """splitmix64 终混，把指纹摊成另一个候选桶的下标偏移。"""
    x = ((x ^ (x >> 30)) * 0xBF58476D1CE4E5B9) & _MASK64
    x = ((x ^ (x >> 27)) * 0x94D049BB133111EB) & _MASK64
    return x ^ (x >> 31)


class CuckooFilter:
    """布谷鸟过滤器。

    每个键留一份 fp_bits 位指纹，落在两个候选桶之一，查询说不在就一定不在。
    槽位里同时留着键的 64 位哈希：扩容重排靠它找回第一个桶，remove 靠它只撤
    这个键自己那一份，同指纹的其他键不动。踢出链超限就翻倍扩容，新表在边上
    搭好才换上来，任何时刻查已加的键都命中。
    """

    BUCKET_SIZE = 2

    def __init__(self, capacity, fp_bits=12):
        capacity = int(capacity)
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        fp_bits = int(fp_bits)
        if not 1 <= fp_bits <= 32:
            raise ValueError("fp_bits must be in [1, 32]")
        self.capacity = capacity
        self.fp_bits = fp_bits
        self._bucket_size = self.BUCKET_SIZE
        needed = math.ceil(capacity / (self._bucket_size * _TARGET_LOAD))
        num_buckets = 4
        while num_buckets < needed:
            num_buckets *= 2
        self._num_buckets = num_buckets
        self._fps = [0] * (num_buckets * self._bucket_size)
        self._h1 = [0] * (num_buckets * self._bucket_size)
        self._added = 0

    def _place(self, fps, h1s, num_buckets, h1, fp):
        """把 (h1, fp) 塞进给定表。塞下返回 None；踢出链超限返回被挤在表外的
        (h1, fp)，调用方得接着安置，表里的条目一个都不能丢。"""
        mask = num_buckets - 1
        b = self._bucket_size
        i1 = h1 & mask
        i2 = i1 ^ (_mix64(fp) & mask)
        for base in (i1 * b, i2 * b):
            for s in range(b):
                idx = base + s
                if fps[idx] == 0:
                    fps[idx] = fp
                    h1s[idx] = h1
                    return None
        state = (h1 ^ (fp << 32) ^ 0x9E3779B97F4A7C15) & _MASK64
        i = i1 if state & 1 else i2
        for _ in range(_MAX_KICKS):
            state = (state * 6364136223846793005 + 1442695040888963407) & _MASK64
            idx = i * b + state % b
            fps[idx], fp = fp, fps[idx]
            h1s[idx], h1 = h1, h1s[idx]
            i = i ^ (_mix64(fp) & mask)
            base = i * b
            for s in range(b):
                idx = base + s
                if fps[idx] == 0:
                    fps[idx] = fp
                    h1s[idx] = h1
                    return None
        return (h1, fp)

    def _grow(self, pending):
        """桶数翻倍重排。pending 里是踢出链没安置下的 (h1, fp)，也得进新表。

        新表在边上完整搭好才换上来，旧表全程不动；搭失败了带着没安置的条目
        换个更大的表重来，全程迭代，不递归。
        """
        num_buckets = self._num_buckets
        b = self._bucket_size
        pend = list(pending)
        while True:
            num_buckets *= 2
            fps = [0] * (num_buckets * b)
            h1s = [0] * (num_buckets * b)
            ok = True
            for idx in range(len(self._fps)):
                fp = self._fps[idx]
                if fp:
                    dropped = self._place(fps, h1s, num_buckets, self._h1[idx], fp)
                    if dropped is not None:
                        pend.append(dropped)
                        ok = False
                        break
            while ok and pend:
                h1, fp = pend.pop()
                dropped = self._place(fps, h1s, num_buckets, h1, fp)
                if dropped is not None:
                    pend.append(dropped)
                    ok = False
            if ok:
                self._fps = fps
                self._h1 = h1s
                self._num_buckets = num_buckets
                return

    def add(self, key):
        """放入一个键。同一个键重复放不重复占位，返回是否新放进去了。"""
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, self.fp_bits)
        mask = self._num_buckets - 1
        b = self._bucket_size
        i1 = h1 & mask
        i2 = i1 ^ (_mix64(fp) & mask)
        fps = self._fps
        h1s = self._h1
        for base in (i1 * b, i2 * b):
            for s in range(b):
                idx = base + s
                if fps[idx] and h1s[idx] == h1:
                    return False
        dropped = self._place(fps, h1s, self._num_buckets, h1, fp)
        if dropped is not None:
            self._grow([dropped])
        self._added += 1
        return True

    def __contains__(self, key):
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, self.fp_bits)
        mask = self._num_buckets - 1
        b = self._bucket_size
        fps = self._fps
        i1 = h1 & mask
        i2 = i1 ^ (_mix64(fp) & mask)
        for base in (i1 * b, i2 * b):
            for s in range(b):
                if fps[base + s] == fp:
                    return True
        return False

    def remove(self, key):
        """撤掉一个键自己那份指纹，返回是否真的撤到了。同指纹的其他键不动。"""
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, self.fp_bits)
        mask = self._num_buckets - 1
        b = self._bucket_size
        i1 = h1 & mask
        i2 = i1 ^ (_mix64(fp) & mask)
        for base in (i1 * b, i2 * b):
            for s in range(b):
                idx = base + s
                if self._fps[idx] == fp and self._h1[idx] == h1:
                    self._fps[idx] = 0
                    self._h1[idx] = 0
                    self._added -= 1
                    return True
        return False

    def __len__(self):
        return self._added

    def stats(self):
        """计数快照，独立 dict。"""
        return {
            "added": self._added,
            "capacity": self.capacity,
            "fp_bits": self.fp_bits,
            "num_buckets": self._num_buckets,
            "bucket_size": self._bucket_size,
            "size_bytes": len(self._fps) * 12,
        }

    def to_bytes(self):
        """落盘格式：定长头加指纹表和哈希表，头里带上构造参数与计数。"""
        head = _HEADER.pack(
            MAGIC,
            self._num_buckets,
            self._bucket_size,
            self.fp_bits,
            self.capacity,
            self._added,
        )
        fps = array("I", self._fps)
        h1s = array("Q", self._h1)
        if sys.byteorder == "little":
            fps.byteswap()
            h1s.byteswap()
        return head + fps.tobytes() + h1s.tobytes()

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, num_buckets, bucket_size, fp_bits, capacity, added = _HEADER.unpack(
            blob[:_HEADER.size]
        )
        if magic != MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        if num_buckets < 1 or num_buckets & (num_buckets - 1):
            raise ValueError("num_buckets must be a power of two")
        if bucket_size < 1:
            raise ValueError("bucket_size must be >= 1")
        if not 1 <= fp_bits <= 32:
            raise ValueError("fp_bits must be in [1, 32]")
        n = num_buckets * bucket_size
        want = _HEADER.size + n * 4 + n * 8
        if len(blob) != want:
            raise ValueError("payload length mismatch")
        fps = array("I")
        fps.frombytes(blob[_HEADER.size:_HEADER.size + n * 4])
        h1s = array("Q")
        h1s.frombytes(blob[_HEADER.size + n * 4:want])
        if sys.byteorder == "little":
            fps.byteswap()
            h1s.byteswap()
        obj = cls.__new__(cls)
        obj.capacity = capacity
        obj.fp_bits = fp_bits
        obj._bucket_size = bucket_size
        obj._num_buckets = num_buckets
        obj._fps = list(fps)
        obj._h1 = list(h1s)
        obj._added = added
        return obj
