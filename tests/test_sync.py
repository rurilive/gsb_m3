import unittest

from syndigest import FullSync


class ConstructTest(unittest.TestCase):
    def test_initial_items(self):
        s = FullSync({"a": 1, "b": 2})
        self.assertEqual(s.get("a"), 1)
        self.assertEqual(s.get("b"), 2)

    def test_default_empty(self):
        s = FullSync()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.keys(), [])

    def test_initial_items_are_copied(self):
        src = {"a": 1}
        s = FullSync(src)
        src["a"] = 99
        self.assertEqual(s.get("a"), 1)


class AccessTest(unittest.TestCase):
    def test_set_get(self):
        s = FullSync()
        s.set("x", 10)
        self.assertEqual(s.get("x"), 10)

    def test_missing_default(self):
        s = FullSync()
        self.assertIsNone(s.get("nope"))
        self.assertEqual(s.get("nope", 7), 7)

    def test_contains_and_len(self):
        s = FullSync({"a": 1, "b": 2})
        self.assertIn("a", s)
        self.assertNotIn("z", s)
        self.assertEqual(len(s), 2)

    def test_keys_sorted(self):
        s = FullSync({"c": 3, "a": 1, "b": 2})
        self.assertEqual(s.keys(), ["a", "b", "c"])

    def test_items_is_copy(self):
        s = FullSync({"a": 1})
        snap = s.items()
        snap["a"] = 5
        self.assertEqual(s.get("a"), 1)

    def test_snapshot_is_copy(self):
        s = FullSync({"a": 1})
        snap = s.snapshot()
        snap["a"] = 5
        self.assertEqual(s.get("a"), 1)


class SyncTest(unittest.TestCase):
    def test_sync_sends_whole_table(self):
        left = FullSync({"a": 1, "b": 2, "c": 3})
        right = FullSync()
        sent = left.sync_to(right)
        self.assertEqual(sent, 3)
        self.assertEqual(left.sent_entries, 3)
        self.assertEqual(right.snapshot(), {"a": 1, "b": 2, "c": 3})

    def test_receive_overwrites_entirely(self):
        right = FullSync({"x": 9, "y": 8})
        right.receive({"a": 1})
        self.assertEqual(right.snapshot(), {"a": 1})
        self.assertNotIn("x", right)

    def test_sync_counts_accumulate(self):
        left = FullSync({"a": 1})
        right = FullSync()
        left.sync_to(right)
        left.sync_to(right)
        self.assertEqual(left.sent_entries, 2)

    def test_sync_does_not_merge(self):
        left = FullSync({"a": 1})
        right = FullSync({"b": 2})
        left.sync_to(right)
        self.assertIsNone(right.get("b"))
        self.assertEqual(right.snapshot(), {"a": 1})

    def test_repr(self):
        self.assertEqual(repr(FullSync({"a": 1, "b": 2})), "FullSync(2)")


if __name__ == "__main__":
    unittest.main()
