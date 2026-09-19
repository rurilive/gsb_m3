"""Trie 现有补全行为的锁定测试。"""

import unittest

from lexicon.trie import Trie


class TestTrie(unittest.TestCase):
    def test_insert_and_complete(self):
        t = Trie()
        t.insert("cat", 10)
        t.insert("car", 5)
        t.insert("dog", 8)
        self.assertEqual(t.complete("ca"), ["cat", "car"])
        self.assertEqual(t.complete("do"), ["dog"])

    def test_complete_sorted_by_freq_desc(self):
        t = Trie()
        t.insert("ab", 1)
        t.insert("aa", 9)
        t.insert("ac", 5)
        self.assertEqual(t.complete("a"), ["aa", "ac", "ab"])

    def test_complete_no_match_returns_empty(self):
        t = Trie()
        t.insert("cat", 3)
        self.assertEqual(t.complete("ze"), [])

    def test_complete_full_word_is_included(self):
        t = Trie()
        t.insert("cat", 3)
        self.assertEqual(t.complete("cat"), ["cat"])

    def test_prefix_itself_not_a_word(self):
        t = Trie()
        t.insert("cart", 4)
        t.insert("car", 2)
        self.assertEqual(t.complete("car"), ["cart", "car"])

    def test_insert_duplicate_updates_freq(self):
        t = Trie()
        t.insert("go", 1)
        t.insert("go", 100)
        t.insert("gold", 50)
        self.assertEqual(t.complete("g"), ["go", "gold"])

    def test_freq_tie_sorted_lexicographically(self):
        t = Trie()
        t.insert("bat", 5)
        t.insert("ban", 5)
        t.insert("bam", 5)
        self.assertEqual(t.complete("ba"), ["bam", "ban", "bat"])

    def test_empty_prefix_returns_all(self):
        t = Trie()
        t.insert("b", 1)
        t.insert("aa", 9)
        t.insert("cc", 5)
        self.assertEqual(t.complete(""), ["aa", "cc", "b"])

    def test_many_words_all_returned_sorted(self):
        t = Trie()
        freqs = {}
        for i in range(50):
            w = "w%02d" % i
            freqs[w] = i
            t.insert(w, i)
        expected = [w for w, _ in sorted(freqs.items(), key=lambda kv: (-kv[1], kv[0]))]
        self.assertEqual(t.complete("w"), expected)

    def test_insert_empty_word_raises(self):
        t = Trie()
        with self.assertRaises(ValueError):
            t.insert("", 3)


if __name__ == "__main__":
    unittest.main()
