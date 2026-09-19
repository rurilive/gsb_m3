"""事务与插入合并的行为测试。"""

import unittest

from editstack.commands import Buffer, Command, DeleteText, InsertText
from editstack.stack import EditStack


class FakeClock:
    """手动推进的单调时钟，返回毫秒。"""

    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, ms):
        self.now += ms


class RecordingCommand(Command):
    """把 do/undo 调用记进 log，用于观察顺序。"""

    def __init__(self, log, name):
        self.log = log
        self.name = name

    def do(self):
        self.log.append(("do", self.name))

    def undo(self):
        self.log.append(("undo", self.name))


def insert(stack, buf, pos, text):
    stack.execute(InsertText(buf, pos, text))


class TestTransaction(unittest.TestCase):
    def test_commit_batches_into_one_history_entry(self):
        buf = Buffer("doc", "ab")
        stack = EditStack()
        stack.begin()
        insert(stack, buf, 2, "cd")
        stack.execute(DeleteText(buf, 0, 1))
        insert(stack, buf, 3, "!")
        self.assertEqual(buf.text, "bcd!")
        stack.commit()
        stack.undo()
        self.assertEqual(buf.text, "ab")
        self.assertFalse(stack.can_undo)

    def test_commit_empty_transaction_adds_no_history(self):
        stack = EditStack()
        stack.begin()
        stack.commit()
        self.assertFalse(stack.can_undo)

    def test_redo_reapplies_whole_batch(self):
        buf = Buffer("doc", "")
        stack = EditStack()
        stack.begin()
        insert(stack, buf, 0, "x")
        insert(stack, buf, 1, "y")
        stack.commit()
        stack.undo()
        stack.redo()
        self.assertEqual(buf.text, "xy")

    def test_rollback_reverts_in_reverse_order(self):
        log = []
        buf = Buffer("doc", "")
        stack = EditStack()
        stack.begin()
        stack.execute(RecordingCommand(log, "a"))
        insert(stack, buf, 0, "x")
        stack.execute(RecordingCommand(log, "b"))
        stack.rollback()
        self.assertEqual(log, [
            ("do", "a"), ("do", "b"),
            ("undo", "b"), ("undo", "a"),
        ])
        self.assertEqual(buf.text, "")
        self.assertFalse(stack.can_undo)
        self.assertFalse(stack.can_redo)

    def test_execute_inside_transaction_truncates_redo(self):
        buf = Buffer("doc", "s")
        stack = EditStack()
        insert(stack, buf, 1, "A")
        stack.undo()
        self.assertTrue(stack.can_redo)
        stack.begin()
        insert(stack, buf, 1, "B")
        stack.commit()
        self.assertFalse(stack.can_redo)
        self.assertEqual(buf.text, "sB")

    def test_nested_begin_raises(self):
        stack = EditStack()
        stack.begin()
        with self.assertRaises(RuntimeError):
            stack.begin()
        stack.rollback()

    def test_commit_without_transaction_raises(self):
        with self.assertRaises(RuntimeError):
            EditStack().commit()

    def test_rollback_without_transaction_raises(self):
        with self.assertRaises(RuntimeError):
            EditStack().rollback()

    def test_undo_redo_inside_transaction_raise(self):
        buf = Buffer("doc", "")
        stack = EditStack()
        stack.begin()
        insert(stack, buf, 0, "x")
        with self.assertRaises(RuntimeError):
            stack.undo()
        with self.assertRaises(RuntimeError):
            stack.redo()
        stack.rollback()
        self.assertEqual(buf.text, "")

    def test_main_stack_untouched_until_commit(self):
        buf = Buffer("doc", "a")
        stack = EditStack()
        insert(stack, buf, 1, "b")
        stack.begin()
        insert(stack, buf, 2, "c")
        self.assertEqual(buf.text, "abc")
        stack.rollback()
        stack.undo()
        self.assertEqual(buf.text, "a")


class TestCoalesce(unittest.TestCase):
    def make_stack(self, window=500):
        clock = FakeClock()
        return EditStack(coalesce_window_ms=window, clock=clock), clock

    def test_default_window_disables_coalescing(self):
        buf = Buffer("doc", "")
        stack = EditStack()
        insert(stack, buf, 0, "a")
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertEqual(buf.text, "a")

    def test_rapid_typing_merges_into_one_entry(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack()
        for i, ch in enumerate("hello"):
            clock.advance(50)
            insert(stack, buf, i, ch)
        self.assertEqual(buf.text, "hello")
        stack.undo()
        self.assertEqual(buf.text, "")
        self.assertFalse(stack.can_undo)

    def test_window_boundary_inclusive(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack(window=100)
        insert(stack, buf, 0, "a")
        clock.advance(100)
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertEqual(buf.text, "")

    def test_window_expired_starts_new_entry(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack(window=100)
        insert(stack, buf, 0, "a")
        clock.advance(101)
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertEqual(buf.text, "a")

    def test_different_key_does_not_merge(self):
        a, b = Buffer("a", ""), Buffer("b", "")
        stack, _ = self.make_stack()
        insert(stack, a, 0, "x")
        insert(stack, b, 0, "y")
        stack.undo()
        self.assertEqual(a.text, "x")
        self.assertEqual(b.text, "")

    def test_non_adjacent_position_does_not_merge(self):
        buf = Buffer("doc", "----")
        stack, _ = self.make_stack()
        insert(stack, buf, 0, "a")
        insert(stack, buf, 3, "b")
        self.assertEqual(buf.text, "a--b--")
        stack.undo()
        self.assertEqual(buf.text, "a----")

    def test_non_insert_command_breaks_chain(self):
        buf = Buffer("doc", "ab")
        stack, _ = self.make_stack()
        insert(stack, buf, 2, "c")
        stack.execute(DeleteText(buf, 0, 1))
        insert(stack, buf, 2, "d")
        self.assertEqual(buf.text, "bcd")
        stack.undo()
        self.assertEqual(buf.text, "bc")

    def test_merged_entry_redoes_whole_text(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack()
        insert(stack, buf, 0, "a")
        clock.advance(10)
        insert(stack, buf, 1, "b")
        stack.undo()
        stack.redo()
        self.assertEqual(buf.text, "ab")

    def test_undo_between_inserts_breaks_chain(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack()
        insert(stack, buf, 0, "a")
        stack.undo()
        clock.advance(10)
        insert(stack, buf, 0, "b")
        stack.undo()
        self.assertEqual(buf.text, "")

    def test_new_edit_after_undo_still_truncates_redo(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack()
        insert(stack, buf, 0, "a")
        clock.advance(10)
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertTrue(stack.can_redo)
        insert(stack, buf, 0, "z")
        self.assertFalse(stack.can_redo)
        self.assertEqual(buf.text, "z")


if __name__ == "__main__":
    unittest.main()
