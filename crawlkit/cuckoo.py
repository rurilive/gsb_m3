"""标准库布谷鸟过滤器：指纹双桶 + 踢出，支持删除与满载扩容。

每个槽位是一个 64 位无符号字：低 fp_bits 位放指纹（恒不为零，见
hashing.fingerprint），高 52 位放该键哈希 h1 的低位（“归属”），全零
字即空槽哨兵。归属位一次取够 52 位，不同键在“指纹 + 归属”上撞车的
概率是 2^-52，可视为不撞；之后翻多少倍表都能按归属定位，扩容不依赖
原 key，表最多 2**52 个桶。

桶数永远是 2 的幂，于是
    alt(i, f) = i xor (hash(f) & mask)
是一个对合（alt(alt(i, f), f) == i），删除时不需要原 key 的哈希。

满载时不原地改表：另建一张翻倍的新表，把旧表每一条连同踢出链末端
的“孤儿”条目一起重排，全部落位后才一次性替换——重排期间旧表完整
在场，已加入的键任何时刻都命中。重排失败就整体回滚再翻倍重试，整条
流程只有循环，没有递归。
"""

import random
import struct
from array import array

from .hashing import fingerprint, hash_pair

MAGIC = b"DBCK"
# magic, capacity, num_buckets, fp_bits, slots, added
_HEADER = struct.Struct(">4sIIIIQ")

BUCKETSIZE = 4
MAX_KICKS = 500
# 同一规模重排时踢出链是随机游走，单次失败不代表放不下，重试几次
REBUILD_ATTEMPTS = 8
# 初始按约 0.8 的桶内装载率定桶数，给踢出留余量
LOAD_FACTOR = 0.8
# 防病态碰撞下无限翻倍（正常数据走不到）
MAX_GROWTH_STEPS = 32

_FP_BITS_MAX = 16
_WORD_BITS = 64


