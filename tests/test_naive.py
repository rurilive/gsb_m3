"""zstr 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from zstr.naive import (
    Erro,
    TextError,
    TextTools,
    min_period,
    occurrences,
    z_array,
)


class TestZArray(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(z_array("aabcaab"), [0, 1, 0, 0, 3, 1, 0])

    def test_single_char(self):
        self.assertEqual(z_array("a"), [0])

    def test_empty(self):
        self.assertEqual(z_array(""), [])

    def test_all_equal(self):
        self.assertEqual(z_array("aaaa"), [0, 3, 2, 1])

    def test_no_prefix_match(self):
        self.assertEqual(z_array("abcd"), [0, 0, 0, 0])

    def test_non_str_rejected(self):
        with self.assertRaises(TextError):
            z_array(7)


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
        tools = TextTools("ababab")
        self.assertTrue(tools.is_periodic())
        self.assertFalse(TextTools("ababc").is_periodic())

    def test_is_periodic_single_char(self):
        self.assertFalse(TextTools("a").is_periodic())


class TestTextTools(unittest.TestCase):
    def test_z_array_matches_plain(self):
        tools = TextTools("aabcaab")
        self.assertEqual(tools.z_array(), z_array("aabcaab"))

    def test_occurrences_matches_plain(self):
        tools = TextTools("ababab")
        self.assertEqual(tools.occurrences("ab"), occurrences("ab", "ababab"))

    def test_count_matches_positions(self):
        tools = TextTools("ababab")
        self.assertEqual(tools.count("ab"), len(tools.occurrences("ab")))

    def test_compare_count_grows_and_resets(self):
        tools = TextTools("abcabcabc")
        tools.reset_compare_count()
        self.assertEqual(tools.compare_count(), 0)
        tools.z_array()
        after = tools.compare_count()
        self.assertGreater(after, 0)
        tools.reset_compare_count()
        self.assertEqual(tools.compare_count(), 0)
        tools.z_array()
        self.assertEqual(tools.compare_count(), after)

    def test_two_tools_do_not_share_state(self):
        a = TextTools("ababab")
        b = TextTools("ababab")
        a.z_array()
        self.assertEqual(b.compare_count(), 0)

    def test_text_accessor(self):
        self.assertEqual(TextTools("hello").text(), "hello")

    def test_non_str_text_rejected(self):
        with self.assertRaises(TextError):
            TextTools(None)


class TestDeterminism(unittest.TestCase):
    def test_repeated_run_same_result(self):
        tools = TextTools("abcabcabc")
        first = (tools.z_array(), tools.occurrences("abc"), tools.min_period())
        for _ in range(3):
            self.assertEqual(
                (tools.z_array(), tools.occurrences("abc"), tools.min_period()),
                first,
            )


if __name__ == "__main__":
    unittest.main()
