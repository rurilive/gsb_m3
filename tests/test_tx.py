"""事务（begin/commit/rollback）与插入合并（coalesce）的行为测试。"""

import unittest

from editstack.commands import Buffer, Command, DeleteText, InsertText
from editstack.stack import EditStack


class FakeClock:
    """以毫秒为单位、可手动推进的单调时钟。"""

    def __init__(self):
        self.now = 0

    def __call__(self):
        return self.now

    def advance(self, ms):
        self.now += ms


class RecordingCommand(Command):
    """记录 do/undo 调用顺序的探针命令。"""

    def __init__(self, name, log, key="probe"):
        self.name = name
        self.log = log
        self.key = key

    def do(self):
        self.log.append(("do", self.name))

    def undo(self):
        self.log.append(("undo", self.name))


def insert(stack, buf, pos, text):
    cmd = InsertText(buf, pos, text)
    stack.execute(cmd)
    return cmd


class TestTransaction(unittest.TestCase):
    def test_execute_in_tx_applies_but_stays_off_main_stack(self):
        buf = Buffer("doc", "ab")
        stack = EditStack()
        stack.begin()
        self.assertTrue(stack.in_transaction)
        insert(stack, buf, 2, "cd")
        self.assertEqual(buf.text, "abcd")
        self.assertFalse(stack.can_undo)

    def test_commit_batches_as_single_history_entry(self):
        buf = Buffer("doc", "")
        stack = EditStack()
        stack.begin()
        insert(stack, buf, 0, "a")
        insert(stack, buf, 1, "b")
        insert(stack, buf, 2, "c")
        stack.commit()
        self.assertFalse(stack.in_transaction)
        self.assertEqual(buf.text, "abc")
        stack.undo()
        self.assertEqual(buf.text, "")
        self.assertFalse(stack.can_undo)
        stack.redo()
        self.assertEqual(buf.text, "abc")

    def test_commit_undoes_in_reverse_order(self):
        log = []
        stack = EditStack()
        stack.begin()
        for name in ("x", "y", "z"):
            stack.execute(RecordingCommand(name, log))
        stack.commit()
        stack.undo()
        self.assertEqual(
            log,
            [("do", "x"), ("do", "y"), ("do", "z"),
             ("undo", "z"), ("undo", "y"), ("undo", "x")],
        )

    def test_rollback_reverts_in_reverse_and_discards(self):
        log = []
        buf = Buffer("doc", "ab")
        stack = EditStack()
        insert(stack, buf, 2, "!")
        stack.undo()
        self.assertTrue(stack.can_redo)
        stack.begin()
        for name in ("x", "y", "z"):
            stack.execute(RecordingCommand(name, log))
        insert(stack, buf, 2, "cd")
        stack.rollback()
        self.assertFalse(stack.in_transaction)
        self.assertEqual(
            log,
            [("do", "x"), ("do", "y"), ("do", "z"),
             ("undo", "z"), ("undo", "y"), ("undo", "x")],
        )
        self.assertEqual(buf.text, "ab")
        self.assertFalse(stack.can_undo)
        # 事务内的 execute 已按既定语义截断重做分支；
        # rollback 本身不往重做分支塞任何东西。
        self.assertFalse(stack.can_redo)
        self.assertIsNone(stack.redo())

    def test_empty_rollback_keeps_redo_branch(self):
        buf = Buffer("doc", "ab")
        stack = EditStack()
        insert(stack, buf, 2, "!")
        stack.undo()
        self.assertTrue(stack.can_redo)
        stack.begin()
        stack.rollback()  # 事务内没有编辑，重做分支原样保留
        self.assertTrue(stack.can_redo)
        stack.redo()
        self.assertEqual(buf.text, "ab!")

    def test_nested_begin_raises(self):
        stack = EditStack()
        stack.begin()
        with self.assertRaises(RuntimeError):
            stack.begin()
        stack.rollback()  # 原事务仍然有效，可正常收尾
        self.assertFalse(stack.in_transaction)

    def test_commit_without_tx_raises(self):
        stack = EditStack()
        with self.assertRaises(RuntimeError):
            stack.commit()

    def test_rollback_without_tx_raises(self):
        stack = EditStack()
        with self.assertRaises(RuntimeError):
            stack.rollback()

    def test_empty_commit_adds_no_history(self):
        stack = EditStack()
        stack.begin()
        self.assertIsNone(stack.commit())
        self.assertFalse(stack.can_undo)

    def test_tx_execute_truncates_redo_branch(self):
        buf = Buffer("doc", "a")
        stack = EditStack()
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertTrue(stack.can_redo)
        stack.begin()
        insert(stack, buf, 1, "c")
        stack.commit()
        self.assertFalse(stack.can_redo)
        self.assertEqual(buf.text, "ac")

    def test_empty_commit_keeps_redo_branch(self):
        buf = Buffer("doc", "a")
        stack = EditStack()
        insert(stack, buf, 1, "b")
        stack.undo()
        stack.begin()
        stack.commit()  # 空事务不产生新编辑，不截断重做分支
        self.assertTrue(stack.can_redo)


