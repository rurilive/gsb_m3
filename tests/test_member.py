"""MembershipTable 的行为基线。"""

import unittest

from membersim.member import ALIVE, DEAD, MembershipTable


class TestMembershipTable(unittest.TestCase):
    def setUp(self):
        self.table = MembershipTable(["n1", "n2", "n3"])

    def test_members_start_alive(self):
        self.assertEqual(self.table.alive_members(), ("n1", "n2", "n3"))
        self.assertEqual(self.table.status_of("n2"), ALIVE)

    def test_unknown_member_raises(self):
        with self.assertRaises(KeyError):
            self.table.status_of("n9")

    def test_mark_down_then_up(self):
        self.table.mark_down("n3")
        self.assertEqual(self.table.status_of("n3"), DEAD)
        self.assertEqual(self.table.alive_members(), ("n1", "n2"))
        self.table.mark_up("n3")
        self.assertEqual(self.table.status_of("n3"), ALIVE)

    def test_marking_unknown_member_raises(self):
        with self.assertRaises(KeyError):
            self.table.mark_down("n9")
        with self.assertRaises(KeyError):
            self.table.mark_up("n9")

    def test_members_filters_by_status(self):
        self.table.mark_down("n1")
        self.assertEqual(self.table.members(DEAD), ("n1",))
        self.assertEqual(self.table.members(ALIVE), ("n2", "n3"))
        self.assertEqual(self.table.members(), ("n1", "n2", "n3"))

    def test_snapshot_is_a_copy(self):
        snap = self.table.snapshot()
        snap["n1"] = DEAD
        self.assertEqual(self.table.status_of("n1"), ALIVE)

    def test_merge_snapshot_keeps_members(self):
        self.table.merge_snapshot({"n2": ALIVE, "n3": DEAD})
        self.assertEqual(self.table.members(), ("n1", "n2", "n3"))
        self.assertEqual(self.table.status_of("n3"), DEAD)

    def test_merge_snapshot_ignores_unknown(self):
        self.table.merge_snapshot({"n9": DEAD})
        self.assertEqual(self.table.members(), ("n1", "n2", "n3"))

    def test_duplicate_members_rejected(self):
        with self.assertRaises(ValueError):
            MembershipTable(["n1", "n1"])


if __name__ == "__main__":
    unittest.main()
