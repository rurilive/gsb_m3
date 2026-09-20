"""SnapLine 现有行为的锁定测试。"""

import unittest

from snapline.chain import SnapLine


class StepClock:
    """每次调用前进 1，保证测试里的快照时刻互不相同。"""

    def __init__(self, start=1000):
        self._now = start

    def __call__(self):
        self._now += 1
        return self._now


def make_store(start=1000):
    return SnapLine(clock=StepClock(start))


class TestSnapLine(unittest.TestCase):
    def test_versions_increase_one_by_one(self):
        s = make_store()
        self.assertEqual(s.snapshot("a", 1), 1)
        self.assertEqual(s.snapshot("a", 2), 2)
        self.assertEqual(s.snapshot("a", 3), 3)

    def test_at_reads_back_state(self):
        s = make_store()
        s.snapshot("a", "one")
        s.snapshot("a", "two")
        self.assertEqual(s.at("a", 1), "one")
        self.assertEqual(s.at("a", 2), "two")

    def test_at_unknown_version_returns_none(self):
        s = make_store()
        s.snapshot("a", "one")
        self.assertIsNone(s.at("a", 99))

    def test_at_unknown_object_returns_none(self):
        s = make_store()
        self.assertIsNone(s.at("nobody", 1))

    def test_latest_returns_newest(self):
        s = make_store()
        s.snapshot("a", "one")
        s.snapshot("a", "two")
        self.assertEqual(s.latest("a"), (2, "two"))

    def test_latest_unknown_object_returns_none(self):
        s = make_store()
        self.assertIsNone(s.latest("nobody"))

    def test_history_lists_versions_in_order(self):
        s = make_store()
        for state in ("one", "two", "three"):
            s.snapshot("a", state)
        self.assertEqual(s.history("a"), [1, 2, 3])

    def test_history_returns_fresh_list(self):
        s = make_store()
        s.snapshot("a", "one")
        got = s.history("a")
        got.append(99)
        self.assertEqual(s.history("a"), [1])

    def test_objects_are_independent(self):
        s = make_store()
        s.snapshot("a", "a1")
        s.snapshot("b", "b1")
        self.assertEqual(s.history("a"), [1])
        self.assertEqual(s.history("b"), [1])
        self.assertEqual(s.at("a", 1), "a1")
        self.assertEqual(s.at("b", 1), "b1")

    def test_delete_removes_version(self):
        s = make_store()
        for state in ("a", "b", "c"):
            s.snapshot("cfg", state)
        self.assertTrue(s.delete("cfg", 2))
        self.assertEqual(s.history("cfg"), [1, 3])
        self.assertIsNone(s.at("cfg", 2))
        self.assertEqual(s.at("cfg", 3), "c")

    def test_delete_unknown_returns_false(self):
        s = make_store()
        s.snapshot("cfg", "a")
        self.assertFalse(s.delete("cfg", 42))
        self.assertFalse(s.delete("nobody", 1))

    def test_delete_newest_moves_latest_back(self):
        s = make_store()
        for state in ("a", "b", "c"):
            s.snapshot("cfg", state)
        s.delete("cfg", 3)
        self.assertEqual(s.latest("cfg"), (2, "b"))
        self.assertEqual(s.at("cfg", 2), "b")

    def test_rollback_moves_latest_back(self):
        s = make_store()
        for state in ("a", "b", "c"):
            s.snapshot("cfg", state)
        s.rollback("cfg", 1)
        self.assertEqual(s.latest("cfg"), (1, "a"))
        self.assertEqual(s.at("cfg", 1), "a")
        self.assertEqual(s.at("cfg", 3), "c")

    def test_rollback_unknown_raises(self):
        s = make_store()
        s.snapshot("cfg", "a")
        with self.assertRaises(KeyError):
            s.rollback("cfg", 9)

    def test_clock_is_injectable(self):
        s = SnapLine(clock=lambda: 42.0)
        s.snapshot("a", "one")
        self.assertEqual(s.at("a", 1), "one")
        self.assertEqual(s.latest("a"), (1, "one"))


if __name__ == "__main__":
    unittest.main()
