"""bloomx 布隆过滤器的 README 语义锁定测试（纯标准库 unittest）。

用例严格以仓库根目录 README.md 的「语义约定」为准。
运行：python3 -m unittest discover -s tests

允许存在红用例：每个红用例上方的注释都写明了
「README 期望什么 / 实际发生什么」，用于钉出源码缺陷。
"""

import math
import struct
import unittest

from bloomx import BloomFilter
from bloomx.bloom import _HEADER, _MAGIC, _mix


def _readme_params(capacity, fp_rate):
    """README 第 1 节给定的 m / k 构造公式，独立复算以便断言。"""
    ln2 = math.log(2.0)
    m = math.ceil(-capacity * math.log(fp_rate) / (ln2 * ln2))
    k = max(1, round((m / capacity) * ln2))
    return m, k


class TestConstruction(unittest.TestCase):
    def test_invalid_capacity_nonpositive(self):
        with self.assertRaises(ValueError):
            BloomFilter(0)
        with self.assertRaises(ValueError):
            BloomFilter(-7)

    # 红：README 第 1 节要求 capacity「必须是正整数」。
    # README 期望：非整数 capacity（如 1.5）抛 ValueError。
    # 实际发生：源码只检查 capacity <= 0，1.5 被接受（位数组按小数算出）。
    def test_invalid_capacity_noninteger_is_red(self):
        with self.assertRaises(ValueError):
            BloomFilter(1.5)

    def test_invalid_fp_rate(self):
        for bad in (0.0, 1.0, -0.01, 1.01):
            with self.subTest(bad=bad):
                with self.assertRaises(ValueError):
                    BloomFilter(100, bad)

    def test_num_bits_formula(self):
        for capacity, fp in [(1000, 0.01), (100, 0.001), (10, 0.2), (1, 0.5)]:
            expected_m, _ = _readme_params(capacity, fp)
            bf = BloomFilter(capacity, fp)
            self.assertEqual(bf.num_bits, expected_m)

    # 红：README 第 1 节要求 k = max(1, round((m / capacity) * ln 2))。
    # README 期望：(1000, 0.01) -> k=7；(100, 0.99) -> k=1；(1, 0.5) -> k=1。
    # 实际发生：源码用 log10(2) 代替 ln2、用 int() 截断且没有 max(1, ...)，
    # 分别得到 2、0、0（k=0 时 add/contains 的探测循环根本不执行）。
    def test_num_hashes_formula_is_red(self):
        cases = [(1000, 0.01), (100, 0.001), (100, 0.99), (1, 0.5), (10, 0.2)]
        for capacity, fp in cases:
            _, expected_k = _readme_params(capacity, fp)
            bf = BloomFilter(capacity, fp)
            with self.subTest(capacity=capacity, fp=fp):
                self.assertEqual(bf.num_hashes, expected_k)

    def test_attributes_read_only(self):
        bf = BloomFilter(100, 0.1)
        for attr in ("num_bits", "num_hashes", "num_added"):
            with self.subTest(attr=attr):
                with self.assertRaises(AttributeError):
                    setattr(bf, attr, 1)


