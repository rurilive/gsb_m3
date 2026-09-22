"""连接顺序规划的行为测试。

小表集上跟穷举全排列的最优探测行数对拍（不许超过两倍），
十一张表时规划要在一秒内出结果；连接组拆分、统计缺失或过期的
整体退化、以及同查询同统计必出同计划的确定性也在这里锁住。
"""

import itertools
import random
import time
import unittest

from jqplan.engine import Engine, Plan, Query
from jqplan.planner import Planner
from jqplan.stats import Stats
from jqplan.table import Table

from test_engine import make_query, make_tables


def make_star(seed, dim_count, fact_rows, dim_rows):
    """外键星型 schema：事实表大、维度表小，外键分布往小键值扎堆。"""
    rng = random.Random(seed)
    dims = []
    for i in range(dim_count):
        dim = Table(f"dim{i}", ["k", "v"])
        dim.insert_many([(k, rng.randrange(100)) for k in range(dim_rows[i])])
        dims.append(dim)
    fact = Table("fact", ["id"] + [f"k{i}" for i in range(dim_count)])
    fact.insert_many(
        (i,)
        + tuple(
            min(rng.randrange(dim_rows[j]), rng.randrange(dim_rows[j]))
            for j in range(dim_count)
        )
        for i in range(fact_rows)
    )
    tables = [fact] + dims
    rng.shuffle(tables)
    joins = [("fact", f"k{i}", f"dim{i}", "k") for i in range(dim_count)]
    return tables, joins


def brute_force_best(engine, query):
    return min(
        engine.execute_plan(query, Plan(perm)).rows_scanned
        for perm in itertools.permutations(query.table_names())
    )


class StarJoinOrderTest(unittest.TestCase):
    def test_within_two_x_of_brute_force_optimal(self):
        engine = Engine()
        planner = Planner()
        for seed in range(4):
            rng = random.Random(100 + seed)
            tables, joins = make_star(
                seed,
                dim_count=rng.randrange(2, 4),
                fact_rows=rng.randrange(60, 200),
                dim_rows=[rng.randrange(3, 9) for _ in range(3)],
            )
            query = Query(tables, joins)
            stats = Stats.collect(tables)
            planned = engine.execute_plan(query, planner.plan(query, stats))
            best = brute_force_best(engine, query)
            self.assertLessEqual(
                planned.rows_scanned,
                2 * best,
                f"seed={seed}: 规划探测 {planned.rows_scanned}，最优 {best}",
            )

    def test_skewed_fact_table_no_longer_scanned_first(self):
        engine = Engine()
        tables, joins = make_star(5, dim_count=3, fact_rows=2000, dim_rows=[4, 6, 8])
        query = Query(tables, joins)
        planned = engine.execute_plan(query, Planner().plan(query, Stats.collect(tables)))
        declared = engine.execute(query)
        self.assertNotEqual(planned.order, query.table_names())
        self.assertLess(planned.rows_scanned, declared.rows_scanned)
        self.assertEqual(sorted(planned.rows), sorted(declared.rows))


class LargeQueryTest(unittest.TestCase):
    def test_eleven_tables_plan_within_a_second(self):
        rng = random.Random(11)
        tables = []
        for i in range(11):
            table = Table(f"t{i}", ["k", "v"])
            table.insert_many(
                (rng.randrange(40), rng.randrange(1000))
                for _ in range(rng.randrange(10, 60))
            )
            tables.append(table)
        joins = [(f"t{i}", "k", f"t{i+1}", "k") for i in range(10)]
        query = Query(tables, joins)
        stats = Stats.collect(tables)

        start = time.monotonic()
        plan = Planner().plan(query, stats)
        elapsed = time.monotonic() - start

        self.assertLess(elapsed, 1.0)
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))
        engine = Engine()
        planned = engine.execute_plan(query, plan)
        declared = engine.execute(query)
        self.assertEqual(sorted(planned.rows), sorted(declared.rows))
        self.assertLessEqual(planned.rows_scanned, declared.rows_scanned)


