"""FuzzyIndex 现有行为的锁定测试。"""

import unittest

from fuzzyidx.index import FuzzyIndex


def sample():
    idx = FuzzyIndex()
    idx.add_doc(1, ["apple", "apply", "ape"])
    idx.add_doc(2, ["banana", "band"])
    return idx


class TestDocRegistry(unittest.TestCase):
    def test_add_doc_returns_term_count(self):
        idx = FuzzyIndex()
        self.assertEqual(idx.add_doc(1, ["a", "b", "c"]), 3)

    def test_add_doc_dedupes_terms(self):
        idx = FuzzyIndex()
        self.assertEqual(idx.add_doc(1, ["a", "a", "b"]), 2)

    def test_doc_count(self):
        self.assertEqual(sample().doc_count(), 2)

    def test_term_count(self):
        self.assertEqual(sample().term_count(), 5)

    def test_terms_sorted(self):
        self.assertEqual(sample().terms(), ["ape", "apple", "apply", "banana", "band"])

    def test_doc_terms_sorted(self):
        idx = FuzzyIndex()
        idx.add_doc(1, ["pear", "apple", "fig"])
        self.assertEqual(idx.doc_terms(1), ["apple", "fig", "pear"])

    def test_doc_terms_unknown_doc_is_empty(self):
        self.assertEqual(sample().doc_terms(99), [])


class TestDocOverwrite(unittest.TestCase):
    def test_readd_replaces_old_terms(self):
        idx = FuzzyIndex()
        idx.add_doc(1, ["old", "stale"])
        idx.add_doc(1, ["fresh"])
        self.assertEqual(idx.doc_terms(1), ["fresh"])
        self.assertEqual(idx.docs_for("old"), set())
        self.assertEqual(idx.docs_for("stale"), set())

    def test_readd_keeps_doc_count(self):
        idx = FuzzyIndex()
        idx.add_doc(1, ["old"])
        idx.add_doc(1, ["fresh"])
        self.assertEqual(idx.doc_count(), 1)


class TestRemoveDoc(unittest.TestCase):
    def test_remove_returns_true_then_false(self):
        idx = sample()
        self.assertTrue(idx.remove_doc(1))
        self.assertFalse(idx.remove_doc(1))

    def test_remove_prunes_postings(self):
        idx = sample()
        idx.remove_doc(2)
        self.assertNotIn("banana", idx.terms())
        self.assertEqual(idx.term_count(), 3)

    def test_remove_prunes_shared_term(self):
        idx = FuzzyIndex()
        idx.add_doc(1, ["apple"])
        idx.add_doc(2, ["apple"])
        idx.remove_doc(1)
        self.assertEqual(idx.docs_for("apple"), {2})
        idx.remove_doc(2)
        self.assertNotIn("apple", idx.terms())


class TestExactMatch(unittest.TestCase):
    def test_docs_for_exact(self):
        self.assertEqual(sample().docs_for("apple"), {1})

    def test_docs_for_shared_term(self):
        idx = FuzzyIndex()
        idx.add_doc(1, ["apple"])
        idx.add_doc(2, ["apple"])
        self.assertEqual(idx.docs_for("apple"), {1, 2})

    def test_docs_for_not_a_word_boundary(self):
        # 当前只做整词匹配，app 不是任何已登记的词
        self.assertEqual(sample().docs_for("app"), set())

    def test_docs_for_miss_is_empty(self):
        self.assertEqual(sample().docs_for("zzz"), set())

    def test_docs_for_returns_private_copy(self):
        idx = sample()
        hit = idx.docs_for("apple")
        hit.add(999)
        self.assertEqual(idx.docs_for("apple"), {1})

    def test_docs_for_scans_whole_term_table(self):
        idx = sample()
        idx.reset_access_count()
        idx.docs_for("banana")
        self.assertEqual(idx.access_count, idx.term_count())

    def test_access_count_accumulates_and_resets(self):
        idx = sample()
        idx.reset_access_count()
        idx.docs_for("apple")
        idx.docs_for("banana")
        self.assertEqual(idx.access_count, 2 * idx.term_count())
        idx.reset_access_count()
        self.assertEqual(idx.access_count, 0)


if __name__ == "__main__":
    unittest.main()
