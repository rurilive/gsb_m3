"""HuffmanTree 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from huffx.tree import (
    EmptySymbolError,
    HuffError,
    HuffmanTree,
    InvalidBitstreamError,
    InvalidFrequencyError,
    UnknownSymbolError,
    build_frequency,
)


class BuildFrequencyTest(unittest.TestCase):
    def test_counts_each_symbol(self):
        self.assertEqual(build_frequency("aab"), {"a": 2, "b": 1})

    def test_empty_text_is_empty_mapping(self):
        self.assertEqual(build_frequency(""), {})


class HuffmanTreeTest(unittest.TestCase):
    def make(self):
        return HuffmanTree({"a": 5, "b": 2, "c": 1, "d": 1})

    def test_symbols_sorted(self):
        self.assertEqual(self.make().symbols(), ["a", "b", "c", "d"])

    def test_code_table_ordered_by_length_then_symbol(self):
        self.assertEqual(self.make().code_table(),
                         [("a", "1"), ("b", "00"), ("c", "010"), ("d", "011")])

    def test_codes_are_prefix_free(self):
        codes = list(self.make().codes().values())
        for i, left in enumerate(codes):
            for j, right in enumerate(codes):
                if i != j:
                    self.assertFalse(left.startswith(right))

    def test_weighted_path_length(self):
        self.assertEqual(self.make().weighted_path_length(), 15)

    def test_average_length(self):
        self.assertAlmostEqual(self.make().average_length(), 15 / 9)

    def test_naive_fixed_width_is_ceiling_log2(self):
        self.assertEqual(self.make().fixed_width(), 2)
        self.assertAlmostEqual(self.make().naive_average_length(), 2.0)

    def test_huffman_not_worse_than_fixed_width(self):
        tree = self.make()
        total = sum({"a": 5, "b": 2, "c": 1, "d": 1}.values())
        self.assertLessEqual(tree.weighted_path_length(),
                             total * tree.fixed_width())

    def test_rescan_count_counts_two_scans_per_merge(self):
        self.assertEqual(self.make().rescan_count(), 6)

    def test_encode_decode_roundtrip(self):
        tree = self.make()
        text = "abacabadabacaba"
        self.assertEqual(tree.decode(tree.encode(text)), text)

    def test_encode_matches_codes(self):
        tree = self.make()
        self.assertEqual(tree.encode("abcd"), "1" + "00" + "010" + "011")

    def test_decode_empty_bitstream(self):
        self.assertEqual(self.make().decode(""), "")

    def test_unknown_symbol_rejected(self):
        with self.assertRaises(UnknownSymbolError):
            self.make().encode("z")

    def test_invalid_bit_character_rejected(self):
        with self.assertRaises(InvalidBitstreamError):
            self.make().decode("10x")

    def test_truncated_bitstream_rejected(self):
        with self.assertRaises(InvalidBitstreamError):
            self.make().decode("01")

    def test_single_symbol_uses_zero_code(self):
        tree = HuffmanTree({"x": 4})
        self.assertEqual(tree.codes(), {"x": "0"})
        self.assertEqual(tree.encode("xxx"), "000")
        self.assertEqual(tree.decode("000"), "xxx")
        self.assertEqual(tree.rescan_count(), 0)

    def test_single_symbol_rejects_one_bit(self):
        with self.assertRaises(InvalidBitstreamError):
            HuffmanTree({"x": 4}).decode("1")

    def test_equal_frequencies_are_deterministic(self):
        first = HuffmanTree({"a": 1, "b": 1, "c": 1, "d": 1})
        second = HuffmanTree({"a": 1, "b": 1, "c": 1, "d": 1})
        self.assertEqual(first.codes(), second.codes())

    def test_empty_frequency_rejected(self):
        with self.assertRaises(EmptySymbolError):
            HuffmanTree({})

    def test_negative_frequency_rejected(self):
        with self.assertRaises(InvalidFrequencyError):
            HuffmanTree({"a": -1})

    def test_zero_frequency_rejected(self):
        with self.assertRaises(InvalidFrequencyError):
            HuffmanTree({"a": 0})

    def test_non_integer_frequency_rejected(self):
        with self.assertRaises(InvalidFrequencyError):
            HuffmanTree({"a": 1.5})

    def test_error_base_class(self):
        for exc in (InvalidFrequencyError, EmptySymbolError,
                    UnknownSymbolError, InvalidBitstreamError):
            self.assertTrue(issubclass(exc, HuffError))
        self.assertTrue(issubclass(HuffError, Exception))

    def test_deterministic_repeat(self):
        tree = self.make()
        self.assertEqual(tree.code_table(), tree.code_table())
        self.assertEqual(tree.encode("ab"), tree.encode("ab"))


if __name__ == "__main__":
    unittest.main()
