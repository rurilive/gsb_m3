"""matchx 基线行为测试：锁住改造前朴素查找的现状。

本文件是基线，改造时一个字不许改，且必须原样全绿。
"""

import unittest

from matchx.search import (
    InvalidPatternError,
    MatchError,
    NaiveSearch,
    find,
    find_all,
    has,
    count,
)


def brute_find_all(text, pat):
    """独立的暴力参照实现：逐位比对，收集全部出现（含重叠）。"""
    n, m = len(text), len(pat)
    hits = []
    for start in range(n - m + 1):
        if text[start:start + m] == pat:
            hits.append(start)
    return hits


class TestFind(unittest.TestCase):
    def test_find_first_hit(self):
        self.assertEqual(find("abcabc", "abc"), 0)
        self.assertEqual(find("xxabcxx", "abc"), 2)

    def test_find_miss_returns_minus_one(self):
        self.assertEqual(find("abcdef", "xyz"), -1)
        self.assertEqual(find("aaa", "aaaa"), -1)

    def test_find_includes_last_aligned_position(self):
        self.assertEqual(find("abab", "ab"), 0)
        self.assertEqual(find("baba", "ba"), 0)
        self.assertEqual(find("xyab", "ab"), 2)

    def test_find_pattern_equals_text(self):
        self.assertEqual(find("exact", "exact"), 0)

    def test_find_single_chars(self):
        self.assertEqual(find("", "a"), -1)
        self.assertEqual(find("a", "a"), 0)


class TestFindAll(unittest.TestCase):
    def test_overlapping_hits(self):
        self.assertEqual(find_all("aaaa", "aa"), [0, 1, 2])
        self.assertEqual(find_all("aaaa", "a"), [0, 1, 2, 3])

    def test_no_hit(self):
        self.assertEqual(find_all("abcdef", "gh"), [])

    def test_ascending_order(self):
        self.assertEqual(find_all("ababab", "ab"), [0, 2, 4])

    def test_every_hit_matches_pattern(self):
        text = "abcabcabc"
        pat = "abc"
        for pos in find_all(text, pat):
            self.assertEqual(text[pos:pos + len(pat)], pat)

    def test_agrees_with_brute_force(self):
        cases = [
            ("aaaaa", "aa"),
            ("abababab", "aba"),
            ("abcabcabc", "abc"),
            ("zzz", "z"),
            ("hello world", "o"),
            ("mississippi", "issi"),
        ]
        for text, pat in cases:
            with self.subTest(text=text, pat=pat):
                self.assertEqual(find_all(text, pat), brute_find_all(text, pat))


class TestHas(unittest.TestCase):
    def test_has_true_false(self):
        self.assertTrue(has("hello", "ell"))
        self.assertFalse(has("hello", "xyz"))

    def test_has_matches_find(self):
        for text, pat in [("abc", "c"), ("abc", "d"), ("", "a")]:
            with self.subTest(text=text, pat=pat):
                self.assertEqual(has(text, pat), find(text, pat) != -1)


class TestCount(unittest.TestCase):
    def test_count_overlapping(self):
        self.assertEqual(count("aaaa", "aa"), 3)
        self.assertEqual(count("aaaa", "a"), 4)

    def test_count_miss(self):
        self.assertEqual(count("abc", "z"), 0)

    def test_count_equals_len_find_all(self):
        for text, pat in [("ababab", "ab"), ("aaaa", "aaa"), ("abc", "abc")]:
            with self.subTest(text=text, pat=pat):
                self.assertEqual(count(text, pat), len(find_all(text, pat)))


class TestInvalidPattern(unittest.TestCase):
    def test_empty_pattern_raises_value_error(self):
        for meth in (find, find_all, has, count):
            with self.subTest(meth=meth.__name__):
                with self.assertRaises(ValueError):
                    meth("abc", "")

    def test_empty_pattern_is_match_error(self):
        with self.assertRaises(MatchError):
            find("abc", "")

    def test_invalid_pattern_error_is_both(self):
        self.assertTrue(issubclass(InvalidPatternError, MatchError))
        self.assertTrue(issubclass(InvalidPatternError, ValueError))


class TestNaiveComparisonCounter(unittest.TestCase):
    def test_comparisons_positive_on_hit(self):
        s = NaiveSearch()
        s.find("abcabc", "abc")
        self.assertGreater(s.comparisons, 0)

    def test_degenerate_quadratic_blowup(self):
        # 全是同一字符、且模式几乎与文本等长，朴素比对会大量重复比较。
        text = "a" * 50
        pat = "a" * 20 + "b"
        s = NaiveSearch()
        s.find(text, pat)
        # 每个起点都会逐位比较到模式的最后一个字符才失败，比较次数远超文本长度。
        self.assertGreater(s.comparisons, len(text))


class TestDeterminism(unittest.TestCase):
    def test_repeated_calls_agree(self):
        args = ("abababab", "aba")
        self.assertEqual(find(*args), find(*args))
        self.assertEqual(find_all(*args), find_all(*args))

    def test_module_functions_stateless(self):
        # 反复调用不依赖模块级可变状态，结果稳定。
        results = [find_all("aaaa", "aa") for _ in range(5)]
        for r in results:
            self.assertEqual(r, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
