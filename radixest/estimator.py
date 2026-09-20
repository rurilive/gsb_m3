"""概率基数估算。

CardinalityEstimator 在不同 key 数不超过 exact_limit 时走精确集合，结果与
DistinctCounter 一致；超过上限后退化成一张位图做 Linear Counting：每个 key
哈希到一位，靠位图中 0 位的比例反推基数，内存只跟位图位数走，与基数无关。

位图有两种表示：稀疏表示用 set 存被置位的位号，稠密表示用 bytearray 存整个
位图。置位数涨过 sparse_max 时自动转稠密，也可以用 to_dense()/to_sparse()
显式互转；两种表示记录的信息完全相同，count() 不会因转换而跳变。
"""

import hashlib
import math
import threading


def _encode_key(key):
    """把可哈希 key 编成带类型前缀的稳定字节串。

    类型前缀保证不同但相似的类型（如 "1"、1、1.0、b"1"）不会编出同样的字节。
    """
    if isinstance(key, str):
        return b"s" + key.encode("utf-8")
    if isinstance(key, bool):
        return b"b" + (b"1" if key else b"0")
    if isinstance(key, int):
        return b"i" + str(key).encode("ascii")
    if isinstance(key, float):
        return b"f" + repr(key).encode("ascii")
    if key is None:
        return b"n"
    if isinstance(key, bytes):
        return b"y" + key
    if isinstance(key, (list, dict, set)):
        raise TypeError(f"unhashable type: {type(key).__name__!r}")
    if isinstance(key, tuple):
        parts = [b"t("]
        for item in key:
            part = _encode_key(item)
            parts.append(str(len(part)).encode("ascii"))
            parts.append(b":")
            parts.append(part)
        parts.append(b")")
        return b"".join(parts)
    return b"o" + repr(key).encode("utf-8")


