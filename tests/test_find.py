"""Baseline tests for multimatch.find.EachPattern.

These tests lock down the current naive per-pattern scanning behaviour.
They must stay green and must not be modified by later feature work.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multimatch.find import (
    EachPattern,
    InvalidPatternError,
    Match,
    MultiMatchError,
)


class PatternCheckTest(unittest.TestCase):
    def test_non_string_pattern_rejected(self):
        with self.assertRaises(InvalidPatternError):
            EachPattern([123])

    def test_empty_pattern_rejected(self):
        with self.assertRaises(InvalidPatternError):
            EachPattern([""])

    def test_empty_pattern_set_allowed(self):
        matcher = EachPattern([])
        self.assertEqual(matcher.patterns(), [])
        self.assertEqual(matcher.find("anything"), [])

    def test_patterns_preserve_registration_order(self):
        matcher = EachPattern(["he", "she", "his"])
        self.assertEqual(matcher.patterns(), ["he", "she", "his"])

    def test_invalid_pattern_error_is_subclass(self):
        self.assertTrue(issubclass(InvalidPatternError, MultiMatchError))


class EachPatternFindTest(unittest.TestCase):
    def test_single_pattern_single_hit(self):
        matcher = EachPattern(["she"])
        self.assertEqual(matcher.find("ushers"), [Match("she", 1, 4)])

    def test_single_pattern_no_hit(self):
        matcher = EachPattern(["xyz"])
        self.assertEqual(matcher.find("ushers"), [])

    def test_overlapping_occurrences_reported(self):
        matcher = EachPattern(["aa"])
        self.assertEqual(
            matcher.find("aaaa"),
            [Match("aa", 0, 2), Match("aa", 1, 3), Match("aa", 2, 4)],
        )

    def test_results_grouped_by_pattern_order(self):
        matcher = EachPattern(["he", "she"])
        self.assertEqual(
            matcher.find("she"),
            [Match("he", 1, 3), Match("she", 0, 3)],
        )

    def test_nested_patterns_all_reported(self):
        matcher = EachPattern(["he", "she", "hers"])
        self.assertEqual(
            matcher.find("ushers"),
            [Match("he", 2, 4), Match("she", 1, 4), Match("hers", 2, 6)],
        )

    def test_no_match_returns_empty(self):
        matcher = EachPattern(["cat", "dog"])
        self.assertEqual(matcher.find("the quick brown fox"), [])

    def test_empty_text(self):
        matcher = EachPattern(["a"])
        self.assertEqual(matcher.find(""), [])

    def test_non_string_text_rejected(self):
        matcher = EachPattern(["a"])
        with self.assertRaises(InvalidPatternError):
            matcher.find(None)


if __name__ == "__main__":
    unittest.main()
