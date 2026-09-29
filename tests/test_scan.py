"""Table 现有行为的锁定测试。"""

import unittest

from rangeidx.table import Table


def sample():
    t = Table("users")
    t.insert({"id": 1, "name": "alice", "age": 30})
    t.insert({"id": 2, "name": "bob", "age": 25})
    t.insert({"id": 3, "name": "carol", "age": 30})
    return t


class TestTableBasics(unittest.TestCase):
    def test_insert_returns_copy(self):
        t = Table("users")
        row = t.insert({"id": 1, "name": "alice", "age": 30})
        self.assertEqual(row, {"id": 1, "name": "alice", "age": 30})
        row["age"] = 99
        self.assertEqual(t.all()[0]["age"], 30)

    def test_count(self):
        t = sample()
        self.assertEqual(t.count(), 3)

    def test_fields_by_appearance(self):
        t = Table("users")
        t.insert({"id": 1, "age": 30, "name": "alice"})
        self.assertEqual(t.fields, ["id", "age", "name"])

    def test_all_returns_copies_in_insertion_order(self):
        t = sample()
        rows = t.all()
        self.assertEqual([r["id"] for r in rows], [1, 2, 3])
        rows[0]["age"] = 0
        self.assertEqual(t.all()[0]["age"], 30)

    def test_default_pk(self):
        t = sample()
        self.assertEqual(t.pk, "id")


class TestScan(unittest.TestCase):
    def test_scan_filters_by_predicate(self):
        t = sample()
        hit = t.scan(lambda r: r["age"] == 30)
        self.assertEqual([r["id"] for r in hit], [1, 3])

    def test_scan_keeps_insertion_order(self):
        t = Table("users")
        for i in (5, 3, 4):
            t.insert({"id": i, "age": i})
        hit = t.scan(lambda r: r["age"] >= 4)
        self.assertEqual([r["id"] for r in hit], [5, 4])

    def test_scan_empty_result(self):
        t = sample()
        self.assertEqual(t.scan(lambda r: r["age"] > 100), [])

    def test_scan_counts_every_row(self):
        t = sample()
        t.reset_access_count()
        t.scan(lambda r: r["id"] == 2)
        self.assertEqual(t.access_count, 3)

    def test_access_count_accumulates(self):
        t = sample()
        t.reset_access_count()
        t.scan(lambda r: r["age"] == 30)
        t.scan(lambda r: r["age"] == 30)
        self.assertEqual(t.access_count, 6)

    def test_reset_access_count(self):
        t = sample()
        t.scan(lambda r: True)
        t.reset_access_count()
        self.assertEqual(t.access_count, 0)

    def test_scan_returns_copies(self):
        t = sample()
        hit = t.scan(lambda r: r["id"] == 1)
        hit[0]["age"] = 0
        self.assertEqual(t.all()[0]["age"], 30)


if __name__ == "__main__":
    unittest.main()