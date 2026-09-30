"""FlatVocab 基线行为锁定测试。

锁住改造前的朴素现状: 插入与删除、存在性判定、前缀判定与计数、按前缀取
全部字符串与去重集合、按字典序输出、最长公共前缀、字符比较计数与异常口径。
本文件在改造后一字不许改, 且必须一直全绿。
"""

import unittest

from trievocab.vocab import (
    EmptyError,
    FlatVocab,
    NotFoundError,
    VocabError,
)


def build(words):
    """按给定顺序插入一串单词, 返回基线词表。"""
    v = FlatVocab()
    for w in words:
        v.insert(w)
    return v


def sample():
    return build(["app", "apple", "app", "apricot", "bat", "banana", "band"])


class TestBasics(unittest.TestCase):
    def test_empty(self):
        v = FlatVocab()
        self.assertEqual(len(v), 0)
        self.assertEqual(v.all_words(), [])
        self.assertEqual(v.count_prefix(""), 0)
        self.assertFalse(v.has_prefix("a"))
        self.assertFalse(v.contains("a"))

    def test_insert_keeps_duplicates(self):
        v = build(["app", "apple", "app"])
        self.assertEqual(len(v), 3)
        self.assertEqual(v.count_prefix("app"), 3)

    def test_insert_rejects_non_str(self):
        v = FlatVocab()
        with self.assertRaises(VocabError):
            v.insert(3)
        with self.assertRaises(VocabError):
            v.insert(None)

    def test_empty_string_roundtrip(self):
        v = FlatVocab()
        v.insert("")
        self.assertEqual(len(v), 1)
        self.assertTrue(v.contains(""))
        self.assertTrue(v.has_prefix(""))
        self.assertEqual(v.count_prefix(""), 1)


class TestContains(unittest.TestCase):
    def test_contains_whole_word_only(self):
        v = build(["app", "apple"])
        self.assertTrue(v.contains("app"))
        self.assertTrue(v.contains("apple"))
        self.assertFalse(v.contains("appl"))
        self.assertFalse(v.contains("apples"))

    def test_contains_rejects_non_str(self):
        with self.assertRaises(VocabError):
            sample().contains(7)


class TestPrefixQueries(unittest.TestCase):
    def setUp(self):
        self.v = sample()

    def test_has_prefix(self):
        self.assertTrue(self.v.has_prefix("app"))
        self.assertTrue(self.v.has_prefix("ba"))
        self.assertTrue(self.v.has_prefix(""))
        self.assertFalse(self.v.has_prefix("cat"))
        self.assertFalse(self.v.has_prefix("apples"))

    def test_count_prefix(self):
        self.assertEqual(self.v.count_prefix("app"), 3)
        self.assertEqual(self.v.count_prefix("ap"), 4)
        self.assertEqual(self.v.count_prefix("b"), 3)
        self.assertEqual(self.v.count_prefix(""), 7)
        self.assertEqual(self.v.count_prefix("z"), 0)

    def test_prefix_whole_word_counts_itself(self):
        self.assertEqual(self.v.count_prefix("apple"), 1)
        self.assertTrue(self.v.has_prefix("apple"))

    def test_words_with_prefix_sorted_with_dupes(self):
        self.assertEqual(
            self.v.words_with_prefix("ap"),
            ["app", "app", "apple", "apricot"],
        )
        self.assertEqual(self.v.words_with_prefix("zzz"), [])

    def test_distinct_with_prefix(self):
        self.assertEqual(
            self.v.distinct_with_prefix("ap"),
            ["app", "apple", "apricot"],
        )
        self.assertEqual(self.v.distinct_with_prefix(""), sorted(set(self.v.all_words())))

    def test_words_with_prefix_is_a_copy(self):
        got = self.v.words_with_prefix("ap")
        got.append("junk")
        self.assertEqual(len(self.v), 7)


class TestOrdering(unittest.TestCase):
    def test_all_words_sorted(self):
        v = build(["bat", "app", "banana", "apple", "band", "app", "apricot"])
        self.assertEqual(
            v.all_words(),
            ["app", "app", "apple", "apricot", "banana", "band", "bat"],
        )

    def test_all_words_is_a_copy(self):
        v = build(["b", "a"])
        got = v.all_words()
        got.append("c")
        self.assertEqual(v.all_words(), ["a", "b"])


class TestLongestCommonPrefix(unittest.TestCase):
    def test_empty_raises(self):
        with self.assertRaises(EmptyError):
            FlatVocab().longest_common_prefix()

    def test_single(self):
        self.assertEqual(build(["abc"]).longest_common_prefix(), "abc")

    def test_shared(self):
        self.assertEqual(
            build(["flower", "flow", "flight"]).longest_common_prefix(), "fl"
        )

    def test_all_equal(self):
        self.assertEqual(build(["dog", "dog", "dog"]).longest_common_prefix(), "dog")

    def test_prefix_of_other(self):
        self.assertEqual(build(["ab", "abc"]).longest_common_prefix(), "ab")

    def test_no_common(self):
        self.assertEqual(build(["dog", "cat"]).longest_common_prefix(), "")

    def test_with_empty_string(self):
        self.assertEqual(build(["ab", ""]).longest_common_prefix(), "")


class TestRemove(unittest.TestCase):
    def test_remove_one_of_duplicates(self):
        v = build(["app", "app", "bat"])
        v.remove("app")
        self.assertEqual(len(v), 2)
        self.assertTrue(v.contains("app"))
        self.assertEqual(v.count_prefix("app"), 1)

    def test_remove_absent_raises(self):
        v = build(["app"])
        with self.assertRaises(NotFoundError):
            v.remove("bat")

    def test_remove_rejects_non_str(self):
        v = build(["app"])
        with self.assertRaises(VocabError):
            v.remove(7)

    def test_remove_to_empty(self):
        v = build(["a"])
        v.remove("a")
        self.assertEqual(len(v), 0)
        self.assertEqual(v.all_words(), [])


class TestCompareCount(unittest.TestCase):
    def test_query_scans_whole_table(self):
        v = sample()
        v.reset_compare_count()
        v.count_prefix("app")
        self.assertEqual(v.compare_count, len(v) * len("app"))

    def test_has_prefix_scans_whole_table(self):
        v = sample()
        v.reset_compare_count()
        v.has_prefix("ban")
        self.assertEqual(v.compare_count, len(v) * len("ban"))

    def test_accumulates_and_resets(self):
        v = sample()
        v.reset_compare_count()
        v.contains("app")
        first = v.compare_count
        self.assertGreater(first, 0)
        v.contains("banana")
        self.assertGreater(v.compare_count, first)
        v.reset_compare_count()
        self.assertEqual(v.compare_count, 0)


class TestExceptionHierarchy(unittest.TestCase):
    def test_all_inherit_base(self):
        self.assertTrue(issubclass(EmptyError, VocabError))
        self.assertTrue(issubclass(NotFoundError, VocabError))
        self.assertTrue(issubclass(VocabError, Exception))


class TestDeterminism(unittest.TestCase):
    def test_repeat_same_result(self):
        words = ["banana", "app", "band", "apple", "bat", "app"]
        a = build(words)
        b = build(words)
        self.assertEqual(a.all_words(), b.all_words())
        self.assertEqual(a.count_prefix("app"), b.count_prefix("app"))
        self.assertEqual(a.distinct_with_prefix("ba"), b.distinct_with_prefix("ba"))
        self.assertEqual(a.longest_common_prefix(), b.longest_common_prefix())


if __name__ == "__main__":
    unittest.main()