class CardinalityEstimator:
    """位图 + 精确段的概率基数估算器。

    不同 key 数不超过 exact_limit 时精确计数；超过后用 bits 位的位图做
    Linear Counting。位图默认稀疏存储，置位数超过 sparse_max 时自动转稠密。
    """

    def __init__(self, bits=1 << 14, seed=0, exact_limit=128, sparse_max=1024):
        if isinstance(bits, bool) or not isinstance(bits, int):
            raise TypeError("bits must be an int")
        if not 1 <= bits <= 1 << 32:
            raise ValueError("bits must be in [1, 2**32]")
        if not isinstance(seed, int):
            raise TypeError("seed must be an int")
        if isinstance(exact_limit, bool) or not isinstance(exact_limit, int) or exact_limit < 0:
            raise ValueError("exact_limit must be a non-negative int")
        if isinstance(sparse_max, bool) or not isinstance(sparse_max, int) or sparse_max < 0:
            raise ValueError("sparse_max must be a non-negative int")

        self.bits = bits
        self.seed = seed
        self.exact_limit = exact_limit
        self.sparse_max = sparse_max

        self._exact = True
        self._keys = set()
        self._sparse = set()
        self._dense = None
        self._lock = threading.Lock()

    def is_exact(self):
        """当前是否仍处在精确段（基数未超过 exact_limit）。"""
        return self._exact

    def representation(self):
        """位图当前表示：'exact'（精确段）、'sparse' 或 'dense'。"""
        with self._lock:
            if self._exact:
                return "exact"
            return "dense" if self._dense is not None else "sparse"

    def _position(self, key):
        digest = hashlib.blake2b(
            _encode_key(key), key=str(self.seed).encode("ascii"), digest_size=8
        ).digest()
        return int.from_bytes(digest, "big") % self.bits

    def add(self, key):
        """记一个 key。

        精确段内首次出现返回 True、重复返回 False，行为与 DistinctCounter 一致；
        超过 exact_limit 退化为概率估算后无法再判重，返回 None。
        """
        with self._lock:
            if self._exact:
                if key in self._keys:
                    return False
                self._keys.add(key)
                if len(self._keys) <= self.exact_limit:
                    return True
                self._promote_locked()
                return None
            self._set_bit_locked(self._position(key))
            return None

    def _promote_locked(self):
        """精确集合超过上限：把已记录的 key 全部灌进位图并丢弃精确集合。"""
        self._dense = None
        self._sparse = {self._position(key) for key in self._keys}
        self._keys = set()
        self._exact = False
        self._maybe_sparse_to_dense_locked()

    def _set_bit_locked(self, position):
        if self._dense is not None:
            self._dense[position >> 3] |= 1 << (position & 7)
            return
        if position not in self._sparse:
            self._sparse.add(position)
            self._maybe_sparse_to_dense_locked()

    def _maybe_sparse_to_dense_locked(self):
        if len(self._sparse) > self.sparse_max:
            self._convert_to_dense_locked()

    def _convert_to_dense_locked(self):
        dense = bytearray((self.bits + 7) >> 3)
        for position in self._sparse:
            dense[position >> 3] |= 1 << (position & 7)
        self._dense = dense
        self._sparse = set()

    def _convert_to_sparse_locked(self):
        positions = set(self._iter_positions_locked())
        self._dense = None
        self._sparse = positions

    def _iter_positions_locked(self):
        if self._dense is not None:
            for index, byte in enumerate(self._dense):
                while byte:
                    low = byte & -byte
                    offset = low.bit_length() - 1
                    yield (index << 3) + offset
                    byte ^= low
        else:
            yield from self._sparse

    def _set_bits_locked(self):
        if self._dense is not None:
            return sum(bin(byte).count("1") for byte in self._dense)
        return len(self._sparse)

    def to_dense(self):
        """显式转成稠密位图表示，返回自身。精确段内为空操作。"""
        with self._lock:
            if not self._exact and self._dense is None:
                self._convert_to_dense_locked()
        return self

    def to_sparse(self):
        """显式转回稀疏位图表示，返回自身。精确段内为空操作。"""
        with self._lock:
            if not self._exact and self._dense is not None:
                self._convert_to_sparse_locked()
        return self

    def count(self):
        """估算当前基数；不超过 exact_limit 时为精确值，否则为 Linear Counting 估算。"""
        with self._lock:
            if self._exact:
                return len(self._keys)
            set_bits = self._set_bits_locked()
            zeros = self.bits - set_bits
            if zeros <= 0:
                return int(round(self.bits * math.log(self.bits)))
            return int(round(self.bits * math.log(self.bits / zeros)))

    def error_bound(self):
        """count() 的相对误差上界（约 3 倍标准差）；精确段返回 0.0。

        位图接近饱和（0 位耗尽）时上界封顶为 1.0，表示估算已不可信。
        """
        with self._lock:
            if self._exact:
                return 0.0
            set_bits = self._set_bits_locked()
            zeros = self.bits - set_bits
            if zeros <= 0:
                return 1.0
            estimate = self.bits * math.log(self.bits / zeros)
            if estimate <= 0:
                return 1.0
            rho = estimate / self.bits
            variance = self.bits * (math.exp(rho) - rho - 1.0)
            return min(1.0, 3.0 * math.sqrt(variance) / estimate)

    def merge(self, other):
        """返回覆盖 self 与 other 并集的新估算器，两边均不修改。

        要求两边位图位数与种子相同；双方都在精确段且并集不超过 exact_limit
        时合并结果仍精确，否则合并位图走概率估算。
        """
        if not isinstance(other, CardinalityEstimator):
            raise TypeError("can only merge another CardinalityEstimator")
        if self.bits != other.bits or self.seed != other.seed:
            raise ValueError("estimators must share bits and seed to merge")

        with self._lock, other._lock:
            if self._exact and other._exact and len(self._keys | other._keys) <= self.exact_limit:
                merged = CardinalityEstimator(
                    self.bits, self.seed, self.exact_limit, self.sparse_max
                )
                merged._keys = set(self._keys) | set(other._keys)
                return merged

            merged = CardinalityEstimator(
                self.bits, self.seed, self.exact_limit, self.sparse_max
            )
            merged._exact = False
            use_dense = self._dense is not None or other._dense is not None
            if use_dense:
                dense = bytearray((self.bits + 7) >> 3)
                for estimator in (self, other):
                    if estimator._dense is not None:
                        for index, byte in enumerate(estimator._dense):
                            dense[index] |= byte
                    else:
                        for position in estimator._iter_positions_locked():
                            dense[position >> 3] |= 1 << (position & 7)
                merged._dense = dense
                merged._sparse = set()
            else:
                positions = set(self._sparse)
                positions.update(other._sparse)
                for estimator in (self, other):
                    if estimator._exact:
                        positions.update(estimator._position(key) for key in estimator._keys)
                merged._sparse = positions
                if len(positions) > self.sparse_max:
                    merged._convert_to_dense_locked()
            return merged
