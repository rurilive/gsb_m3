"""连接顺序规划的行为测试。

统计可用时 Planner 重排顺序：小表集上跟穷举全排列的最优解对拍
（实际探测行数不超过最优的两倍），十一张表规划一秒内出结果，
连不上的连接组分开排再叉，统计缺失或过期整体退回声明顺序，
同样的查询加同样的统计每次给出同一个计划。
"""

import itertools
import random
import time
import unittest

from jqplan.engine import Engine, Plan, Query
from jqplan.planner import Planner
from jqplan.stats import Stats
from jqplan.table import Table


def make_skewed():
    """订单比用户大几个量级、连接键扎堆的三表场景。"""
    rng = random.Random(3)
    users = Table("users", ["uid", "city"])
    users.insert_many([(uid, rng.choice(["bj", "sh"])) for uid in range(10)])
    orders = Table("orders", ["oid", "uid"])
    orders.insert_many([(oid, rng.randrange(10)) for oid in range(5000)])
    items = Table("items", ["sku", "oid"])
    items.insert_many([(f"s{i}", rng.randrange(5000)) for i in range(300)])
    query = Query(
        [orders, items, users],
        [
            ("users", "uid", "orders", "uid"),
            ("orders", "oid", "items", "oid"),
        ],
    )
    return query, [users, orders, items]


def make_chain(count, seed):
    """count 张表连成一条链，键值均匀，行数错落。"""
    rng = random.Random(seed)
    tables = []
    for i in range(count):
        table = Table(f"t{i}", ["k", "v"])
        table.insert_many(
            [(k, rng.randrange(40)) for k in range(rng.randrange(15, 120))]
        )
        tables.append(table)
    joins = [(f"t{i}", "k", f"t{i + 1}", "k") for i in range(count - 1)]
    shuffled = list(tables)
    rng.shuffle(shuffled)
    return Query(shuffled, joins), tables


def best_scan(query):
    """穷举全排列，回报实际探测行数的最小值。"""
    engine = Engine()
    return min(
        engine.execute_plan(query, Plan(perm)).rows_scanned
        for perm in itertools.permutations(query.table_names())
    )


class ReorderTest(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()
        self.planner = Planner()

    def planned_scan(self, query, tables):
        stats = Stats.collect(tables)
        plan = self.planner.plan(query, stats)
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))
        return self.engine.execute_plan(query, plan).rows_scanned

    def test_skewed_tables_get_reordered(self):
        query, tables = make_skewed()
        stats = Stats.collect(tables)
        plan = self.planner.plan(query, stats)
        self.assertNotEqual(plan.order, query.table_names())
        planned = self.engine.execute_plan(query, plan)
        declared = self.engine.execute(query)
        self.assertLess(planned.rows_scanned, declared.rows_scanned)
        self.assertEqual(sorted(planned.rows), sorted(declared.rows))

    def test_small_queries_within_twice_of_optimal(self):
        for seed in (1, 2, 3, 4):
            query, tables = make_chain(4, seed)
            scanned = self.planned_scan(query, tables)
            self.assertLessEqual(scanned, 2 * best_scan(query))

    def test_skewed_within_twice_of_optimal(self):
        query, tables = make_skewed()
        self.assertLessEqual(self.planned_scan(query, tables), 2 * best_scan(query))

    def test_eleven_tables_planned_within_a_second(self):
        query, tables = make_chain(11, 9)
        stats = Stats.collect(tables)
        started = time.perf_counter()
        plan = self.planner.plan(query, stats)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0)
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))

    def test_components_split_disconnected_joins(self):
        a = Table("a", ["k"])
        b = Table("b", ["k"])
        c = Table("c", ["k"])
        d = Table("d", ["k"])
        e = Table("e", ["k"])
        query = Query(
            [a, b, c, d, e],
            [("a", "k", "b", "k"), ("b", "k", "c", "k"), ("d", "k", "e", "k")],
        )
        self.assertEqual(
            self.planner.components(query), (("a", "b", "c"), ("d", "e"))
        )

    def test_components_keep_singletons(self):
        a = Table("a", ["k"])
        b = Table("b", ["k"])
        lonely = Table("lonely", ["k"])
        query = Query([a, lonely, b], [("a", "k", "b", "k")])
        self.assertEqual(
            self.planner.components(query), (("a", "b"), ("lonely",))
        )

    def test_disconnected_groups_planned_per_component(self):
        rng = random.Random(5)
        big = Table("big", ["k", "v"])
        big.insert_many([(k, k) for k in range(400)])
        small = Table("small", ["k", "v"])
        small.insert_many([(k, rng.randrange(400)) for k in range(8)])
        other = Table("other", ["x"])
        other.insert_many([(x,) for x in range(3)])
        query = Query([big, other, small], [("big", "k", "small", "k")])
        stats = Stats.collect([big, small, other])
        plan = self.planner.plan(query, stats)
        self.assertEqual(plan.order, ("small", "big", "other"))
        planned = self.engine.execute_plan(query, plan)
        self.assertEqual(
            sorted(planned.rows), sorted(self.engine.execute(query).rows)
        )

    def test_stale_stats_fall_back_to_declared_order(self):
        query, tables = make_skewed()
        stats = Stats.collect(tables)
        tables[1].insert((5000, 1))
        self.assertEqual(
            self.planner.plan(query, stats).order, query.table_names()
        )

    def test_missing_table_stats_fall_back(self):
        query, tables = make_skewed()
        stats = Stats.collect(tables[:2])
        self.assertEqual(
            self.planner.plan(query, stats).order, query.table_names()
        )

    def test_missing_join_column_distinct_falls_back(self):
        query, tables = make_skewed()
        entries = {}
        for table in tables:
            entries[table.name] = {
                "rows": table.row_count(),
                "distinct": {
                    column: table.distinct(column) for column in table.columns
                },
                "revision": table.revision,
            }
        del entries["orders"]["distinct"]["uid"]
        stats = Stats(entries)
        self.assertFalse(stats.stale(tables))
        self.assertEqual(
            self.planner.plan(query, stats).order, query.table_names()
        )

    def test_same_query_same_stats_same_plan(self):
        query, tables = make_skewed()
        stats = Stats.collect(tables)
        first = self.planner.plan(query, stats)
        second = Planner().plan(query, stats)
        self.assertEqual(first, second)
        self.assertEqual(first.order, self.planner.plan(query, stats).order)

    def test_planned_rows_match_declared_rows(self):
        for seed in (11, 12):
            query, tables = make_chain(5, seed)
            stats = Stats.collect(tables)
            planned = self.engine.execute_plan(
                query, self.planner.plan(query, stats)
            )
            declared = self.engine.execute(query)
            self.assertEqual(sorted(planned.rows), sorted(declared.rows))


if __name__ == "__main__":
    unittest.main()
