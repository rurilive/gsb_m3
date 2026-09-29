"""Log 现有行为的锁定测试：追加、按位读取、长度与清空。

只覆盖当前实现已经具备的能力。序号、检查点、截断与重放、崩溃恢复与校验和
都还没有，新增行为另建测试文件，不改动本文件。
"""

import unittest

from walog import InvalidLsn, Log


class TestAppend(unittest.TestCase):
    def test_append_returns_position(self):
        log = Log()
        self.assertEqual(log.append("a"), 0)
        self.assertEqual(log.append("b"), 1)

    def test_append_keeps_insertion_order(self):
        log = Log()
        log.append("a")
        log.append("b")
        log.append("c")
        self.assertEqual(log.read(0), "a")
        self.assertEqual(log.read(1), "b")
        self.assertEqual(log.read(2), "c")

    def test_append_returns_new_position_each_time(self):
        log = Log()
        positions = [log.append(i) for i in range(4)]
        self.assertEqual(positions, [0, 1, 2, 3])


class TestRead(unittest.TestCase):
    def test_read_first_item(self):
        log = Log()
        log.append("first")
        self.assertEqual(log.read(0), "first")

    def test_read_last_item(self):
        log = Log()
        log.append("a")
        log.append("b")
        self.assertEqual(log.read(1), "b")

    def test_read_payload_is_returned_unchanged(self):
        log = Log()
        payload = {"op": "put", "key": "k", "value": 7}
        log.append(payload)
        self.assertEqual(log.read(0), payload)


class TestLength(unittest.TestCase):
    def test_len_empty_log_is_zero(self):
        self.assertEqual(len(Log()), 0)

    def test_len_tracks_appends(self):
        log = Log()
        log.append("a")
        log.append("b")
        self.assertEqual(len(log), 2)


class TestReset(unittest.TestCase):
    def test_reset_clears_items(self):
        log = Log()
        log.append("a")
        log.append("b")
        log.reset()
        self.assertEqual(len(log), 0)

    def test_read_after_reset_is_out_of_range(self):
        log = Log()
        log.append("a")
        log.reset()
        with self.assertRaises(InvalidLsn):
            log.read(0)


class TestValidation(unittest.TestCase):
    def test_read_negative_rejected(self):
        with self.assertRaises(InvalidLsn):
            Log().read(-1)

    def test_read_beyond_end_rejected(self):
        log = Log()
        log.append("a")
        with self.assertRaises(InvalidLsn):
            log.read(1)

    def test_read_non_integer_rejected(self):
        log = Log()
        log.append("a")
        with self.assertRaises(InvalidLsn):
            log.read(0.5)

    def test_read_bool_rejected(self):
        with self.assertRaises(InvalidLsn):
            Log().read(True)

    def test_rejected_read_leaves_log_untouched(self):
        log = Log()
        log.append("a")
        try:
            log.read(9)
        except InvalidLsn:
            pass
        self.assertEqual(len(log), 1)


if __name__ == "__main__":
    unittest.main()
