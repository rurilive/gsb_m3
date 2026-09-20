"""内存表与变更流的既有行为锁定。"""

import unittest

from mvjoin import (
    ChangeLog,
    Dataset,
    Table,
    TableError,
    delete_change,
    insert_change,
    update_change,
)


def make_dataset():
    return Dataset(Table("orders", "order_id"), Table("skus", "row_id"))


ORDER = {"order_id": 1, "sku": "A1", "amount": 10}


class TableTest(unittest.TestCase):
    def test_rows_are_copies(self):
        table = Table("orders", "order_id")
        table._put(dict(ORDER))
        table.get(1)["amount"] = 999
        table.rows()[0]["amount"] = 999
        self.assertEqual(table.get(1)["amount"], 10)

    def test_key_of_rejects_bad_rows(self):
        table = Table("orders", "order_id")
        for bad in ({"sku": "A1"}, {"order_id": None}, "not a row"):
            with self.assertRaises(TableError):
                table.key_of(bad)

    def test_table_names_must_be_unique(self):
        with self.assertRaises(TableError):
            Dataset(Table("orders", "order_id"), Table("orders", "order_id"))


class DatasetTest(unittest.TestCase):
    def test_insert_update_delete(self):
        dataset = make_dataset()
        dataset.apply(insert_change(1, "orders", ORDER))
        self.assertEqual(len(dataset.table("orders")), 1)
        key = dataset.apply(update_change(2, "orders", ORDER,
                                          {"order_id": 1, "sku": "B2", "amount": 25}))
        self.assertEqual((key, dataset.table("orders").get(1)),
                         (1, {"order_id": 1, "sku": "B2", "amount": 25}))
        dataset.apply(delete_change(3, "orders", {"order_id": 1, "sku": "B2", "amount": 25}))
        self.assertEqual(len(dataset.table("orders")), 0)

    def test_rejects_inconsistent_changes(self):
        dataset = make_dataset()
        dataset.apply(insert_change(1, "orders", ORDER))
        bad = [insert_change(2, "orders", ORDER),
               update_change(3, "orders", {"order_id": 9, "sku": "A1", "amount": 1},
                             {"order_id": 9, "sku": "A1", "amount": 2}),
               update_change(4, "orders", {"order_id": 1, "sku": "A1", "amount": 99},
                             {"order_id": 1, "sku": "A1", "amount": 2}),
               delete_change(5, "orders", {"order_id": 8, "sku": "A1", "amount": 10}),
               {"seq": 6, "table": "nope", "op": "insert", "before": None,
                "after": {"order_id": 2}},
               {"seq": 7, "table": "orders", "op": "upsert", "before": None,
                "after": {"order_id": 2}},
               {"seq": 0, "table": "orders", "op": "insert", "before": None,
                "after": {"order_id": 2}}]
        for change in bad:
            with self.assertRaises(TableError):
                dataset.apply(change)

    def test_update_cannot_change_primary_key(self):
        dataset = make_dataset()
        dataset.apply(insert_change(1, "orders", ORDER))
        with self.assertRaises(TableError):
            dataset.apply(update_change(2, "orders", ORDER,
                                        {"order_id": 2, "sku": "A1", "amount": 10}))

    def test_insert_and_delete_carry_one_side_only(self):
        dataset = make_dataset()
        bad_insert = insert_change(1, "orders", ORDER)
        bad_insert["before"] = {"order_id": 1}
        bad_delete = delete_change(2, "orders", ORDER)
        bad_delete["after"] = {"order_id": 1}
        for change in (bad_insert, bad_delete):
            with self.assertRaises(TableError):
                dataset.apply(change)


class ChangeLogTest(unittest.TestCase):
    def test_seq_starts_at_one_and_increments(self):
        log = ChangeLog()
        self.assertEqual(log.insert("orders", ORDER)["seq"], 1)
        self.assertEqual(log.update("orders", ORDER, ORDER)["seq"], 2)
        self.assertEqual(log.delete("orders", ORDER)["seq"], 3)
        self.assertEqual((log.next_seq, [c["op"] for c in log.changes()]),
                         (4, ["insert", "update", "delete"]))

    def test_changes_are_copies(self):
        log = ChangeLog(start=11)
        log.insert("orders", ORDER)
        changes = log.changes()
        changes[0]["after"]["amount"] = 999
        self.assertEqual(log.changes()[0]["after"]["amount"], 10)
        self.assertEqual(log.changes()[0]["seq"], 11)

    def test_dataset_can_follow_a_log(self):
        log = ChangeLog()
        log.insert("skus", {"row_id": 1, "sku": "A1", "category": "fresh"})
        log.insert("orders", ORDER)
        dataset = make_dataset()
        for change in log.changes():
            dataset.apply(change)
        self.assertEqual(dataset.table("skus").get(1)["category"], "fresh")
        self.assertEqual(dataset.table("orders").get(1)["amount"], 10)


if __name__ == "__main__":
    unittest.main()
