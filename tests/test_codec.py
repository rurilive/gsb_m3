"""Baseline behaviour tests for the FixedWidth encoder.

This file pins the current fixed-width semantics. It must stay unchanged
and keep passing as the library evolves.
"""

import unittest

from entropack import EntropyError, FixedWidth
from entropack.codec import (
    BitStreamError,
    InvalidAlphabetError,
    SymbolNotFoundError,
)


class FixedWidthConstructionTest(unittest.TestCase):
    def test_width_for_two_symbols(self):
        codec = FixedWidth("ab")
        self.assertEqual(codec.width, 1)

    def test_width_for_four_symbols(self):
        codec = FixedWidth("abcd")
        self.assertEqual(codec.width, 2)

    def test_width_for_five_symbols_rounds_up(self):
        codec = FixedWidth("abcde")
        self.assertEqual(codec.width, 3)

    def test_symbols_returns_index_order(self):
        codec = FixedWidth("abcd")
        self.assertEqual(codec.symbols, ["a", "b", "c", "d"])

    def test_empty_alphabet_rejected(self):
        with self.assertRaises(InvalidAlphabetError):
            FixedWidth("")

    def test_duplicate_alphabet_rejected(self):
        with self.assertRaises(InvalidAlphabetError):
            FixedWidth("aab")

    def test_alphabet_errors_are_entropy_errors(self):
        self.assertTrue(issubclass(InvalidAlphabetError, EntropyError))
        self.assertTrue(issubclass(SymbolNotFoundError, EntropyError))
        self.assertTrue(issubclass(BitStreamError, EntropyError))

    def test_repr_mentions_class_and_width(self):
        codec = FixedWidth("abcd")
        self.assertIn("FixedWidth", repr(codec))
        self.assertIn("width=2", repr(codec))


class FixedWidthEncodeTest(unittest.TestCase):
    def test_encode_packs_one_symbol_per_bit(self):
        codec = FixedWidth("ab")
        self.assertEqual(codec.encode("a"), b"\x00")
        self.assertEqual(codec.encode("b"), b"\x80")

    def test_encode_packs_three_symbols(self):
        codec = FixedWidth("ab")
        self.assertEqual(codec.encode("aba"), b"\x40")

    def test_encode_two_bit_symbols(self):
        codec = FixedWidth("abcd")
        self.assertEqual(codec.encode("abcd"), b"\x1b")

    def test_encode_empty_text_is_empty_bytes(self):
        codec = FixedWidth("abc")
        self.assertEqual(codec.encode(""), b"")

    def test_encode_non_str_rejected(self):
        codec = FixedWidth("abc")
        with self.assertRaises(EntropyError):
            codec.encode(123)

    def test_encode_unknown_symbol_rejected(self):
        codec = FixedWidth("abc")
        with self.assertRaises(SymbolNotFoundError):
            codec.encode("z")

    def test_encode_is_fixed_size_regardless_of_frequency(self):
        codec = FixedWidth("ab")
        self.assertEqual(len(codec.encode("aaaa")), len(codec.encode("abab")))


class FixedWidthDecodeTest(unittest.TestCase):
    def test_round_trip_short(self):
        codec = FixedWidth("abcd")
        data = codec.encode("badc")
        self.assertEqual(codec.decode(data, 4), "badc")

    def test_round_trip_needs_count(self):
        codec = FixedWidth("ab")
        data = codec.encode("a")
        self.assertEqual(codec.decode(data, 1), "a")
        self.assertEqual(codec.decode(data, 8), "a" * 8)

    def test_decode_non_bytes_rejected(self):
        codec = FixedWidth("abc")
        with self.assertRaises(EntropyError):
            codec.decode("not bytes", 3)

    def test_decode_negative_count_rejected(self):
        codec = FixedWidth("abc")
        with self.assertRaises(BitStreamError):
            codec.decode(b"\x00", -1)

    def test_decode_not_enough_bits_rejected(self):
        codec = FixedWidth("abc")
        with self.assertRaises(BitStreamError):
            codec.decode(b"\x00", 100)


if __name__ == "__main__":
    unittest.main()
