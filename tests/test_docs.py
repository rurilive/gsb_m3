"""锁定 LinearDocs 基线行为的测试。改造时本文件一字不许改。"""

import unittest

from indexly import LinearDocs


class TestLinearDocs(unittest.TestCase):

    def setUp(self):
        self.docs = LinearDocs()
        self.docs.add("a", "the quick brown fox")
        self.docs.add("b", "quick quick brown bear")
        self.docs.add("c", "lazy dogs sleep")

    def test_add_keeps_order(self):
        self.assertEqual(self.docs.doc_ids(), ["a", "b", "c"])

    def test_duplicate_doc_id_rejected(self):
        with self.assertRaises(ValueError):
            self.docs.add("a", "another")

    def test_bad_doc_id_rejected(self):
        with self.assertRaises(ValueError):
            self.docs.add("", "x")
        with self.assertRaises(ValueError):
            self.docs.add(3, "x")

    def test_bad_text_rejected(self):
        with self.assertRaises(ValueError):
            self.docs.add("d", 12)

    def test_text_roundtrip(self):
        self.assertEqual(self.docs.text("a"), "the quick brown fox")
        with self.assertRaises(ValueError):
            self.docs.text("zzz")

    def test_search_word_hits_in_order(self):
        self.assertEqual(self.docs.search("quick"), ["a", "b"])
        self.assertEqual(self.docs.search("brown"), ["a", "b"])
        self.assertEqual(self.docs.search("dogs"), ["c"])
        self.assertEqual(self.docs.search("zebra"), [])

    def test_search_is_token_exact(self):
        # 查询词按整词匹配，子串不算命中。
        self.assertEqual(self.docs.search("qui"), [])

    def test_search_bad_word_rejected(self):
        with self.assertRaises(ValueError):
            self.docs.search("")
        with self.assertRaises(ValueError):
            self.docs.search(7)

    def test_count(self):
        self.assertEqual(self.docs.count("quick"), 3)
        self.assertEqual(self.docs.count("brown"), 2)
        self.assertEqual(self.docs.count("zebra"), 0)

    def test_remove(self):
        self.docs.remove("b")
        self.assertEqual(self.docs.doc_ids(), ["a", "c"])
        self.assertEqual(self.docs.search("quick"), ["a"])
        with self.assertRaises(ValueError):
            self.docs.remove("b")

    def test_empty(self):
        docs = LinearDocs()
        self.assertEqual(docs.doc_ids(), [])
        self.assertEqual(docs.search("anything"), [])


if __name__ == "__main__":
    unittest.main()
