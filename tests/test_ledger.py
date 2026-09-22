"""Ledger 行为基线：追加、副本语义与按类汇总。"""

import unittest

from quotatree import Ledger


class LedgerTest(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()

    def test_record_and_read_back(self):
        self.ledger.record("web", "acquire", 10, True, "r1")
        self.assertEqual(self.ledger.entries(), [{
            "seq": 1,
            "team": "web",
            "kind": "acquire",
            "amount": 10,
            "ok": True,
            "req_id": "r1",
        }])

    def test_entries_come_back_as_copies(self):
        self.ledger.record("web", "acquire", 10, True)
        got = self.ledger.entries()
        got[0]["amount"] = 999
        got.append({"fake": True})
        self.assertEqual(self.ledger.count(), 1)
        self.assertEqual(self.ledger.entries()[0]["amount"], 10)

    def test_seq_counts_up(self):
        self.ledger.record("web", "acquire", 10, True)
        self.ledger.record("web", "release", 4, True)
        self.assertEqual([e["seq"] for e in self.ledger.entries()], [1, 2])

    def test_by_team_filters_in_order(self):
        self.ledger.record("web", "acquire", 10, True)
        self.ledger.record("db", "acquire", 5, False)
        self.ledger.record("web", "release", 3, True)
        self.assertEqual([e["amount"] for e in self.ledger.by_team("web")], [10, 3])
        self.assertEqual([e["amount"] for e in self.ledger.by_team("db")], [5])
        self.assertEqual(self.ledger.by_team("nope"), [])

    def test_stats_counts_by_kind_and_rejections(self):
        self.ledger.record("web", "acquire", 10, True)
        self.ledger.record("web", "release", 4, True)
        self.ledger.record("web", "replay", 10, True)
        self.ledger.record("db", "acquire", 5, False)
        stats = self.ledger.stats()
        self.assertEqual(stats["acquire"], 2)
        self.assertEqual(stats["release"], 1)
        self.assertEqual(stats["replay"], 1)
        self.assertEqual(stats["rejected"], 1)

    def test_unknown_kind_rejected_and_nothing_recorded(self):
        with self.assertRaises(ValueError):
            self.ledger.record("web", "nope", 1, True)
        self.assertEqual(self.ledger.count(), 0)

    def test_falsy_result_is_kept(self):
        self.ledger.record("web", "acquire", 10, False)
        self.assertIs(self.ledger.entries()[0]["ok"], False)


if __name__ == "__main__":
    unittest.main()
