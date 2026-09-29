"""histkit 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from histkit import HistRecorder


class TestHistRecorder(unittest.TestCase):
    def test_initial_state_is_current(self):
        rec = HistRecorder("a")
        self.assertEqual(rec.state, "a")
        self.assertEqual(rec.depth, 1)

    def test_push_becomes_current_and_grows_depth(self):
        rec = HistRecorder("a")
        rec.push("b")
        self.assertEqual(rec.state, "b")
        self.assertEqual(rec.depth, 2)
        rec.push("c")
        self.assertEqual(rec.state, "c")
        self.assertEqual(rec.depth, 3)

    def test_push_returns_state(self):
        rec = HistRecorder("a")
        self.assertEqual(rec.push("x"), "x")
        self.assertEqual(rec.push("y"), "y")

    def test_undo_steps_back_one(self):
        rec = HistRecorder("a")
        rec.push("b")
        rec.push("c")
        self.assertEqual(rec.undo(), "b")
        self.assertEqual(rec.state, "b")
        self.assertEqual(rec.undo(), "a")
        self.assertEqual(rec.state, "a")

    def test_undo_at_initial_state_is_stable(self):
        rec = HistRecorder("only")
        self.assertEqual(rec.undo(), "only")
        self.assertEqual(rec.undo(), "only")
        self.assertEqual(rec.state, "only")
        self.assertEqual(rec.depth, 1)

    def test_recorder_without_initial_uses_none(self):
        rec = HistRecorder()
        self.assertIsNone(rec.state)
        rec.push(1)
        self.assertEqual(rec.undo(), None)
        self.assertIsNone(rec.state)


if __name__ == "__main__":
    unittest.main()
