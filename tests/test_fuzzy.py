"""fuzzy 模糊补全行为测试。"""

import unittest

from lexicon.trie import Trie


def make_trie(pairs):
    t = Trie()
    for word, freq in pairs:
        t.insert(word, freq)
    return t


# 与 demo 一致的小词库，便于复现 helo、cary 这类手滑输入
DEMO_WORDS = [
    ("carry", 90),
    ("carrion", 20),
    ("card", 70),
    ("care", 60),
    ("hello", 100),
    ("help", 80),
    ("helicopter", 10),
    ("world", 95),
]


class TestFuzzyK0Equivalence(unittest.TestCase):
    def test_k0_same_as_exact(self):
        t = make_trie(DEMO_WORDS)
        for prefix in ["", "c", "car", "hel", "helo", "world", "zzz"]:
            self.assertEqual(
                t.complete(prefix, fuzzy=0),
                t.complete(prefix),
                prefix,
            )

    def test_default_fuzzy_is_none(self):
        t = make_trie([("cat", 3), ("car", 5)])
        self.assertEqual(t.complete("ca"), t.complete("ca", fuzzy=None))

    def test_k0_exact_word_included_once(self):
        t = make_trie([("cat", 3), ("cats", 1)])
        # cat 既是精确前缀命中，也在模糊遍历中出现，必须去重
        self.assertEqual(t.complete("cat", fuzzy=0), ["cat", "cats"])


class TestFuzzyKToKPlusOneBoundary(unittest.TestCase):
    def setUp(self):
        # abc/abcd 距离 0；ab/abd 距离 1；zab/xab 距离 2
        self.t = make_trie([
            ("abc", 10),
            ("abcd", 9),
            ("ab", 5),
            ("abd", 5),
            ("zab", 8),
            ("xab", 3),
        ])

    def test_k0_only_exact_prefix(self):
        self.assertEqual(self.t.complete("abc", fuzzy=0), ["abc", "abcd"])

    def test_k1_adds_distance_one(self):
        self.assertEqual(
            self.t.complete("abc", fuzzy=1),
            ["abc", "abcd", "ab", "abd"],
        )

    def test_k2_adds_distance_two(self):
        self.assertEqual(
            self.t.complete("abc", fuzzy=2),
            ["abc", "abcd", "ab", "abd", "zab", "xab"],
        )

    def test_boundary_is_not_skipped_for_larger_k(self):
        self.assertEqual(
            self.t.complete("abc", fuzzy=5),
            self.t.complete("abc", fuzzy=2),
        )

    def test_typo_helo_cary_demo_inputs(self):
        t = make_trie(DEMO_WORDS)
        self.assertEqual(t.complete("helo"), [])
        self.assertEqual(
            t.complete("helo", fuzzy=1), ["hello", "help", "helicopter"]
        )
        self.assertEqual(t.complete("cary"), [])
        self.assertEqual(
            t.complete("cary", fuzzy=1),
            ["carry", "card", "care", "carrion"],
        )

    def test_too_large_typo_still_empty(self):
        t = make_trie(DEMO_WORDS)
        # heloxxxx 与任何候选前缀的最小距离都是 4
        self.assertEqual(t.complete("heloxxxx", fuzzy=1), [])


class TestFuzzyOrdering(unittest.TestCase):
    def test_distance_before_freq(self):
        # xb 与 ab 距离 1 但频次很高；ab 精确距离 0 但频次低
        t = make_trie([("xb", 100), ("ab", 1)])
        self.assertEqual(t.complete("ab", fuzzy=1), ["ab", "xb"])

    def test_same_distance_freq_desc(self):
        t = make_trie([("xb", 1), ("ab", 9), ("cb", 5)])
        self.assertEqual(t.complete("ab", fuzzy=1), ["ab", "cb", "xb"])

    def test_same_distance_same_freq_lexicographic(self):
        t = make_trie([("xb", 5), ("ab", 5), ("cb", 5)])
        self.assertEqual(
            t.complete("ab", fuzzy=1), ["ab", "cb", "xb"]
        )

    def test_zero_distance_group_still_freq_desc(self):
        t = make_trie([("abcd", 1), ("ab", 9), ("abce", 5)])
        # 距离全为 0（均以 ab 开头），退回 freq 降序
        self.assertEqual(
            t.complete("ab", fuzzy=1), ["ab", "abce", "abcd"]
        )


class TestFuzzyEditOperations(unittest.TestCase):
    def test_substitution(self):
        t = make_trie([("cat", 1)])
        self.assertEqual(t.complete("hat", fuzzy=1), ["cat"])

    def test_deletion_in_prefix(self):
        # abc -> 候选前缀 ab，删一个字符
        t = make_trie([("ab", 1), ("abz", 1)])
        self.assertEqual(t.complete("abc", fuzzy=1), ["ab", "abz"])

    def test_insertion_in_prefix(self):
        # ac -> ab（插入 b），最小距离 1
        t = make_trie([("abc", 1)])
        self.assertEqual(t.complete("ac", fuzzy=1), ["abc"])
        self.assertEqual(t.complete("ac", fuzzy=0), [])


class TestFuzzyValidation(unittest.TestCase):
    def test_negative_k_raises(self):
        t = Trie()
        with self.assertRaises(ValueError):
            t.complete("a", fuzzy=-1)

    def test_non_integer_k_raises(self):
        t = Trie()
        with self.assertRaises(ValueError):
            t.complete("a", fuzzy="1")
        with self.assertRaises(ValueError):
            t.complete("a", fuzzy=1.0)
        with self.assertRaises(ValueError):
            t.complete("a", fuzzy=True)


if __name__ == "__main__":
    unittest.main()
