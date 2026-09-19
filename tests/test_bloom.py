"""bloomx 语义测试：逐条锁定 README「语义约定」。

允许存在红用例：凡源码与 README 不符之处，用例上方均以注释写明
「README 期望什么 / 实际发生什么」。
"""

import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bloomx import BloomFilter
from bloomx.bloom import _mix


def expected_num_bits(capacity, fp_rate):
    ln2 = math.log(2)
    return math.ceil(-capacity * math.log(fp_rate) / (ln2 * ln2))



class TestConstruction(unittest.TestCase):
    """README 第 1 条：构造与容量约束。"""

    def test_capacity_must_be_positive(self):
        for bad in (0, -1, -1000):
            with self.subTest(capacity=bad):
                with self.assertRaises(ValueError):
                    BloomFilter(bad, 0.01)

    # 【红】README 期望：capacity 必须是正整数，非整数（如 10.5）抛 ValueError。
    # 实际发生：源码只检查 capacity <= 0，10.5 被静默接受。
    def test_capacity_must_be_integer(self):
        with self.assertRaises(ValueError):
            BloomFilter(10.5, 0.01)

    def test_fp_rate_must_be_in_open_interval(self):
        for bad in (0.0, 1.0, -0.1, 1.5):
            with self.subTest(fp_rate=bad):
                with self.assertRaises(ValueError):
                    BloomFilter(1000, bad)

    def test_num_bits_formula(self):
        # m = ceil(-capacity * ln(fp_rate) / ln(2)^2)，固定输入断言
        self.assertEqual(BloomFilter(1000, 0.01).num_bits,
                         expected_num_bits(1000, 0.01))
        self.assertEqual(BloomFilter(1000, 0.01).num_bits, 9586)
        self.assertEqual(BloomFilter(100, 0.001).num_bits, 1438)
        self.assertEqual(BloomFilter(10, 0.01).num_bits, 96)

    # 【红】README 期望：k = max(1, round((m / capacity) * ln 2))，
    # 例如 (1000, 0.01) -> 7、(100, 0.001) -> 10。
    # 实际发生：源码用 log10(2) 且 int() 截断，得到 k=2 与 k=4。
    def test_num_hashes_formula(self):
        self.assertEqual(BloomFilter(1000, 0.01).num_hashes, 7)
        self.assertEqual(BloomFilter(100, 0.001).num_hashes, 10)
        self.assertEqual(BloomFilter(10, 0.01).num_hashes, 7)

    # 【红】README 期望：k 至少为 1（max(1, ...)），(1, 0.5) 时 m=2、k=1。
    # 实际发生：源码缺少 max(1, ...) 且用错误底数，得到 k=0。
    def test_num_hashes_at_least_one(self):
        self.assertEqual(BloomFilter(1, 0.5).num_hashes, 1)
        self.assertEqual(BloomFilter(2, 0.5).num_hashes, 1)

    def test_attributes_read_only(self):
        bf = BloomFilter(1000, 0.01)
        with self.assertRaises(AttributeError):
            bf.num_bits = 1
        with self.assertRaises(AttributeError):
            bf.num_hashes = 1
        with self.assertRaises(AttributeError):
            bf.num_added = 1


class TestHashing(unittest.TestCase):
    """README 第 2 条：哈希与探测。"""

    def test_type_error_for_unsupported_types(self):
        bf = BloomFilter(1000, 0.01)
        for bad in (1, 1.5, None, ["x"], {"x": 1}, object()):
            with self.subTest(item=bad):
                with self.assertRaises(TypeError):
                    bad in bf
                with self.assertRaises(TypeError):
                    bf.add(bad)

    def test_str_encoded_as_utf8(self):
        bf = BloomFilter(1000, 0.01)
        bf.add("héllo")
        self.assertIn("héllo".encode("utf-8"), bf)

    def test_double_hashing_probe_formula(self):
        # idx_i = (h1 + i * h2) mod m；哈希输入复现源码构造（UTF-8 字节）
        bf = BloomFilter(10, 0.01)  # m = 96
        bf.add("a")
        h1, h2 = _mix(b"a")
        m = bf.num_bits
        for i in range(bf.num_hashes):
            idx = (h1 + i * h2) % m
            self.assertTrue(bf._bits[idx >> 3] & (0x80 >> (idx & 7)))

    def test_add_and_contains_share_probe_function(self):
        bf = BloomFilter(1000, 0.01)
        keys = ["user-1001", "user-1002", "order-77", "sess-abc", "job-42",
                b"\x00\x01\x02", "重复元素"]
        for key in keys:
            bf.add(key)
        for key in keys:
            self.assertIn(key, bf)

    # 【红】README 期望：两个基础哈希必须各自依赖输入的每一个字节，
    # 即改一个字节 h1、h2 都应变化。
    # 实际发生：_mix 中 h2 = h2 * 31 从不读入字节，b"a" 与 b"b" 的 h2 相同。
    def test_both_base_hashes_depend_on_every_byte(self):
        _, h2_a = _mix(b"a")
        _, h2_b = _mix(b"b")
        self.assertNotEqual(h2_a, h2_b)
        h1_ab, h2_ab = _mix(b"ab")
        h1_ba, h2_ba = _mix(b"ba")
        self.assertNotEqual(h1_ab, h1_ba)
        self.assertNotEqual(h2_ab, h2_ba)

    # 【红】README 期望：两个不同元素的探测序列不允许完全相同。
    # 实际发生：h2 只依赖长度，且等长元素可发生 h1 碰撞；b"\x00a" 与
    # b"\x01\x00" 的 (h1, h2) 完全相同（探测位均为 [36, 43]），只 add 前者，
    # 后者也必然命中。
    def test_distinct_elements_have_distinct_probe_sequences(self):
        item_a = b"\x00a"
        item_b = b"\x01\x00"
        bf = BloomFilter(10, 0.01)  # m = 96
        bf.add(item_a)
        self.assertFalse(item_b in bf)


