"""Coordinator 现有行为的锁定测试。

参与者只实现 begin()/commit()（外加 name）。测试断言的是"哪个动作
落在哪些参与者上、相对顺序如何、协调者状态怎么走"，不依赖参与者
上除 begin/commit 之外还调用了什么。
"""

import unittest

from coordx.coordinator import Coordinator, Ledger, Participant


class FakeParticipant(Participant):
    """把 begin/commit 记进共享流水，用来观察调用顺序。"""

    def __init__(self, name, journal, fail_on=None):
        super().__init__(name)
        self._journal = journal
        self._fail_on = fail_on

    def begin(self):
        self._journal.append(("begin", self.name))
        if self._fail_on == "begin":
            raise RuntimeError("%s: begin failed" % self.name)

    def commit(self):
        self._journal.append(("commit", self.name))
        if self._fail_on == "commit":
            raise RuntimeError("%s: commit failed" % self.name)


def names_of(journal, op):
    """按记录顺序取某个动作落在的参与者名字。"""
    return [name for recorded_op, name in journal if recorded_op == op]


class TestCoordinator(unittest.TestCase):
    def setUp(self):
        self.journal = []
        self.a = FakeParticipant("a", self.journal)
        self.b = FakeParticipant("b", self.journal)
        self.c = FakeParticipant("c", self.journal)
        self.coord = Coordinator([self.a, self.b, self.c])

    def test_participants_returns_names_in_order(self):
        self.assertEqual(self.coord.participants(), ("a", "b", "c"))

    def test_active_starts_false(self):
        self.assertFalse(self.coord.active())

    def test_begin_calls_each_participant_in_order(self):
        self.coord.begin()
        self.assertTrue(self.coord.active())
        self.assertEqual(names_of(self.journal, "begin"), ["a", "b", "c"])

    def test_commit_calls_each_participant_in_order(self):
        self.coord.begin()
        self.coord.commit()
        self.assertEqual(names_of(self.journal, "commit"), ["a", "b", "c"])
        self.assertFalse(self.coord.active())

    def test_begin_twice_raises(self):
        self.coord.begin()
        with self.assertRaises(RuntimeError):
            self.coord.begin()

    def test_commit_without_begin_raises(self):
        with self.assertRaises(RuntimeError):
            self.coord.commit()

    def test_empty_participants_cycle(self):
        coord = Coordinator([])
        self.assertEqual(coord.participants(), ())
        coord.begin()
        self.assertTrue(coord.active())
        coord.commit()
        self.assertFalse(coord.active())

    def test_can_begin_again_after_commit(self):
        self.coord.begin()
        self.coord.commit()
        self.coord.begin()
        self.coord.commit()
        self.assertEqual(names_of(self.journal, "begin"), ["a", "b", "c"] * 2)

    def test_error_in_begin_propagates_and_stays_inactive(self):
        journal = []
        bad = FakeParticipant("bad", journal, fail_on="begin")
        coord = Coordinator([bad])
        with self.assertRaises(RuntimeError):
            coord.begin()
        self.assertFalse(coord.active())

    def test_error_in_commit_propagates(self):
        journal = []
        bad = FakeParticipant("bad", journal, fail_on="commit")
        coord = Coordinator([bad])
        coord.begin()
        with self.assertRaises(RuntimeError):
            coord.commit()

    def test_elapsed_zero_without_active_transaction(self):
        self.assertEqual(self.coord.elapsed(), 0.0)

    def test_elapsed_reads_injected_clock(self):
        now = [100.0]
        coord = Coordinator([self.a], clock=lambda: now[0])
        coord.begin()
        now[0] = 112.5
        self.assertEqual(coord.elapsed(), 12.5)
        coord.commit()
        self.assertEqual(coord.elapsed(), 0.0)


class TestLedger(unittest.TestCase):
    def test_commit_publishes_pending_write(self):
        ledger = Ledger("l", value=1)
        ledger.begin()
        ledger.write(7)
        self.assertEqual(ledger.value, 1)   # 提交前不可见
        ledger.commit()
        self.assertEqual(ledger.value, 7)

    def test_commit_without_begin_raises(self):
        with self.assertRaises(RuntimeError):
            Ledger("l").commit()

    def test_write_outside_transaction_raises(self):
        with self.assertRaises(RuntimeError):
            Ledger("l").write(1)

    def test_coordinator_drives_ledgers(self):
        left = Ledger("left", value=0)
        right = Ledger("right", value=0)
        coord = Coordinator([left, right])
        coord.begin()
        left.write(5)
        right.write(6)
        coord.commit()
        self.assertEqual((left.value, right.value), (5, 6))


if __name__ == "__main__":
    unittest.main()