class TestHashing(unittest.TestCase):
    def test_type_error_for_unsupported_types(self):
        bf = BloomFilter(100, 0.1)
        for bad in (123, 3.14, None, ["x"]):
            with self.subTest(bad=bad):
                with self.assertRaises(TypeError):
                    bf.add(bad)
                with self.assertRaises(TypeError):
                    bad in bf

    def test_str_encoded_as_utf8(self):
        bf = BloomFilter(1000, 0.01)
        bf.add("héllo")
        self.assertIn("héllo", bf)
        self.assertIn("héllo".encode("utf-8"), bf)

    def test_hash_input_construction_matches_source(self):
        # 哈希构造输入可复现：str 按 UTF-8 编码，bytes 原样参与 djb2 风格混合。
        self.assertEqual(_mix(b""), (5381, 52711))
        h1, _ = _mix(b"a")
        self.assertEqual(h1, ((5381 * 33) ^ ord("a")) & 0xFFFFFFFF)

    def test_add_and_contains_share_one_probe_function(self):
        bf = BloomFilter(1000, 0.01)
        for item in ("alpha", "beta", b"gamma"):
            bf.add(item)
            self.assertIn(item, bf)
            encoded = bytes(item, "utf-8") if isinstance(item, str) else item
            self.assertIn(encoded, bf)

    def test_double_hashing_probe_formula(self):
        # idx_i = (h1 + i * h2) mod m（i = 0..k-1），位序为 MSB-first。
        bf = BloomFilter(1000, 0.01)
        bf.add("probe-formula")
        h1, h2 = _mix(b"probe-formula")
        for i in range(bf.num_hashes):
            idx = (h1 + i * h2) % bf.num_bits
            self.assertTrue(bf._get_bit(idx), "bit %d should be set" % idx)

    # 红：README 第 2 节要求「两个基础哈希必须各自依赖输入的每一个字节」。
    # README 期望：对不同字节，h2 至少有一个不同（h2 随字节更新）。
    # 实际发生：_mix 中 h2 = ((h2 * 31)) & mask，循环体从不使用字节 b，
    # h2 对长度相同的任意输入恒为常数（任意单字节输入 h2 恒为 1634041）。
    def test_h2_depends_on_every_byte_is_red(self):
        self.assertNotEqual(_mix(b"a")[1], _mix(b"b")[1])
        self.assertNotEqual(_mix(b"x")[1], _mix(b"y")[1])

    # 红：README 第 2 节要求「两个不同元素的探测序列不允许完全相同」。
    # README 期望：不同元素的 (h1, h2) 不同，从而 k 个探测位的序列不同。
    # 实际发生：因 h2 与字节无关，可构造出不同元素 b'\x00a' 与
    # b'\x01\x00' 的 (h1, h2) 完全相同（均为 (5859876, 50655271)），
    # 在任意 m、任意 k 下探测序列逐位重合。
    def test_distinct_elements_probe_sequences_differ_is_red(self):
        first = b"\x00a"
        second = b"\x01\x00"
        self.assertNotEqual(first, second)
        m = 9586
        k = 7
        h1a, h2a = _mix(first)
        h1b, h2b = _mix(second)
        seq_a = [(h1a + i * h2a) % m for i in range(k)]
        seq_b = [(h1b + i * h2b) % m for i in range(k)]
        self.assertNotEqual(seq_a, seq_b)


class TestMembership(unittest.TestCase):
    def test_no_false_negatives_fixed_inputs(self):
        bf = BloomFilter(1000, 0.01)
        keys = ["fixed-key-%d" % i for i in range(500)]
        for key in keys:
            bf.add(key)
        for key in keys:
            self.assertIn(key, bf)

    def test_repeated_add_consistent(self):
        bf = BloomFilter(1000, 0.01)
        bf.add("same")
        bf.add("same")
        self.assertIn("same", bf)
        self.assertEqual(bf.num_added, 2)

    # 红：README 第 3 节要求「空过滤器对任何元素 in 必须返回 False，不允许抛异常」。
    # README 期望：未 add 任何元素时，"anything" in bf == False。
    # 实际发生：_bits 在首次 add 前是长度为 0 的 bytearray，__contains__
    # 直接索引 _bits[0]，抛 IndexError: bytearray index out of range。
    def test_empty_filter_membership_is_red(self):
        bf = BloomFilter(1000, 0.01)
        self.assertNotIn("anything", bf)


