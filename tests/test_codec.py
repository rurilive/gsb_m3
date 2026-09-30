"""HuffmanCodec 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from huffman import (
    EmptySymbolError,
    Erro,
    HuffmanCodec,
    InvalidBitstreamError,
    InvalidWeightError,
    NaiveIndexHeap,
    UnknownSymbolError,
    build_frequency,
    weighted_path_length,
)

WEIGHTS = {"a": 5, "b": 2, "c": 1, "d": 1}


class BuildFrequencyTest(unittest.TestCase):
    def test_counts_each_symbol(self):
        self.assertEqual(build_frequency("aab"), {"a": 2, "b": 1})

    def test_empty_text_is_empty_mapping(self):
        self.assertEqual(build_frequency(""), {})


class HuffmanCodecTest(unittest.TestCase):
    def make(self):
        return HuffmanCodec(dict(WEIGHTS))

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

    def test_module_level_weighted_path_length(self):
        self.assertEqual(weighted_path_length(dict(WEIGHTS)), 15)

    def test_average_length(self):
        self.assertAlmostEqual(self.make().average_length(), 15 / 9)

    def test_rescan_count_counts_two_scans_per_merge(self):
        self.assertEqual(self.make().rescan_count(), 6)

    def test_rescan_count_grows_linearly_in_symbols(self):
        for n in (2, 3, 5, 8):
            weights = {chr(ord("a") + i): 1 for i in range(n)}
            self.assertEqual(HuffmanCodec(weights).rescan_count(), 2 * (n - 1))

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
            self.make().decode("10")


class SingleSymbolTest(unittest.TestCase):
    def test_single_symbol_uses_zero_code(self):
        tree = HuffmanCodec({"x": 4})
        self.assertEqual(tree.codes(), {"x": "0"})
        self.assertEqual(tree.encode("xxx"), "000")
        self.assertEqual(tree.decode("000"), "xxx")
        self.assertEqual(tree.rescan_count(), 0)

    def test_single_symbol_rejects_one_bit(self):
        with self.assertRaises(InvalidBitstreamError):
            HuffmanCodec({"x": 4}).decode("1")


class EqualWeightTest(unittest.TestCase):
    def test_equal_frequencies_are_deterministic(self):
        first = HuffmanCodec({"a": 1, "b": 1, "c": 1, "d": 1})
        second = HuffmanCodec({"a": 1, "b": 1, "c": 1, "d": 1})
        self.assertEqual(first.codes(), second.codes())

    def test_four_equal_make_balanced_two_bit_codes(self):
        tree = HuffmanCodec({"a": 1, "b": 1, "c": 1, "d": 1})
        self.assertEqual(tree.codes(), {"a": "00", "b": "01", "c": "10", "d": "11"})
        self.assertEqual(tree.weighted_path_length(), 8)


class WeightValidationTest(unittest.TestCase):
    def test_zero_weight_is_allowed(self):
        tree = HuffmanCodec({"a": 0, "b": 1})
        self.assertEqual(tree.weighted_path_length(), 1)
        self.assertEqual(tree.encode("b"), "1")

    def test_empty_weight_rejected(self):
        with self.assertRaises(EmptySymbolError):
            HuffmanCodec({})

    def test_negative_weight_rejected(self):
        with self.assertRaises(InvalidWeightError):
            HuffmanCodec({"a": -1})

    def test_non_integer_weight_rejected(self):
        with self.assertRaises(InvalidWeightError):
            HuffmanCodec({"a": 1.5})

    def test_bool_weight_rejected(self):
        with self.assertRaises(InvalidWeightError):
            HuffmanCodec({"a": True})

    def test_non_mapping_rejected(self):
        with self.assertRaises(InvalidWeightError):
            HuffmanCodec([("a", 1)])

    def test_error_base_class(self):
        for exc in (InvalidWeightError, EmptySymbolError,
                    UnknownSymbolError, InvalidBitstreamError):
            self.assertTrue(issubclass(exc, Erro))
        self.assertTrue(issubclass(Erro, Exception))


class NaiveIndexHeapTest(unittest.TestCase):
    def test_pop_is_stable_minimum(self):
        heap = NaiveIndexHeap()
        for item in [(2, 0), (1, 1), (2, 2), (1, 3)]:
            heap.push(item)
        self.assertEqual(len(heap), 4)
        self.assertEqual(heap.pop(), (1, 1))
        self.assertEqual(heap.pop(), (1, 3))
        self.assertEqual(heap.peek(), (2, 0))
        self.assertEqual(heap.pop(), (2, 0))
        self.assertEqual(heap.pop(), (2, 2))

    def test_empty_heap_pop_rejected(self):
        with self.assertRaises(IndexError):
            NaiveIndexHeap().pop()


if __name__ == "__main__":
    unittest.main()