class TestFPSemantics(unittest.TestCase):
    """README 第 3 条：FP 语义。"""

    # 【红】README 期望：空过滤器对任何元素 in 返回 False，不允许抛异常。
    # 实际发生：_bits 初始为长度 0 的 bytearray（首次 add 才分配），
    # 查询直接 IndexError: bytearray index out of range。
    def test_empty_filter_contains_is_false_without_raise(self):
        bf = BloomFilter(1000, 0.01)
        self.assertFalse("anything" in bf)
        self.assertFalse(b"\xff" in bf)

    # 【红】README 期望：空过滤器 in 一律 False（k 至少为 1）。
    # 实际发生：(1, 0.5) 构造出 k=0，探测循环空转，任何元素都返回 True。
    def test_empty_filter_with_k_zero_still_false(self):
        bf = BloomFilter(1, 0.5)
        self.assertFalse("x" in bf)

    def test_no_false_negatives_fixed_inputs(self):
        bf = BloomFilter(2000, 0.01)
        present = ["present-key-%04d" % i for i in range(2000)]
        for key in present:
            bf.add(key)
        for key in present:
            self.assertIn(key, bf)

    def test_num_added_counts_calls_without_dedup(self):
        bf = BloomFilter(1000, 0.01)
        self.assertEqual(bf.num_added, 0)
        bf.add("dup")
        bf.add("dup")
        bf.add("other")
        self.assertEqual(bf.num_added, 3)

    def test_estimated_fp_formula_and_n_semantics(self):
        # (1 - e^(-k*n/m))^k，n 为 add 次数（不去重）
        bf = BloomFilter(1000, 0.01)
        self.assertEqual(bf.estimated_fp(), 0.0)
        for n in range(1, 6):
            bf.add("dup")
            k = bf.num_hashes
            expected = (1.0 - math.exp(-k * n / bf.num_bits)) ** k
            self.assertAlmostEqual(bf.estimated_fp(), expected)

    def test_fp_rate_statistics_fixed_inputs(self):
        # 固定输入的统计性断言：满容量 2000 个存在元素 + 500 个固定不存在元素
        bf = BloomFilter(2000, 0.01)
        present = ["present-key-%04d" % i for i in range(2000)]
        for key in present:
            bf.add(key)
        absent = ["absent-key-%04d" % i for i in range(500)]
        hits = sum(1 for key in absent if key in bf)
        self.assertLessEqual(hits, 60)  # 目标 1%（期望约 5 次），留余量


class TestSerialization(unittest.TestCase):
    """README 第 4 条：序列化。"""

    def _populated(self):
        bf = BloomFilter(1000, 0.01)
        for key in ["user-1001", "user-1002", "order-77", "sess-abc", "job-42"]:
            bf.add(key)
        return bf

    def test_serialize_layout(self):
        bf = self._populated()
        blob = bf.serialize()
        body_len = (bf.num_bits + 7) // 8
        self.assertEqual(len(blob), 28 + body_len)
        magic, m, k, n = struct.unpack(">4sQQQ", blob[:28])
        self.assertEqual(magic, b"BLMX")
        self.assertEqual(m, bf.num_bits)
        self.assertEqual(k, bf.num_hashes)
        self.assertEqual(n, bf.num_added)
        self.assertEqual(blob[28:], bytes(bf._bits))

    def test_loads_bad_magic_raises_value_error(self):
        blob = self._populated().serialize()
        bad = b"XXXX" + blob[4:]
        with self.assertRaises(ValueError):
            BloomFilter.loads(bad)

    # 【红】README 期望：loads 还原后 num_bits、num_hashes、num_added 与原实例一致。
    # 实际发生：unpack 字段顺序写成 (magic, num_hashes, num_bits, added)，
    # m 与 k 被对调（原 9586/2 -> 还原成 2/9586）。
    def test_roundtrip_fields(self):
        bf = self._populated()
        restored = BloomFilter.loads(bf.serialize())
        self.assertEqual(restored.num_bits, bf.num_bits)
        self.assertEqual(restored.num_hashes, bf.num_hashes)
        self.assertEqual(restored.num_added, bf.num_added)

    # 【红】README 期望：位数组内容一致，还原后 `in` 行为与原实例一致
    # （已加入元素必须仍命中）。
    # 实际发生：位数组虽原样拷回，但 m/k 对调导致探测位全部错位，
    # 5 个已加入元素 loads 后全部判为不存在（假阴性）。
    def test_roundtrip_bits_and_behavior(self):
        bf = self._populated()
        restored = BloomFilter.loads(bf.serialize())
        self.assertEqual(bytes(restored._bits), bytes(bf._bits))
        for key in ["user-1001", "user-1002", "order-77", "sess-abc", "job-42"]:
            self.assertIn(key, restored)


if __name__ == "__main__":
    unittest.main(verbosity=2)
