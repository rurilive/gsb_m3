"""fuzzy 模糊补全行为测试。

覆盖：k=0 与精确前缀补全严格等价、k 与 k+1 的命中边界、
同距同频按字典序的排序确定性、精确/模糊命中合并去重、
距离口径为 prefix 与候选词任意前缀的最小编辑距离。
"""

import unittest

from lexicon.trie import Trie


def build():
    t = Trie()
    for w, f in [
        ("carry", 90),
        ("carrion", 20),
        ("card", 70),
        ("care", 60),
        ("hello", 100),
        ("help", 80),
        ("helicopter", 10),
        ("world", 95),
    ]:
        t.insert(w, f)
    return t


class TestFuzzyK0Equivalence(unittest.TestCase):
    def test_k0_matches_exact_prefix_completion(self):
        t = build()
        for p in ["", "c", "car", "he", "hello", "ze", "helo", "cary"]:
            self.assertEqual(t.complete(p, fuzzy=0), t.complete(p), p)

    def test_k0_no_match_returns_empty(self):
        t = build()
        self.assertEqual(t.complete("ze", fuzzy=0), [])


class TestFuzzyBoundary(unittest.TestCase):
    def test_distance_exactly_k_hits_k_minus_1_misses(self):
        t = Trie()
        t.insert("abc", 5)
        # lev("axy", "abc") == 2：两次替换
        self.assertEqual(t.complete("axy", fuzzy=1), [])
        self.assertEqual(t.complete("axy", fuzzy=2), ["abc"])

    def test_one_edit_typos_recalled_at_k1(self):
        t = build()
        self.assertEqual(t.complete("helo", fuzzy=1), ["hello", "help", "helicopter"])
        self.assertIn("carry", t.complete("cary", fuzzy=1))
        self.assertEqual(t.complete("helo"), [])
        self.assertEqual(t.complete("cary"), [])

    def test_distance_to_any_prefix_of_candidate(self):
        t = Trie()
        t.insert("helicopter", 10)
        # "hel" 是 "helicopter" 的前缀，lev("helo", "hel") == 1
        self.assertEqual(t.complete("helo", fuzzy=1), ["helicopter"])
        self.assertEqual(t.complete("helo", fuzzy=0), [])


class TestFuzzyOrdering(unittest.TestCase):
    def test_distance_beats_freq(self):
        t = Trie()
        t.insert("cat", 1)    # 距离 0，低频
        t.insert("bat", 100)  # 距离 1，高频
        self.assertEqual(t.complete("cat", fuzzy=1), ["cat", "bat"])

    def test_same_distance_sorted_by_freq_desc(self):
        t = Trie()
        t.insert("bat", 5)
        t.insert("cut", 9)
        self.assertEqual(t.complete("cat", fuzzy=1), ["cut", "bat"])

    def test_same_distance_same_freq_lexicographic(self):
        t = Trie()
        t.insert("car", 5)
        t.insert("bat", 5)
        t.insert("can", 5)
        self.assertEqual(t.complete("cat", fuzzy=1), ["bat", "can", "car"])

    def test_exact_and_fuzzy_hits_merged_without_duplicates(self):
        t = build()
        result = t.complete("car", fuzzy=1)
        self.assertEqual(len(result), len(set(result)))
        # 精确前缀命中距离为 0，排在模糊命中之前
        self.assertEqual(result[:3], ["carry", "card", "care"])
        self.assertIn("carrion", result)


class TestFuzzyValidation(unittest.TestCase):
    def test_negative_or_non_int_fuzzy_raises(self):
        t = build()
        for bad in [-1, 1.5, "1", True]:
            with self.assertRaises(ValueError):
                t.complete("car", fuzzy=bad)


if __name__ == "__main__":
    unittest.main()