class CuckooFilter:
    """可删的定指纹布谷鸟过滤器。

    capacity 是预期容量，只用来定初始桶数；踢出链耗尽或同桶对挤满时
    会自动翻倍扩容重排。查询说不在就一定不在，说在可能没加过。
    """

    def __init__(self, capacity, fp_bits=12):
        capacity = int(capacity)
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        fp_bits = int(fp_bits)
        if not 1 <= fp_bits <= _FP_BITS_MAX:
            raise ValueError("fp_bits must be in [1, %d]" % _FP_BITS_MAX)
        self.capacity = capacity
        self.fp_bits = fp_bits
        self._fp_mask = (1 << fp_bits) - 1
        self._origin_mask = (1 << (_WORD_BITS - fp_bits)) - 1
        self.num_buckets = self._size_for(capacity)
        self._table = array("Q", [0]) * (self.num_buckets * BUCKETSIZE)
        self._added = 0
        self._rng = random.Random()
        self._alt_cache = {}

    @staticmethod
    def _size_for(capacity):
        needed = max(1, int(capacity / (BUCKETSIZE * LOAD_FACTOR)) + 1)
        size = 1
        while size < needed:
            size <<= 1
        return size

    # ---- 打包与定位 -----------------------------------------------------

    def _pack(self, fp, origin):
        return ((origin & self._origin_mask) << self.fp_bits) | fp

    def _fp_of(self, entry):
        return entry & self._fp_mask

    def _origin_of(self, entry):
        return entry >> self.fp_bits

    def _alt_step(self, fp, num_buckets):
        """指纹派生的 alt 步长，落在 [0, num_buckets)；XOR 天然对合。"""
        h = self._alt_cache.get(fp)
        if h is None:
            h, _ = hash_pair("ck-alt:%d" % fp)
            self._alt_cache[fp] = h
        return h & (num_buckets - 1)

    def _alt_bucket(self, bucket, fp, num_buckets):
        step = self._alt_step(fp, num_buckets)
        if step == 0:
            # 步长 0 会让两个候选桶塌成同一个；挪到对半分，仍是对合
            step = num_buckets >> 1
        return bucket ^ step

    # ---- 增删查 ---------------------------------------------------------

    def add(self, key):
        """加入一个键。归属桶对里已有同指纹就不重复计数。

        踢出链耗尽时翻倍扩容重排，重排后再试，直到落位；全程无递归。
        """
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, self.fp_bits)
        origin = h1 & self._origin_mask
        while True:
            num_buckets = self.num_buckets
            mask = num_buckets - 1
            i1 = origin & mask
            i2 = self._alt_bucket(i1, fp, num_buckets)
            if self._has_same_origin(i1, fp, origin) or self._has_same_origin(
                i2, fp, origin
            ):
                # 同一个键（同指纹同归属）已经在表里，幂等返回不计数，
                # 否则它的副本会无限堆积在同一对桶，扩容也劈不开
                return
            pair_slots = BUCKETSIZE if i1 == i2 else 2 * BUCKETSIZE
            pair_full = self._count_fp(i1, fp) + (
                0 if i1 == i2 else self._count_fp(i2, fp)
            ) >= pair_slots
            if pair_full:
                # 同指纹已占满这对桶的全部槽：踢出也腾不出位置，
                # 先翻倍重排（两桶在 2m 表里劈成两对）再落位
                self._grow(fp, origin)
                continue
            orphan = self._place(self._table, num_buckets, fp, origin)
            if orphan is None:
                break
            self._grow(fp, origin)
        self._added += 1

    def _grow(self, fp, origin):
        """翻倍重排（需要时继续翻倍），旧表全程不动，换表是原子一帧。"""
        new_buckets = self.num_buckets
        rebuilt = None
        for _ in range(MAX_GROWTH_STEPS):
            new_buckets <<= 1
            if new_buckets > (1 << (_WORD_BITS - self.fp_bits)):
                break
            for _ in range(REBUILD_ATTEMPTS):
                rebuilt = self._rebuild(new_buckets, fp, origin)
                if rebuilt is not None:
                    break
            if rebuilt is not None:
                break
        if rebuilt is None:
            raise RuntimeError("cuckoo filter cannot grow further")
        self._table = rebuilt
        self.num_buckets = new_buckets

    def _rebuild(self, new_buckets, fp, origin):
        """在局部新表上重排全部旧条目再放新键；失败返回 None。

        旧表自始至终不被触碰，失败即丢弃新表，无任何回滚缺口。
        """
        table = array("Q", [0]) * (new_buckets * BUCKETSIZE)
        old_table = self._table
        for off in range(len(old_table)):
            entry = old_table[off]
            if entry == 0:
                continue
            if self._place(
                table, new_buckets, self._fp_of(entry), self._origin_of(entry)
            ) is not None:
                return None
        if self._place(table, new_buckets, fp, origin) is not None:
            return None
        return table

    def _place(self, table, num_buckets, fp, origin):
        """在归属桶对放置一条；挤出的旧条目沿踢出链搬家，纯循环。

        成功返回 None。链耗尽时把整条链的交换倒放回去，表恢复成调用前
        的状态，返回没落下的 (fp, origin)（即入参本身）。
        """
        mask = num_buckets - 1
        b1 = origin & mask
        b2 = self._alt_bucket(b1, fp, num_buckets)
        for base in (b1, b2):
            slot = self._find_empty(table, base)
            if slot >= 0:
                table[slot] = self._pack(fp, origin)
                return None
        cur_fp = fp
        cur_origin = origin
        # 持有条目准备放入的桶，先在它合法的 b1/b2 里随机挑一个
        bucket = b1 if self._rng.randrange(2) == 0 else b2
        # 整条踢出链固定踢每个桶的同一个槽位 j（经典布谷鸟做法）：每步
        # 只做“交换”，不会回头覆盖链上早先安放的条目
        j = self._rng.randrange(BUCKETSIZE)
        trail = []
        for _ in range(MAX_KICKS):
            slot = bucket * BUCKETSIZE + j
            victim = table[slot]
            table[slot] = self._pack(cur_fp, cur_origin)
            trail.append((slot, victim))
            # 被踢者变成新的持有条目。它原来合法地躺在 bucket 里，
            # XOR 对合保证它的另一个合法桶就是 bucket XOR step(fp)。
            # 不能拿 origin 另算：链上的 bucket 才是它此刻的合法位置。
            cur_fp = self._fp_of(victim)
            cur_origin = self._origin_of(victim)
            bucket = self._alt_bucket(bucket, cur_fp, num_buckets)
            empty = self._find_empty(table, bucket)
            if empty >= 0:
                table[empty] = self._pack(cur_fp, cur_origin)
                return None
        # 倒放：每个槽写回交换前的原条目，表逐位复原
        for slot, old in reversed(trail):
            table[slot] = old
        return cur_fp, cur_origin

    def remove(self, key):
        """撤下这个键自己的那条指纹，返回是否命中。

        只在归属桶对里找“同指纹且同归属”的槽：同指纹但归属不同的键
        （哪怕恰好挤进同一对桶）有独立 origin，不被连带删除。
        """
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, self.fp_bits)
        origin = h1 & self._origin_mask
        mask = self.num_buckets - 1
        i1 = h1 & mask
        i2 = self._alt_bucket(i1, fp, self.num_buckets)
        for base in (i1, i2):
            start = base * BUCKETSIZE
            for slot in range(start, start + BUCKETSIZE):
                entry = self._table[slot]
                if (
                    entry
                    and (entry & self._fp_mask) == fp
                    and entry >> self.fp_bits == origin
                ):
                    self._table[slot] = 0
                    self._added -= 1
                    return True
        return False

    def __contains__(self, key):
        h1, h2 = hash_pair(key)
        fp = fingerprint(h2, self.fp_bits)
        i1 = h1 & (self.num_buckets - 1)
        i2 = self._alt_bucket(i1, fp, self.num_buckets)
        return self._has_entry(i1, fp) or self._has_entry(i2, fp)

    def __len__(self):
        return self._added

    # ---- 表内小工具 -----------------------------------------------------

    def _find_empty(self, table, bucket):
        base = bucket * BUCKETSIZE
        for slot in range(base, base + BUCKETSIZE):
            if table[slot] == 0:
                return slot
        return -1

    def _find_fp(self, table, bucket, fp):
        base = bucket * BUCKETSIZE
        end = base + BUCKETSIZE
        target = fp
        mask = self._fp_mask
        for slot in range(base, end):
            entry = table[slot]
            if entry and (entry & mask) == target:
                return slot
        return -1

    def _has_entry(self, bucket, fp):
        return self._find_fp(self._table, bucket, fp) >= 0

    def _has_same_origin(self, bucket, fp, origin):
        """桶里是否已有同指纹且同归属的条目，即同一个键。"""
        base = bucket * BUCKETSIZE
        for slot in range(base, base + BUCKETSIZE):
            entry = self._table[slot]
            if (
                entry
                and (entry & self._fp_mask) == fp
                and entry >> self.fp_bits == origin
            ):
                return True
        return False

    def _count_fp(self, bucket, fp):
        base = bucket * BUCKETSIZE
        mask = self._fp_mask
        count = 0
        for slot in range(base, base + BUCKETSIZE):
            entry = self._table[slot]
            if entry and (entry & mask) == fp:
                count += 1
        return count

    # ---- 统计与落盘 -----------------------------------------------------

    def load_factor(self):
        return self._added / float(self.num_buckets * BUCKETSIZE)

    def stats(self):
        """计数快照，独立 dict。"""
        return {
            "added": self._added,
            "capacity": self.capacity,
            "num_buckets": self.num_buckets,
            "bucket_size": BUCKETSIZE,
            "fp_bits": self.fp_bits,
            "load_factor": self.load_factor(),
            "size_bytes": len(self._table) * 8,
        }

    def to_bytes(self):
        """落盘格式：定长头加 64 位槽位序列。"""
        head = _HEADER.pack(
            MAGIC, self.capacity, self.num_buckets, self.fp_bits,
            len(self._table), self._added,
        )
        return head + bytes(self._table)

    @classmethod
    def from_bytes(cls, blob):
        if len(blob) < _HEADER.size:
            raise ValueError("blob too short")
        magic, capacity, num_buckets, fp_bits, slots, added = _HEADER.unpack(
            blob[:_HEADER.size]
        )
        if magic != MAGIC:
            raise ValueError("bad magic: %r" % (magic,))
        if capacity <= 0:
            raise ValueError("bad capacity")
        if not 1 <= fp_bits <= _FP_BITS_MAX:
            raise ValueError("bad fp_bits")
        if num_buckets & (num_buckets - 1):
            raise ValueError("num_buckets must be a power of two")
        if slots != num_buckets * BUCKETSIZE:
            raise ValueError("slot count mismatch")
        payload = blob[_HEADER.size:]
        if len(payload) != slots * 8:
            raise ValueError("payload length mismatch")
        obj = cls.__new__(cls)
        obj.capacity = capacity
        obj.fp_bits = fp_bits
        obj._fp_mask = (1 << fp_bits) - 1
        obj._origin_mask = (1 << (_WORD_BITS - fp_bits)) - 1
        obj.num_buckets = num_buckets
        obj._table = array("Q", payload)
        obj._added = added
        obj._rng = random.Random()
        obj._alt_cache = {}
        return obj