class TestCoalesce(unittest.TestCase):
    def make_stack(self, window=100):
        clock = FakeClock()
        return EditStack(coalesce_window_ms=window, clock=clock), clock

    def test_default_window_zero_disables_coalesce(self):
        buf = Buffer("doc", "")
        stack = EditStack()
        insert(stack, buf, 0, "a")
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertEqual(buf.text, "a")

    def test_typing_merges_into_one_entry(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack()
        for i, ch in enumerate("hello"):
            clock.advance(10)
            insert(stack, buf, i, ch)
        self.assertEqual(buf.text, "hello")
        stack.undo()
        self.assertEqual(buf.text, "")
        self.assertFalse(stack.can_undo)
        stack.redo()
        self.assertEqual(buf.text, "hello")

    def test_merge_keeps_chaining_within_window(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack(window=100)
        for i, ch in enumerate("abc"):
            clock.advance(99)  # 每次都距上次 execute 不超过窗口
            insert(stack, buf, i, ch)
        stack.undo()
        self.assertEqual(buf.text, "")

    def test_boundary_exactly_window_merges(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack(window=100)
        insert(stack, buf, 0, "a")
        clock.advance(100)
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertEqual(buf.text, "")

    def test_beyond_window_breaks_merge(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack(window=100)
        insert(stack, buf, 0, "a")
        clock.advance(101)
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertEqual(buf.text, "a")

    def test_non_adjacent_position_does_not_merge(self):
        buf = Buffer("doc", "xy")
        stack, clock = self.make_stack()
        insert(stack, buf, 0, "a")
        clock.advance(10)
        insert(stack, buf, 3, "b")  # 起点不紧接 "a" 末尾
        stack.undo()
        self.assertEqual(buf.text, "axy")

    def test_different_key_does_not_merge(self):
        a, b = Buffer("a", ""), Buffer("b", "")
        stack, clock = self.make_stack()
        insert(stack, a, 0, "x")
        clock.advance(10)
        insert(stack, b, 0, "y")
        stack.undo()
        self.assertEqual(a.text, "x")
        self.assertEqual(b.text, "")

    def test_non_insert_does_not_merge(self):
        buf = Buffer("doc", "ab")
        stack, clock = self.make_stack()
        insert(stack, buf, 2, "c")
        clock.advance(10)
        stack.execute(DeleteText(buf, 0, 1))
        clock.advance(10)
        insert(stack, buf, 2, "d")  # 栈顶是 DeleteText，不合并
        self.assertEqual(buf.text, "bcd")
        stack.undo()
        self.assertEqual(buf.text, "bc")

    def test_undo_breaks_merge_chain(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack()
        insert(stack, buf, 0, "a")
        clock.advance(10)
        stack.undo()
        clock.advance(10)
        insert(stack, buf, 0, "b")
        stack.undo()
        self.assertEqual(buf.text, "")
        self.assertFalse(stack.can_undo)

    def test_merged_entry_truncates_redo_like_normal(self):
        buf = Buffer("doc", "")
        stack, clock = self.make_stack()
        insert(stack, buf, 0, "a")
        clock.advance(10)
        insert(stack, buf, 1, "b")
        stack.undo()
        self.assertTrue(stack.can_redo)
        clock.advance(10)
        insert(stack, buf, 0, "z")
        self.assertFalse(stack.can_redo)
        self.assertEqual(buf.text, "z")


if __name__ == "__main__":
    unittest.main()
