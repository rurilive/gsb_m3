"""BmSearch 现有行为的锁定测试（基线，一字不改）。"""

import unittest

from bmsearch.search import BmSearch, InvalidInputError, SearchError


class TestFindOccurrences(unittest.TestCase):
    def test_two_hits(self):
        self.assertEqual(BmSearch("abc").find_occurrences("abcabc"), [0, 3])

    def test_no_hit(self):
        self.assertEqual(BmSearch("abc").find_occurrences("defdef"), [])

    def test_overlapping_hits(self):
        self.assertEqual(BmSearch("aa").find_occurrences("aaaa"), [0, 1, 2])

    def test_hit_at_end(self):
        self.assertEqual(BmSearch("cd").find_occurrences("abcd"), [2])

    def test_single_char_pattern(self):
        self.assertEqual(BmSearch("a").find_occurrences("banana"), [1, 3, 5])

    def test_text_equal_pattern(self):
        self.assertEqual(BmSearch("abc").find_occurrences("abc"), [0])

    def test_pattern_longer_than_text(self):
        self.assertEqual(BmSearch("abcdef").find_occurrences("abc"), [])

    def test_all_same_text(self):
        self.assertEqual(BmSearch("aa").find_occurrences("aaaaaa"), [0, 1, 2, 3, 4])

    def test_repeated_pattern(self):
        self.assertEqual(BmSearch("abab").find_occurrences("abababab"), [0, 2, 4])

    def test_empty_text(self):
        self.assertEqual(BmSearch("abc").find_occurrences(""), [])


class TestCountOccurrences(unittest.TestCase):
    def test_count_two(self):
        self.assertEqual(BmSearch("abc").count_occurrences("abcabc"), 2)

    def test_count_zero(self):
        self.assertEqual(BmSearch("abc").count_occurrences("defdef"), 0)

    def test_count_overlapping(self):
        self.assertEqual(BmSearch("aa").count_occurrences("aaaa"), 3)

    def test_count_all_same(self):
        self.assertEqual(BmSearch("aa").count_occurrences("aaaaaa"), 5)


class TestContains(unittest.TestCase):
    def test_present(self):
        self.assertTrue(BmSearch("abc").contains("abcabc"))

    def test_absent(self):
        self.assertFalse(BmSearch("abc").contains("defdef"))

    def test_single_char(self):
        self.assertTrue(BmSearch("a").contains("bbba"))


class TestMatchSteps(unittest.TestCase):
    def test_per_match_fields(self):
        kit = BmSearch("abc")
        kit.find_occurrences("abcabc")
        steps = kit.match_steps()
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["start"], 0)
        self.assertEqual(steps[0]["jumps"], 0)
        self.assertEqual(steps[0]["comparisons"], 3)
        self.assertEqual(steps[1]["start"], 3)
        self.assertEqual(steps[1]["jumps"], 3)
        self.assertEqual(steps[1]["comparisons"], 3)

    def test_overlapping_jumps(self):
        kit = BmSearch("aa")
        kit.find_occurrences("aaaa")
        steps = kit.match_steps()
        self.assertEqual([e["jumps"] for e in steps], [0, 1, 1])

    def test_no_hit_empty_steps(self):
        kit = BmSearch("abc")
        kit.find_occurrences("defdef")
        self.assertEqual(kit.match_steps(), [])


class TestSteps(unittest.TestCase):
    def test_search_steps_positive(self):
        kit = BmSearch("ab")
        kit.find_occurrences("ababab")
        self.assertGreater(kit.search_steps(), 0)

    def test_search_steps_value(self):
        kit = BmSearch("abc")
        kit.find_occurrences("abcabc")
        self.assertEqual(kit.search_steps(), 8)

    def test_search_jumps_value(self):
        kit = BmSearch("aa")
        kit.find_occurrences("aaaa")
        self.assertEqual(kit.search_jumps(), 2)

    def test_naive_comparisons(self):
        kit = BmSearch("abc")
        self.assertEqual(kit.naive_comparisons("abcabc"), 8)

    def test_steps_repeat_same(self):
        kit = BmSearch("abab")
        kit.find_occurrences("abababab")
        first = kit.search_steps()
        kit.find_occurrences("abababab")
        self.assertEqual(kit.search_steps(), first)


class TestErrors(unittest.TestCase):
    def test_non_string_pattern_rejected(self):
        with self.assertRaises(InvalidInputError):
            BmSearch(123)

    def test_non_string_text_rejected(self):
        with self.assertRaises(InvalidInputError):
            BmSearch("abc").find_occurrences(None)

    def test_empty_pattern_search_rejected(self):
        with self.assertRaises(InvalidInputError):
            BmSearch("").find_occurrences("abc")

    def test_empty_pattern_naive_rejected(self):
        with self.assertRaises(InvalidInputError):
            BmSearch("").naive_comparisons("abc")

    def test_error_base_class(self):
        self.assertTrue(issubclass(InvalidInputError, SearchError))
        self.assertTrue(issubclass(SearchError, Exception))


class TestDeterminism(unittest.TestCase):
    def test_search_repeat_same(self):
        kit = BmSearch("aa")
        self.assertEqual(kit.find_occurrences("aaaa"), kit.find_occurrences("aaaa"))

    def test_naive_comparisons_stable(self):
        kit = BmSearch("abab")
        self.assertEqual(kit.naive_comparisons("abababab"), kit.naive_comparisons("abababab"))

    def test_pattern_unchanged(self):
        kit = BmSearch("abcabc")
        kit.find_occurrences("abcabcabc")
        kit.match_steps()
        kit.search_steps()
        self.assertEqual(kit.pattern(), "abcabc")


if __name__ == "__main__":
    unittest.main()
