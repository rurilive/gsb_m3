"""autocmplt 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from autocmplt.scan import Autocomplete


def build():
    a = Autocomplete()
    a.add("car", 3)
    a.add("cart", 5)
    a.add("carbon", 1)
    a.add("cat", 4)
    a.add("dog", 2)
    return a


class TestAutocomplete(unittest.TestCase):
    def test_add_returns_word(self):
        a = Autocomplete()
        self.assertEqual(a.add("hello"), "hello")

    def test_add_rejects_empty_word(self):
        a = Autocomplete()
        with self.assertRaises(ValueError):
            a.add("")

    def test_add_rejects_non_str_word(self):
        a = Autocomplete()
        with self.assertRaises(ValueError):
            a.add(7)

    def test_add_rejects_bad_count(self):
        a = Autocomplete()
        with self.assertRaises(ValueError):
            a.add("a", -1)
        with self.assertRaises(ValueError):
            a.add("a", "2")
        with self.assertRaises(ValueError):
            a.add("a", True)

    def test_duplicate_add_accumulates(self):
        a = build()
        a.add("car", 2)
        self.assertEqual(a.count_of("car"), 5)

    def test_len_and_contains(self):
        a = build()
        self.assertEqual(len(a), 5)
        self.assertIn("cat", a)
        self.assertNotIn("zebra", a)

    def test_words_insertion_order(self):
        a = build()
        self.assertEqual(a.words(), ("car", "cart", "carbon", "cat", "dog"))

    def test_words_returns_tuple(self):
        a = build()
        self.assertIsInstance(a.words(), tuple)

    def test_count_of_roundtrip(self):
        a = build()
        self.assertEqual(a.count_of("cart"), 5)

    def test_count_of_missing(self):
        a = build()
        with self.assertRaises(KeyError):
            a.count_of("zebra")

    def test_remove_drops_word(self):
        a = build()
        a.remove("cart")
        self.assertEqual(len(a), 4)
        self.assertEqual(a.words(), ("car", "carbon", "cat", "dog"))
        self.assertNotIn("cart", a)
        self.assertEqual(a.candidates("car"), ["car", "carbon"])

    def test_remove_missing_word(self):
        a = build()
        with self.assertRaises(KeyError):
            a.remove("zebra")

    def test_remove_then_readd_allowed(self):
        a = build()
        a.remove("dog")
        a.add("dog", 9)
        self.assertEqual(a.count_of("dog"), 9)

    def test_learn_bumps_count(self):
        a = build()
        self.assertEqual(a.learn("cat"), 5)
        self.assertEqual(a.count_of("cat"), 5)

    def test_learn_missing_word(self):
        a = build()
        with self.assertRaises(KeyError):
            a.learn("zebra")

    def test_candidates_prefix_match(self):
        a = build()
        self.assertEqual(a.candidates("car"), ["cart", "car", "carbon"])

    def test_candidates_hot_first_then_lexical(self):
        a = build()
        a.add("card", 5)
        self.assertEqual(a.candidates("car"), ["card", "cart", "car", "carbon"])

    def test_candidates_include_exact_prefix_word(self):
        a = build()
        self.assertEqual(a.candidates("cat"), ["cat"])

    def test_candidates_no_hit_is_empty(self):
        a = build()
        self.assertEqual(a.candidates("zebra"), [])

    def test_candidates_empty_prefix_is_all(self):
        a = build()
        self.assertEqual(a.candidates(""), ["cart", "cat", "car", "dog", "carbon"])

    def test_candidates_non_str_prefix_rejected(self):
        a = build()
        with self.assertRaises(ValueError):
            a.candidates(None)

    def test_scans_is_non_negative_int(self):
        a = build()
        a.candidates("car")
        self.assertIsInstance(a.scans(), int)
        self.assertGreaterEqual(a.scans(), 0)


if __name__ == "__main__":
    unittest.main()
