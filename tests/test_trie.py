"""WordList 基线测试：锁住改造前的现状行为。"""

import unittest

from pytrie.trie import WordList


class TestWordListBaseline(unittest.TestCase):
    def setUp(self):
        self.wl = WordList()
        for word in ("car", "cart", "care", "cat", "dog", "do"):
            self.wl.insert(word)
        # 重复插入，锁住词频计数
        self.wl.insert("car")

    def test_len_counts_duplicates(self):
        self.assertEqual(len(self.wl), 7)

    def test_insert_returns_running_count(self):
        wl = WordList()
        self.assertEqual(wl.insert("a"), 1)
        self.assertEqual(wl.insert("a"), 2)
        self.assertEqual(wl.insert("b"), 1)

    def test_count(self):
        self.assertEqual(self.wl.count("car"), 2)
        self.assertEqual(self.wl.count("dog"), 1)
        self.assertEqual(self.wl.count("missing"), 0)

    def test_contains(self):
        self.assertTrue(self.wl.contains("car"))
        self.assertTrue(self.wl.contains("do"))
        self.assertFalse(self.wl.contains("ca"))
        self.assertFalse(self.wl.contains(""))
        self.assertIn("dog", self.wl)

    def test_starts_with(self):
        self.assertTrue(self.wl.starts_with("ca"))
        self.assertTrue(self.wl.starts_with("car"))
        self.assertTrue(self.wl.starts_with(""))
        self.assertFalse(self.wl.starts_with("z"))

    def test_words_with_prefix_preserves_insertion_order(self):
        self.assertEqual(
            self.wl.words_with_prefix("car"), ["car", "cart", "care", "car"]
        )

    def test_words_with_prefix_empty_returns_all(self):
        self.assertEqual(
            self.wl.words_with_prefix(""),
            ["car", "cart", "care", "cat", "dog", "do", "car"],
        )

    def test_remove_decrements_and_drops_one_copy(self):
        self.assertTrue(self.wl.remove("car"))
        self.assertEqual(self.wl.count("car"), 1)
        self.assertEqual(self.wl.words_with_prefix("car"), ["cart", "care", "car"])
        self.assertTrue(self.wl.remove("car"))
        self.assertEqual(self.wl.count("car"), 0)
        self.assertFalse(self.wl.contains("car"))

    def test_remove_absent_word(self):
        self.assertFalse(self.wl.remove("missing"))
        self.assertFalse(self.wl.remove("ca"))
        self.assertEqual(len(self.wl), 7)

    def test_remove_below_zero_is_rejected(self):
        wl = WordList()
        wl.insert("x")
        self.assertTrue(wl.remove("x"))
        self.assertFalse(wl.remove("x"))
        self.assertEqual(wl.count("x"), 0)


if __name__ == "__main__":
    unittest.main()
