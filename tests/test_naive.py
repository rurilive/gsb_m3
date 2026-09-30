"""graycode 现有朴素行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from graycode.naive import (
    Erro,
    GrayError,
    GrayTools,
    diff_count,
    gray_index,
    gray_sequence,
    is_gray_sequence,
    subsets_in_bit_order,
    subsets_in_gray_order,
)


class TestGraySequence(unittest.TestCase):
    def test_zero_width(self):
        self.assertEqual(gray_sequence(0), [""])

    def test_one_width(self):
        self.assertEqual(gray_sequence(1), ["0", "1"])

    def test_two_width(self):
        self.assertEqual(gray_sequence(2), ["00", "01", "11", "10"])

    def test_three_width_length(self):
        self.assertEqual(len(gray_sequence(3)), 8)

    def test_three_width_first_and_last(self):
        seq = gray_sequence(3)
        self.assertEqual(seq[0], "000")
        self.assertEqual(seq[-1], "100")

    def test_generated_is_valid(self):
        for width in range(0, 6):
            self.assertTrue(is_gray_sequence(gray_sequence(width)))

    def test_all_codes_present(self):
        seq = gray_sequence(4)
        self.assertEqual(sorted(seq), sorted(
            format(i, "04b") for i in range(16)))

    def test_negative_width_rejected(self):
        with self.assertRaises(GrayError):
            gray_sequence(-1)

    def test_non_int_width_rejected(self):
        with self.assertRaises(GrayError):
            gray_sequence("3")

    def test_bool_width_rejected(self):
        with self.assertRaises(GrayError):
            gray_sequence(True)


class TestValidity(unittest.TestCase):
    def test_valid_sequence(self):
        self.assertTrue(is_gray_sequence(["00", "01", "11", "10"]))

    def test_missing_wrap(self):
        self.assertFalse(is_gray_sequence(["00", "01", "11"]))

    def test_wrap_can_be_relaxed(self):
        self.assertTrue(is_gray_sequence(["00", "01", "11"], wrap=False))

    def test_adjacent_differs_more_than_one(self):
        self.assertFalse(is_gray_sequence(["00", "11", "10", "01"]))

    def test_repeated_code_rejected(self):
        self.assertFalse(is_gray_sequence(["00", "00", "01", "11"], wrap=False))

    def test_single_element_ok(self):
        self.assertTrue(is_gray_sequence(["0"]))

    def test_extra_element_same_width_may_break(self):
        self.assertFalse(is_gray_sequence(["00", "01", "11", "10", "10"]))

    def test_unequal_width_rejected(self):
        with self.assertRaises(GrayError):
            is_gray_sequence(["00", "1"])

    def test_empty_sequence_rejected(self):
        with self.assertRaises(GrayError):
            is_gray_sequence([])

    def test_bad_symbol_rejected(self):
        with self.assertRaises(GrayError):
            is_gray_sequence(["0x"])

    def test_non_sequence_rejected(self):
        with self.assertRaises(GrayError):
            is_gray_sequence("0011")


class TestDiffAndIndex(unittest.TestCase):
    def test_diff_count(self):
        self.assertEqual(diff_count("0000", "1000"), 1)
        self.assertEqual(diff_count("0000", "1111"), 4)
        self.assertEqual(diff_count("0000", "0000"), 0)

    def test_diff_mismatched_width(self):
        with self.assertRaises(GrayError):
            diff_count("00", "000")

    def test_gray_index(self):
        self.assertEqual(gray_index("000"), 0)
        self.assertEqual(gray_index("001"), 1)
        self.assertEqual(gray_index("011"), 2)
        self.assertEqual(gray_index("010"), 3)
        self.assertEqual(gray_index("110"), 4)
        self.assertEqual(gray_index("100"), 7)

    def test_gray_index_empty(self):
        self.assertEqual(gray_index(""), 0)

    def test_gray_index_bad_bits(self):
        with self.assertRaises(GrayError):
            gray_index(10)


class TestSubsets(unittest.TestCase):
    def test_bit_order_contains_all(self):
        got = subsets_in_bit_order(["a", "b"])
        self.assertEqual(got, [[], ["b"], ["a"], ["a", "b"]])

    def test_bit_order_empty(self):
        self.assertEqual(subsets_in_bit_order([]), [[]])

    def test_gray_order_subsets_match_bit_order(self):
        items = ["a", "b", "c"]
        gray, _ = subsets_in_gray_order(items)
        self.assertEqual(
            sorted(gray), sorted(subsets_in_bit_order(items)))

    def test_gray_order_steps(self):
        gray, steps = subsets_in_gray_order(["a", "b"])
        self.assertEqual(gray, [[], ["b"], ["a", "b"], ["a"]])
        self.assertEqual(steps, [(1, "add"), (0, "add"), (1, "remove")])

    def test_gray_order_steps_unique_and_one(self):
        items = list("abcd")
        gray, steps = subsets_in_gray_order(items)
        self.assertEqual(len(steps), len(items) and (1 << len(items)) - 1)
        previous = gray[-1]
        for i in range(1, len(gray)):
            set_prev = set(gray[i - 1])
            set_cur = set(gray[i])
            self.assertEqual(len(set_prev ^ set_cur), 1)

    def test_gray_order_single_element(self):
        gray, steps = subsets_in_gray_order(["x"])
        self.assertEqual(gray, [[], ["x"]])
        self.assertEqual(steps, [(0, "add")])


class TestGrayTools(unittest.TestCase):
    def test_matches_plain(self):
        tools = GrayTools(3)
        self.assertEqual(tools.gray_sequence(), gray_sequence(3))

    def test_index_matches_plain(self):
        tools = GrayTools(4)
        self.assertEqual(tools.gray_index("0110"), gray_index("0110"))

    def test_trial_count_grows_and_resets(self):
        tools = GrayTools(4)
        tools.reset_trial_count()
        self.assertEqual(tools.trial_count(), 0)
        tools.gray_sequence()
        after = tools.trial_count()
        self.assertGreater(after, 0)
        tools.reset_trial_count()
        self.assertEqual(tools.trial_count(), 0)
        tools.gray_sequence()
        self.assertEqual(tools.trial_count(), after)

    def test_two_tools_do_not_share_state(self):
        a = GrayTools(4)
        b = GrayTools(4)
        a.gray_sequence()
        self.assertEqual(b.trial_count(), 0)

    def test_width_accessor(self):
        self.assertEqual(GrayTools(5).width(), 5)

    def test_subsets_in_gray_order(self):
        tools = GrayTools(2)
        gray, steps = tools.subsets_in_gray_order(["a", "b"])
        self.assertEqual(gray, [[], ["b"], ["a", "b"], ["a"]])
        self.assertEqual(steps, [(1, "add"), (0, "add"), (1, "remove")])

    def test_element_count_mismatch_rejected(self):
        with self.assertRaises(GrayError):
            GrayTools(3).subsets_in_gray_order(["a", "b"])

    def test_non_int_width_rejected(self):
        with self.assertRaises(GrayError):
            GrayTools(None)


class TestErrorsAndDeterminism(unittest.TestCase):
    def test_gray_error_is_erro(self):
        self.assertTrue(issubclass(GrayError, Erro))

    def test_repeated_run_same_result(self):
        tools = GrayTools(4)
        first = (tools.gray_sequence(), tools.gray_index("0110"))
        for _ in range(3):
            self.assertEqual(
                (tools.gray_sequence(), tools.gray_index("0110")), first)


if __name__ == "__main__":
    unittest.main()
