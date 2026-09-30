"""kmpmatch 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from kmpmatch.naive import (
    Erro,
    TextError,
    TextTools,
    count,
    is_periodic,
    min_period,
    occurrences,
    occurrences_many,
    prefix_naive,
)


class TestOccurrences(unittest.TestCase):
    def test_overlapping(self):
        self.assertEqual(occurrences("aa", "aaaa"), [0, 1, 2])

    def test_ascending(self):
        self.assertEqual(occurrences("ab", "ababab"), [0, 2, 4])

    def test_no_hit(self):
        self.assertEqual(occurrences("xyz", "abcabc"), [])

    def test_pattern_equal_text(self):
        self.assertEqual(occurrences("abc", "abc"), [0])

    def test_pattern_longer_than_text(self):
        self.assertEqual(occurrences("abcdef", "abc"), [])

    def test_single_char(self):
        self.assertEqual(occurrences("a", "banana"), [1, 3, 5])

    def test_count(self):
        self.assertEqual(count("aa", "aaaa"), 3)

    def test_empty_pattern_rejected(self):
        with self.assertRaises(TextError):
            occurrences("", "abc")

    def test_non_str_pattern_rejected(self):
        with self.assertRaises(TextError):
            occurrences(None, "abc")

    def test_non_str_text_rejected(self):
        with self.assertRaises(TextError):
            occurrences("ab", 7)

    def test_text_error_is_erro(self):
        self.assertTrue(issubclass(TextError, Erro))


class TestOccurrencesMany(unittest.TestCase):
    def test_basic(self):
        got = occurrences_many(["ab", "ba"], "ababab")
        self.assertEqual(got, {"ab": [0, 2, 4], "ba": [1, 3]})

    def test_duplicate_pattern_kept_once(self):
        got = occurrences_many(["a", "a"], "aba")
        self.assertEqual(list(got.keys()), ["a"])
        self.assertEqual(got["a"], [0, 2])

    def test_ascending_keys(self):
        got = occurrences_many(("b", "a"), "abab")
        self.assertEqual(list(got.keys()), ["b", "a"])

    def test_no_hit(self):
        got = occurrences_many(["z"], "abc")
        self.assertEqual(got, {"z": []})

    def test_not_sequence_rejected(self):
        with self.assertRaises(TextError):
            occurrences_many("ab", "abab")

    def test_empty_pattern_rejected(self):
        with self.assertRaises(TextError):
            occurrences_many(["ab", ""], "abab")


class TestPrefixNaive(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(prefix_naive("ababaca"), [0, 0, 1, 2, 3, 0, 1])

    def test_all_equal(self):
        self.assertEqual(prefix_naive("aaaa"), [0, 1, 2, 3])

    def test_none(self):
        self.assertEqual(prefix_naive("abcd"), [0, 0, 0, 0])

    def test_single_char(self):
        self.assertEqual(prefix_naive("a"), [0])

    def test_empty(self):
        self.assertEqual(prefix_naive(""), [])

    def test_non_str_rejected(self):
        with self.assertRaises(TextError):
            prefix_naive(7)


class TestPeriod(unittest.TestCase):
    def test_min_period_whole(self):
        self.assertEqual(min_period("abcabcabc"), 3)

    def test_min_period_none(self):
        self.assertEqual(min_period("abcd"), 4)

    def test_min_period_single(self):
        self.assertEqual(min_period("a"), 1)

    def test_min_period_empty(self):
        self.assertEqual(min_period(""), 0)

    def test_is_periodic(self):
        self.assertTrue(is_periodic("ababab"))
        self.assertFalse(is_periodic("ababc"))

    def test_is_periodic_single_char(self):
        self.assertFalse(is_periodic("a"))

    def test_non_str_rejected(self):
        with self.assertRaises(TextError):
            min_period(7)


class TestTextTools(unittest.TestCase):
    def test_occurrences_matches_plain(self):
        tools = TextTools("ababab")
        self.assertEqual(tools.occurrences("ab"), occurrences("ab", "ababab"))

    def test_count_matches_positions(self):
        tools = TextTools("ababab")
        self.assertEqual(tools.count("ab"), len(tools.occurrences("ab")))

    def test_many_matches_plain(self):
        tools = TextTools("ababab")
        self.assertEqual(
            tools.occurrences_many(["ab", "ba"]),
            occurrences_many(["ab", "ba"], "ababab"),
        )

    def test_prefix_matches_plain(self):
        tools = TextTools("abcabcabc")
        self.assertEqual(tools.prefix_naive("ababaca"), prefix_naive("ababaca"))

    def test_min_period_matches_plain(self):
        tools = TextTools("abcabcabc")
        self.assertEqual(tools.min_period(), min_period("abcabcabc"))

    def test_compare_count_grows_and_resets(self):
        tools = TextTools("abcabcabc")
        tools.reset_compare_count()
        self.assertEqual(tools.compare_count(), 0)
        tools.occurrences("abc")
        after = tools.compare_count()
        self.assertGreater(after, 0)
        tools.reset_compare_count()
        self.assertEqual(tools.compare_count(), 0)
        tools.occurrences("abc")
        self.assertEqual(tools.compare_count(), after)

    def test_two_tools_do_not_share_state(self):
        a = TextTools("ababab")
        b = TextTools("ababab")
        a.occurrences("ab")
        self.assertEqual(b.compare_count(), 0)

    def test_text_accessor(self):
        self.assertEqual(TextTools("hello").text(), "hello")

    def test_non_str_text_rejected(self):
        with self.assertRaises(TextError):
            TextTools(None)


class TestDeterminism(unittest.TestCase):
    def test_repeated_run_same_result(self):
        tools = TextTools("abcabcabc")
        first = (
            tools.occurrences("abc"),
            tools.occurrences_many(["abc", "ca"]),
            tools.prefix_naive("abcabc"),
            tools.min_period(),
        )
        for _ in range(3):
            self.assertEqual(
                (
                    tools.occurrences("abc"),
                    tools.occurrences_many(["abc", "ca"]),
                    tools.prefix_naive("abcabc"),
                    tools.min_period(),
                ),
                first,
            )


if __name__ == "__main__":
    unittest.main()