class TestEstimatedFp(unittest.TestCase):
    def test_empty_estimated_fp_is_zero(self):
        self.assertEqual(BloomFilter(1000, 0.01).estimated_fp(), 0.0)

    def test_n_counts_add_calls_without_dedup(self):
        # n 为 add 调用次数（不去重）：重复 add 两次与 add 两个不同元素，
        # 在 n=2 时的理论误判率应当相等。
        a = BloomFilter(1000, 0.01)
        a.add("dup")
        a.add("dup")
        b = BloomFilter(1000, 0.01)
        b.add("fixed-x")
        b.add("fixed-y")
        self.assertEqual(a.num_added, 2)
        self.assertEqual(b.num_added, 2)
        self.assertEqual(a.estimated_fp(), b.estimated_fp())

    def test_estimated_fp_matches_formula_with_current_k(self):
        bf = BloomFilter(1000, 0.01)
        keys = ["fixed-add-%d" % i for i in range(1000)]
        for key in keys:
            bf.add(key)
        expected = (
            1.0 - math.exp(-bf.num_hashes * bf.num_added / bf.num_bits)
        ) ** bf.num_hashes
        self.assertAlmostEqual(bf.estimated_fp(), expected)
        # 估计器与固定输入的实测假阳性率应同量级（2000 个固定未加入元素）。
        misses = ["fixed-miss-%d" % i for i in range(2000)]
        observed = sum(1 for key in misses if key in bf) / len(misses)
        self.assertLess(observed, bf.estimated_fp() * 4.0)

    # 红：README 第 3 节规定 estimated_fp() 使用 README 公式选出的 k。
    # README 期望：capacity=1000、fp_rate=0.01 时 m=9586、k=7，
    # n=1000 时理论误判率 (1 - e^(-7*1000/9586))^7 ≈ 0.01003。
    # 实际发生：k 被算成 2，estimated_fp() 返回 (1 - e^(-2*1000/9586))^2
    # ≈ 0.03546，实测假阳性率约 2.6%~3.5%，远超 1% 目标。
    def test_estimated_fp_uses_readme_k_is_red(self):
        capacity, fp = 1000, 0.01
        m, k = _readme_params(capacity, fp)
        bf = BloomFilter(capacity, fp)
        for i in range(1000):
            bf.add("fixed-add-%d" % i)
        expected = (1.0 - math.exp(-k * bf.num_added / m)) ** k
        self.assertAlmostEqual(bf.estimated_fp(), expected, places=4)


class TestSerialization(unittest.TestCase):
    def test_header_layout(self):
        # 28 字节头：magic "BLMX" + m、k、n 三个 8 字节无符号大端整数。
        bf = BloomFilter(1000, 0.01)
        bf.add("hdr")
        blob = bf.serialize()
        self.assertEqual(blob[:4], b"BLMX")
        self.assertEqual(_HEADER.size, 28)
        self.assertEqual(_HEADER.format, "!4sQQQ")
        magic, m, k, n = struct.unpack("!4sQQQ", blob[:28])
        self.assertEqual(magic, _MAGIC)
        self.assertEqual((m, k, n), (bf.num_bits, bf.num_hashes, bf.num_added))

    def test_payload_is_raw_bit_array(self):
        bf = BloomFilter(1000, 0.01)
        for i in range(10):
            bf.add("bit-raw-%d" % i)
        blob = bf.serialize()
        self.assertEqual(blob[28:], bytes(bf._bits))
        self.assertEqual(len(blob), 28 + (bf.num_bits + 7) // 8)

    def test_bad_magic_raises_value_error(self):
        data = b"XXXX" + bytes(24) + bytes(100)
        with self.assertRaises(ValueError):
            BloomFilter.loads(data)

    # 红：README 第 4 节要求 loads 还原出 num_bits / num_hashes /
    # num_added 与原实例一致的等价过滤器。
    # README 期望：头布局是 magic,m,k,n，还原后 (m,k,n) == (9586, 7, 3)。
    # 实际发生：unpack_from 的返回值被按 magic, num_hashes, num_bits,
    # added 接收，m 与 k 被互换，还原成 (2, 9586, 3)。
    def test_loads_restores_fields_is_red(self):
        bf = BloomFilter(1000, 0.01)
        for key in ("user-1001", "user-1002", "order-77"):
            bf.add(key)
        restored = BloomFilter.loads(bf.serialize())
        self.assertEqual(restored.num_bits, bf.num_bits)
        self.assertEqual(restored.num_hashes, bf.num_hashes)
        self.assertEqual(restored.num_added, bf.num_added)

    # 红：README 第 4 节要求还原后继续 add / in 行为一致。
    # README 期望：已加入的三个键 loads 后 in 仍为 True。
    # 实际发生：m、k 互换后用错误的探测函数查位数组，三个键全部查不到。
    def test_loads_membership_equivalent_is_red(self):
        bf = BloomFilter(1000, 0.01)
        keys = ["user-1001", "user-1002", "order-77"]
        for key in keys:
            bf.add(key)
        restored = BloomFilter.loads(bf.serialize())
        for key in keys:
            self.assertIn(key, restored)


if __name__ == "__main__":
    unittest.main()
