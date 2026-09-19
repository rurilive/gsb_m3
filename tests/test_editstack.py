"""EditStack 现有行为的锁定测试。"""

import unittest

from editstack.commands import Buffer, DeleteText, InsertText
from editstack.stack import EditStack


def insert(stack, buf, pos, text):
    cmd = InsertText(buf, pos, text)
    stack.execute(cmd)
    return cmd


class TestExecuteUndoRedo(unittest.TestCase):
    def test_execute_applies(self):
        buf = Buffer("main", "hello")
        stack = EditStack()
        insert(stack, buf, 5, " world")
        self.assertEqual(buf.text, "hello world")

    def test_undo_reverts_text(self):
        buf = Buffer("main", "hello")
        stack = EditStack()
        insert(stack, buf, 5, " world")
        stack.undo()
        self.assertEqual(buf.text, "hello")

    def test_redo_reapplies(self):
        buf = Buffer("main", "ab")
        stack = EditStack()
        insert(stack, buf, 2, "cd")
        stack.undo()
        cmd = stack.redo()
        self.assertEqual(buf.text, "abcd")
        self.assertIsInstance(cmd, InsertText)

    def test_flags_transition(self):
        buf = Buffer("main", "x")
        stack = EditStack()
        self.assertFalse(stack.can_undo)
        self.assertFalse(stack.can_redo)
        insert(stack, buf, 1, "y")
        self.assertTrue(stack.can_undo)
        self.assertFalse(stack.can_redo)
        stack.undo()
        self.assertFalse(stack.can_undo)
        self.assertTrue(stack.can_redo)

    def test_undo_redo_on_empty_stack_return_none(self):
        stack = EditStack()
        self.assertIsNone(stack.undo())
        self.assertIsNone(stack.redo())

    def test_multiple_undo_is_lifo(self):
        buf = Buffer("main", "")
        stack = EditStack()
        insert(stack, buf, 0, "a")
        insert(stack, buf, 1, "b")
        insert(stack, buf, 2, "c")
        stack.undo()
        stack.undo()
        self.assertEqual(buf.text, "a")
        stack.redo()
        self.assertEqual(buf.text, "ab")

    def test_undo_returns_command(self):
        buf = Buffer("main", "")
        stack = EditStack()
        cmd = insert(stack, buf, 0, "z")
        self.assertIs(stack.undo(), cmd)

    def test_new_edit_truncates_redo(self):
        buf = Buffer("main", "s")
        stack = EditStack()
        insert(stack, buf, 1, "A")
        stack.undo()
        self.assertTrue(stack.can_redo)
        insert(stack, buf, 1, "B")
        self.assertFalse(stack.can_redo)
        self.assertIsNone(stack.redo())
        self.assertEqual(buf.text, "sB")


class TestTextCommands(unittest.TestCase):
    def test_delete_and_restore(self):
        buf = Buffer("main", "hello world")
        stack = EditStack()
        stack.execute(DeleteText(buf, 5, 6))
        self.assertEqual(buf.text, "hello")
        stack.undo()
        self.assertEqual(buf.text, "hello world")

    def test_key_taken_from_buffer(self):
        buf = Buffer("notes", "")
        cmd = InsertText(buf, 0, "x")
        self.assertEqual(cmd.key, "notes")

    def test_buffers_are_independent(self):
        a, b = Buffer("a", "1"), Buffer("b", "2")
        stack = EditStack()
        insert(stack, a, 1, "x")
        insert(stack, b, 0, "y")
        stack.undo()
        self.assertEqual(a.text, "1x")
        self.assertEqual(b.text, "2")


if __name__ == "__main__":
    unittest.main()