class ComponentsTest(unittest.TestCase):
    def make_disconnected_query(self):
        rng = random.Random(3)
        tables = []
        for name, rows in (("a", 6), ("b", 9), ("c", 4), ("d", 7), ("e", 5)):
            table = Table(name, ["k", "v"])
            table.insert_many(
                (rng.randrange(4), rng.randrange(50)) for _ in range(rows)
            )
            tables.append(table)
        query = Query(
            tables,
            [("a", "k", "b", "k"), ("b", "k", "c", "k"), ("d", "k", "e", "k")],
        )
        return query, tables

    def test_components_splits_disconnected_graph(self):
        query, _ = self.make_disconnected_query()
        planner = Planner()
        self.assertEqual(
            planner.components(query), (("a", "b", "c"), ("d", "e"))
        )

    def test_components_without_joins_are_singletons(self):
        query, _ = self.make_disconnected_query()
        lone = Query(query.tables(), [])
        self.assertEqual(
            Planner().components(lone),
            tuple((name,) for name in lone.table_names()),
        )

    def test_disconnected_groups_planned_then_crossed(self):
        query, tables = self.make_disconnected_query()
        engine = Engine()
        plan = Planner().plan(query, Stats.collect(tables))
        self.assertEqual(sorted(plan.order), sorted(query.table_names()))
        for group in (("a", "b", "c"), ("d", "e")):
            positions = [plan.order.index(name) for name in group]
            self.assertEqual(
                max(positions) - min(positions), len(group) - 1,
                f"连接组 {group} 在计划里应当连续: {plan.order}",
            )
        planned = engine.execute_plan(query, plan)
        declared = engine.execute(query)
        self.assertEqual(sorted(planned.rows), sorted(declared.rows))
        best = brute_force_best(engine, query)
        self.assertLessEqual(planned.rows_scanned, 2 * best)


class FallbackTest(unittest.TestCase):
    def setUp(self):
        self.users, self.orders, self.items = make_tables()
        self.query = make_query(self.users, self.orders, self.items)
        self.declared = self.query.table_names()

    def test_missing_table_stats_fall_back(self):
        partial = Stats.collect([self.users, self.orders])
        self.assertEqual(Planner().plan(self.query, partial).order, self.declared)

    def test_missing_distinct_stats_fall_back(self):
        stats = Stats(
            {
                table.name: {
                    "rows": table.row_count(),
                    "distinct": {},
                    "revision": table.revision,
                }
                for table in (self.users, self.orders, self.items)
            }
        )
        self.assertEqual(Planner().plan(self.query, stats).order, self.declared)

    def test_stale_stats_fall_back(self):
        stats = Stats.collect([self.users, self.orders, self.items])
        self.users.insert((4, "gz"))
        self.assertEqual(Planner().plan(self.query, stats).order, self.declared)
        fresh = Stats.collect([self.users, self.orders, self.items])
        self.assertEqual(fresh.stale([self.users, self.orders, self.items]), ())
        self.assertEqual(
            Planner().plan(self.query, fresh).order,
            Planner().plan(self.query, fresh).order,
        )

    def test_none_stats_fall_back(self):
        self.assertEqual(Planner().plan(self.query, None).order, self.declared)


class DeterminismTest(unittest.TestCase):
    def test_same_query_same_stats_same_plan(self):
        tables, joins = make_star(9, dim_count=4, fact_rows=800, dim_rows=[3, 5, 7, 9])
        query = Query(tables, joins)
        stats = Stats.collect(tables)
        first = Planner().plan(query, stats)
        for _ in range(5):
            self.assertEqual(Planner().plan(query, stats), first)
            self.assertEqual(Planner().components(query), Planner().components(query))


if __name__ == "__main__":
    unittest.main()
