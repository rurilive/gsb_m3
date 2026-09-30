"""suflcp 现状行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from suflcp.engine import (
    Erro,
    SuffixArray,
    SuffixError,
    common_prefix_len,
    naive_lcp_array,
    naive_suffix_array,
)


class TestNaiveSuffixArray(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(naive_suffix_array("banana"), [5, 3, 1, 0, 4, 2])

    def test_empty(self):
        self.assertEqual(naive_suffix_array(""), [])

    def test_single_char(self):
        self.assertEqual(naive_suffix_array("a"), [0])

    def test_all_same(self):
        self.assertEqual(naive_suffix_array("aaa"), [2, 1, 0])

    def test_no_repeats(self):
        self.assertEqual(naive_suffix_array("cba"), [2, 1, 0])

    def test_non_str_rejected(self):
        with self.assertRaises(SuffixError):
            naive_suffix_array(12345)


class TestCommonPrefixLen(unittest.TestCase):
    def test_shared_prefix(self):
        self.assertEqual(common_prefix_len("banana", 1, 3), 3)

    def test_no_shared_prefix(self):
        self.assertEqual(common_prefix_len("banana", 0, 5), 0)

    def test_self_is_length_of_suffix(self):
        self.assertEqual(common_prefix_len("banana", 2, 2), 4)

    def test_empty_suffix_at_end(self):
        self.assertEqual(common_prefix_len("abc", 3, 0), 0)

    def test_out_of_range(self):
        with self.assertRaises(SuffixError):
            common_prefix_len("abc", 0, 4)

    def test_negative_index(self):
        with self.assertRaises(SuffixError):
            common_prefix_len("abc", -1, 0)

    def test_bool_index_rejected(self):
        with self.assertRaises(SuffixError):
            common_prefix_len("abc", True, 0)


class TestNaiveLcpArray(unittest.TestCase):
    def test_banana(self):
        self.assertEqual(naive_lcp_array("banana"), [1, 3, 0, 0, 2, 0])

    def test_empty(self):
        self.assertEqual(naive_lcp_array(""), [])

    def test_single_char(self):
        self.assertEqual(naive_lcp_array("a"), [0])

    def test_all_same(self):
        self.assertEqual(naive_lcp_array("aaaa"), [1, 2, 3, 0])

    def test_last_entry_is_zero(self):
        lcp = naive_lcp_array("banana")
        self.assertEqual(lcp[-1], 0)

    def test_non_str_rejected(self):
        with self.assertRaises(SuffixError):
            naive_lcp_array(None)


class TestSuffixArrayFacade(unittest.TestCase):
    def test_suffix_array_and_length(self):
        sa = SuffixArray("banana")
        self.assertEqual(len(sa), 6)
        self.assertEqual(sa.suffix_array(), [5, 3, 1, 0, 4, 2])

    def test_rank_is_inverse(self):
        sa = SuffixArray("banana")
        rank = sa.rank()
        for pos, start in enumerate(sa.suffix_array()):
            self.assertEqual(rank[start], pos)

    def test_lcp_array(self):
        sa = SuffixArray("banana")
        self.assertEqual(sa.lcp_array(), naive_lcp_array("banana"))

    def test_lcp_any_pair(self):
        sa = SuffixArray("banana")
        self.assertEqual(sa.lcp(1, 3), 3)
        self.assertEqual(sa.lcp(0, 2), 0)

    def test_error_base_class(self):
        self.assertTrue(issubclass(SuffixError, Erro))
        self.assertTrue(issubclass(SuffixError, Exception))

    def test_empty_text_facade(self):
        sa = SuffixArray("")
        self.assertEqual(sa.suffix_array(), [])
        self.assertEqual(sa.lcp_array(), [])


if __name__ == "__main__":
    unittest.main()
