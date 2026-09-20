"""全量重算视图的既有行为锁定，也是视图语义的基准。"""

import unittest

from mvjoin import (
    ChangeLog,
    Dataset,
    FullView,
    Join,
    SpecError,
    Table,
    ViewSpec,
    delete_change,
    update_change,
)

SKUS = ({"row_id": 1, "sku": "A1", "category": "fresh", "warehouse": "east"},
        {"row_id": 2, "sku": "A1", "category": "frozen", "warehouse": "west"},
        {"row_id": 3, "sku": "B2", "category": "dry", "warehouse": "east"},
        {"row_id": 4, "sku": None, "category": "dry", "warehouse": "west"})
ORDERS = ({"order_id": 101, "sku": "A1", "channel": "app", "amount": 1200},
          {"order_id": 102, "sku": "B2", "channel": "web", "amount": 800},
          {"order_id": 103, "sku": None, "channel": "app", "amount": 5000},
          {"order_id": 104, "sku": "A1", "channel": "app", "amount": 300})


def sample_log():
    """两个仓库在售的商品，加四笔订单。"""
    log = ChangeLog()
    for row in SKUS:
        log.insert("skus", row)
    for row in ORDERS:
        log.insert("orders", row)
    return log


def build(log):
    dataset = Dataset(Table("orders", "order_id"), Table("skus", "row_id"))
    for change in log.changes():
        dataset.apply(change)
    return dataset


JOIN_SPEC = ViewSpec(
    name="category_orders",
    join=Join("orders", "skus", "sku", "sku"),
    group="skus.category",
    metrics=[("cnt", "count", None), ("amount", "sum", "orders.amount")],
)

SINGLE_SPEC = ViewSpec(
    name="app_by_sku",
    table="orders",
    where=lambda row: row["channel"] == "app",
    group="sku",
    metrics=[("cnt", "count", None), ("amount", "sum", "amount")],
)


class JoinViewTest(unittest.TestCase):
    def test_pairs_pair_left_with_every_matching_right_row(self):
        pairs = list(FullView(JOIN_SPEC).pairs(build(sample_log())))
        self.assertEqual(len(pairs), 5)
        self.assertEqual(sorted(row["order_id"] for row, _ in pairs),
                         [101, 101, 102, 104, 104])

    def test_none_join_keys_never_match(self):
        for left_row, right_row in FullView(JOIN_SPEC).pairs(build(sample_log())):
            self.assertIsNotNone(left_row["sku"])
            self.assertIsNotNone(right_row["sku"])

    def test_recompute_groups_by_right_column(self):
        view = FullView(JOIN_SPEC)
        result = view.recompute(build(sample_log()))
        self.assertEqual(result, {
            "fresh": {"cnt": 2, "amount": 1500},
            "frozen": {"cnt": 2, "amount": 1500},
            "dry": {"cnt": 1, "amount": 800},
        })
        self.assertEqual((view.last_pairs, view.refreshes), (5, 1))
        empty = FullView(JOIN_SPEC)
        self.assertEqual((empty.recompute(build(ChangeLog())), empty.result()), ({}, {}))

    def test_where_sees_prefixed_columns(self):
        spec = ViewSpec(name="big_orders",
                        join=Join("orders", "skus", "sku", "sku"),
                        where=lambda row: row["orders.amount"] >= 1000,
                        group="skus.category",
                        metrics=[("cnt", "count", None)])
        self.assertEqual(FullView(spec).recompute(build(sample_log())),
                         {"fresh": {"cnt": 1}, "frozen": {"cnt": 1}})

    def test_recompute_follows_table_changes(self):
        dataset = build(sample_log())
        view = FullView(JOIN_SPEC)
        view.recompute(dataset)
        dataset.apply(update_change(9, "skus", dict(SKUS[2]),
                                    {"row_id": 3, "sku": "B2", "category": "snack",
                                     "warehouse": "east"}))
        result = view.recompute(dataset)
        self.assertEqual(result["snack"], {"cnt": 1, "amount": 800})
        self.assertNotIn("dry", result)
        dataset.apply(delete_change(10, "orders", dict(ORDERS[1])))
        result = view.recompute(dataset)
        self.assertNotIn("snack", result)
        self.assertEqual(sorted(result), ["fresh", "frozen"])
        self.assertEqual(view.refreshes, 3)

    def test_group_key_none_is_its_own_group(self):
        log = ChangeLog()
        log.insert("skus", {"row_id": 1, "sku": "A1", "category": None})
        log.insert("orders", {"order_id": 1, "sku": "A1", "amount": 40})
        self.assertEqual(FullView(JOIN_SPEC).recompute(build(log)),
                         {None: {"cnt": 1, "amount": 40}})

    def test_empty_dataset_gives_empty_result(self):
        view = FullView(JOIN_SPEC)
        self.assertEqual(view.recompute(build(ChangeLog())), {})


class SingleTableViewTest(unittest.TestCase):
    def test_filter_groups_and_aggregates(self):
        self.assertEqual(FullView(SINGLE_SPEC).recompute(build(sample_log())),
                         {"A1": {"cnt": 2, "amount": 1500},
                          None: {"cnt": 1, "amount": 5000}})

    def test_deleted_rows_leave_the_result(self):
        dataset = build(sample_log())
        view = FullView(SINGLE_SPEC)
        view.recompute(dataset)
        dataset.apply(delete_change(20, "orders", dict(ORDERS[3])))
        dataset.apply(delete_change(21, "orders", dict(ORDERS[2])))
        self.assertEqual(view.recompute(dataset), {"A1": {"cnt": 1, "amount": 1200}})

    def test_result_is_a_copy(self):
        view = FullView(SINGLE_SPEC)
        result = view.recompute(build(sample_log()))
        result["A1"]["cnt"] = 99
        result["extra"] = {}
        self.assertNotIn("extra", view.result())
        self.assertEqual(view.result()["A1"]["cnt"], 2)


class SpecTest(unittest.TestCase):
    def test_table_and_join_are_exclusive(self):
        with self.assertRaises(SpecError):
            ViewSpec(name="v", group="sku", metrics=[("cnt", "count", None)],
                     table="orders", join=Join("orders", "skus", "sku", "sku"))
        with self.assertRaises(SpecError):
            ViewSpec(name="v", group="sku", metrics=[("cnt", "count", None)])
        with self.assertRaises(SpecError):
            Join("orders", "orders", "sku", "sku")

    def test_metric_shapes_are_checked(self):
        bad = ([("cnt", "count", "sku")], [("amount", "sum", None)],
               [("x", "avg", "amount")], [("cnt", "count")],
               [("x", "count", None), ("x", "sum", "amount")])
        for metrics in bad:
            with self.assertRaises(SpecError):
                ViewSpec(name="v", group="sku", metrics=metrics, table="orders")

    def test_column_prefixes_follow_the_source(self):
        with self.assertRaises(SpecError):
            ViewSpec(name="v", table="orders", group="orders.sku",
                     metrics=[("cnt", "count", None)])
        join = Join("orders", "skus", "sku", "sku")
        for group in ("category", "carts.category"):
            with self.assertRaises(SpecError):
                ViewSpec(name="v", join=join, group=group, metrics=[("cnt", "count", None)])

    def test_sources_lists_both_sides(self):
        self.assertEqual(JOIN_SPEC.sources(), ("orders", "skus"))
        self.assertEqual(SINGLE_SPEC.sources(), ("orders",))


if __name__ == "__main__":
    unittest.main()
