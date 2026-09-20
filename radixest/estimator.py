"""概率基数估算。

CardinalityEstimator 在小基数时保留精确集合，基数超过 exact_limit 后退化到
线性计数（Linear Counting）：key 经种子化哈希映射到位图，用零位比例估算基数。
位图有稀疏（set 存置位位置）与稠密（bytearray）两种表示，可按阈值互转；
两个估算器可 merge 成覆盖并集的新估算器，输入保持不变。
"""

import hashlib
import math
import pickle
import threading


def _hash_position(key, bits, seed):
    """把 key 确定性地哈希到 [0, bits) 的位图位置。"""
    payload = pickle.dumps((seed, key), protocol=4)
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") % bits


class _SparseBitmap:
    """稀疏位图：只在 set 里存被置位的位置。"""

    def __init__(self, bits, positions=None):
        self.bits = bits
        self.positions = set(positions) if positions else set()

    def set(self, position):
        if position in self.positions:
            return False
        self.positions.add(position)
        return True

    def cardinality(self):
        return len(self.positions)

    def to_dense(self):
        dense = _DenseBitmap(self.bits)
        for position in self.positions:
            dense.bytes[position >> 3] |= 1 << (position & 7)
        return dense

    def merge(self, other, dense_threshold):
        if other.bits != self.bits:
            raise ValueError("位图位数不一致，无法合并")
        if isinstance(other, _SparseBitmap):
            merged = self.positions | other.positions
            sparse = _SparseBitmap(self.bits, merged)
            if dense_threshold > 0 and len(merged) < dense_threshold:
                return sparse
            return sparse.to_dense()
        return self.to_dense().merge(other, dense_threshold)


class _DenseBitmap:
    """稠密位图：每个位置一个 bit，底层用 bytearray。"""

    def __init__(self, bits, data=None):
        self.bits = bits
        if data is None:
            self.bytes = bytearray((bits + 7) // 8)
            return
        self.bytes = bytearray(data)
        overhang = bits & 7
        if overhang:
            self.bytes[-1] &= (1 << overhang) - 1

    def set(self, position):
        byte_index = position >> 3
        bit = 1 << (position & 7)
        if self.bytes[byte_index] & bit:
            return False
        self.bytes[byte_index] |= bit
        return True

    def cardinality(self):
        total = sum(bin(byte).count("1") for byte in self.bytes)
        overhang = self.bits & 7
        if overhang:
            total -= bin(self.bytes[-1] >> overhang).count("1")
        return total

    def to_sparse(self):
        positions = set()
        for byte_index, byte in enumerate(self.bytes):
            while byte:
                low = byte & -byte
                offset = low.bit_length() - 1
                positions.add((byte_index << 3) + offset)
                byte ^= low
        return _SparseBitmap(self.bits, positions)

    def merge(self, other, dense_threshold):
        if other.bits != self.bits:
            raise ValueError("位图位数不一致，无法合并")
        other_bytes = (
            other.bytes if isinstance(other, _DenseBitmap) else other.to_dense().bytes
        )
        merged = _DenseBitmap(self.bits)
        for index, value in enumerate(self.bytes):
            merged.bytes[index] = value | other_bytes[index]
        return merged


class CardinalityEstimator:
    """位图概率基数估算器（精确段 + 线性计数）。"""

    def __init__(self, bits, seed, exact_limit, dense_threshold=1024):
        if not isinstance(bits, int) or bits <= 0:
            raise ValueError("bits 必须是正整数")
        if not isinstance(seed, int):
            raise ValueError("seed 必须是整数")
        if not isinstance(exact_limit, int) or exact_limit < 0:
            raise ValueError("exact_limit 必须是非负整数")
        if not isinstance(dense_threshold, int) or dense_threshold < 0:
            raise ValueError("dense_threshold 必须是非负整数")
        self.bits = bits
        self.seed = seed
        self.exact_limit = exact_limit
        self.dense_threshold = dense_threshold
        self._exact = set()
        self._bitmap = None
        self._lock = threading.RLock()

    def add(self, key):
        """记一个 key，返回这次是否是首次出现。"""
        with self._lock:
            if self._bitmap is None:
                if key in self._exact:
                    return False
                self._exact.add(key)
                if len(self._exact) > self.exact_limit:
                    self._promote()
                return True
            is_new = self._bitmap.set(_hash_position(key, self.bits, self.seed))
            if (
                is_new
                and isinstance(self._bitmap, _SparseBitmap)
                and self.dense_threshold > 0
                and len(self._bitmap.positions) >= self.dense_threshold
            ):
                self._bitmap = self._bitmap.to_dense()
            return is_new

    def _promote(self):
        if self.dense_threshold <= 0:
            self._bitmap = _DenseBitmap(self.bits)
        else:
            self._bitmap = _SparseBitmap(self.bits)
        for key in self._exact:
            self._bitmap.set(_hash_position(key, self.bits, self.seed))
        self._exact = None

    def count(self):
        """当前基数估算；精确段内为精确整数，超出后为线性计数估算。"""
        with self._lock:
            if self._bitmap is None:
                return len(self._exact)
            return self._estimate()

    def _estimate(self):
        zeroes = self.bits - self._bitmap.cardinality()
        if zeroes <= 0:
            return float(self.bits)
        return -self.bits * math.log(zeroes / self.bits)

    def error_bound(self):
        """相对误差上界（固定种子下 count 偏离真实基数的相对幅度不超过此值）。"""
        with self._lock:
            if self._bitmap is None:
                return 0.0
            ones = self._bitmap.cardinality()
            rho = ones / self.bits
            if rho <= 0.0:
                return 0.0
            if rho >= 0.8:
                # 超出线性计数工作区间（负载 n/m > 约 1.6，位图接近饱和），
                # 高斯近似不再适用；此时估上界为 m 而真基数 >= m，
                # 相对误差严格小于 1，故给出最保守的 100% 相对误差界。
                return 1.0
            rse = math.sqrt((math.exp(rho) - 1.0 - rho) / self.bits) / (
                -math.log1p(-rho)
            )
            # 取 6 倍标准差（相对标准差）作为概率误差上界；高负载下估计量
            # 有偏、分布偏斜，再叠 0.5% 的保守地板。
            return min(1.0, max(6.0 * rse, 0.005))

    @property
    def is_dense(self):
        """当前位图是否为稠密表示（精确段无位图，视为稀疏）。"""
        with self._lock:
            return isinstance(self._bitmap, _DenseBitmap)

    def to_dense(self):
        """显式把位图转成稠密表示，原地操作，count() 不变。"""
        with self._lock:
            if isinstance(self._bitmap, _SparseBitmap):
                self._bitmap = self._bitmap.to_dense()

    def to_sparse(self):
        """显式把位图转成稀疏表示，原地操作，count() 不变。"""
        with self._lock:
            if isinstance(self._bitmap, _DenseBitmap):
                self._bitmap = self._bitmap.to_sparse()

    def merge(self, other):
        """返回覆盖两者并集的新估算器，self 与 other 均不被修改。"""
        if not isinstance(other, CardinalityEstimator):
            raise TypeError("只能与 CardinalityEstimator 合并")
        if other.bits != self.bits or other.seed != self.seed:
            raise ValueError("bits 与 seed 必须一致才能合并")

        first, second = self, other
        if id(second) < id(first):
            first, second = second, first
        with first._lock, second._lock:
            exact_limit = min(self.exact_limit, other.exact_limit)
            dense_threshold = max(self.dense_threshold, other.dense_threshold)
            result = CardinalityEstimator(
                self.bits, self.seed, exact_limit, dense_threshold
            )

            exact_union = set()
            for side in (first, second):
                if side._bitmap is None:
                    exact_union |= side._exact
            for key in exact_union:
                result.add(key)

            if first._bitmap is None and second._bitmap is None:
                return result

            if first._bitmap is not None and second._bitmap is not None:
                result._bitmap = first._bitmap.merge(
                    second._bitmap, dense_threshold
                )
            else:
                prob = first._bitmap if first._bitmap is not None else second._bitmap
                if result._bitmap is None:
                    result._promote()
                result._bitmap = result._bitmap.merge(prob, dense_threshold)
            result._exact = None
            return result
