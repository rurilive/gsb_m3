"""IncrementalTopo 的防回归测试。

把事故里暴露的几条口径钉死：
- 随机增删序列下 order()/is_acyclic() 与 reference 全量实现逐项一致；
- 次序只由当前图和节点加入先后决定，跟增删路径无关；
- 同一条边在日志里重复出现，入度不歪、删不穿、结果不变；
- 环标记不靠记“封环的那条边”，删任何一条破环边都立刻恢复；
- 大长链中间删一条边是局部修补，不得退化成整图重算。
"""

import random
import time
import unittest

from topoflow.engine import IncrementalTopo
from topoflow.reference import (
    CycleError,
    order_problems,
    reference_is_acyclic,
    reference_order,
)


def build_fresh(nodes, edges):
    engine = IncrementalTopo()
    for node in nodes:
        engine.add_node(node)
    engine.add_edges(edges)
    return engine


class TestRandomDifferential(unittest.TestCase):
    """随机增删 + 随机查询，每一步都跟全量参考对拍。"""

    def _run(self, seed, n_nodes, n_ops, query_every):
        rng = random.Random(seed)
        engine = IncrementalTopo()
        nodes = list(range(n_nodes))
        rng.shuffle(nodes)
        for node in nodes[:n_nodes // 2 + 1]:
            engine.add_node(node)
        live = set()

        for step in range(n_ops):
            u = rng.randrange(n_nodes)
            v = rng.randrange(n_nodes)
            roll = rng.random()
            if roll < 0.55:
                self.assertEqual(engine.add_edge(u, v), (u, v) not in live)
                live.add((u, v))
            elif roll < 0.8:
                self.assertEqual(engine.remove_edge(u, v), (u, v) in live)
                live.discard((u, v))
            elif roll < 0.9:
                # 故意重复的批量日志
                batch = [(rng.randrange(n_nodes), rng.randrange(n_nodes))
                         for _ in range(rng.randrange(1, 5))]
                engine.add_edges(batch + batch)
                live.update(batch)
            else:
                batch = [(rng.randrange(n_nodes), rng.randrange(n_nodes))
                         for _ in range(rng.randrange(1, 5))]
                engine.remove_edges(batch + batch)
                live.difference_update(batch)

            if step % query_every != 0 and step != n_ops - 1:
                continue

            graph = engine.snapshot()
            ref_acyclic = reference_is_acyclic(graph)
            self.assertIs(engine.is_acyclic(), ref_acyclic)
            for node in graph.nodes():
                self.assertEqual(engine.in_degree(node), graph.in_degree(node))
            if ref_acyclic:
                ref_order = reference_order(graph)
                got = engine.order()
                self.assertEqual(got, ref_order)
                self.assertEqual(order_problems(graph, got), [])
                for index, node in enumerate(got):
                    self.assertEqual(engine.rank(node), index)
            else:
                with self.assertRaises(CycleError):
                    engine.order()

    def test_dense_random_scripts(self):
        for seed in range(60):
            self._run(seed, 18, 150, 1)

    def test_sparse_larger_graphs(self):
        for seed in range(60, 90):
            rng = random.Random(seed)
            self._run(seed, rng.randrange(40, 120),
                      rng.randrange(200, 500), rng.choice((2, 5, 11)))


class TestOrderIsHistoryIndependent(unittest.TestCase):
    """次序只由当前图和节点加入先后决定，中途怎么增删都不许漂移。"""

    def _final_edges(self, rng):
        n = 14
        edges = set()
        for _ in range(30):
            u, v = rng.randrange(n), rng.randrange(n)
            if u != v and v != 0 and u != n - 1:
                edges.add((u, v))
        # 保证最终图无环：只保留 u < v 的边
        return sorted((u, v) for u, v in edges if u < v)

    def test_detour_matches_straight_build(self):
        rng = random.Random(4242)
        for _ in range(25):
            final = self._final_edges(rng)

            straight = IncrementalTopo()
            for i in range(14):
                straight.add_node(i)
            straight.add_edges(final)
            want = straight.order()
            self.assertEqual(want, reference_order(straight.snapshot()))

            # 绕路版本：中间乱序加/删一堆边（包括最终不存在的边），
            # 节点加入顺序与最终边集完全一样。
            detour = IncrementalTopo()
            for i in range(14):
                detour.add_node(i)
            final_set = set(final)
            pool = [(u, v) for u in range(14) for v in range(14) if u != v]
            rng.shuffle(pool)
            for u, v in pool[:20]:
                detour.add_edge(u, v)
                detour.is_acyclic()
                if (u, v) not in final_set:
                    detour.remove_edge(u, v)
            for u, v in final:
                detour.add_edge(u, v)
            for u, v in list(detour.snapshot().edges()):
                if (u, v) not in final_set:
                    detour.remove_edge(u, v)
            self.assertEqual(detour.order(), want)

    def test_replay_twice_is_identical(self):
        script = [
            ("add", 0, 1), ("add", 2, 1), ("add", 2, 3),
            ("add", 1, 4), ("remove", 0, 1), ("add", 0, 4),
            ("add", 3, 5), ("remove", 2, 1), ("add", 2, 6),
            ("add", 6, 5), ("remove", 0, 4), ("add", 0, 2),
        ]
        orders = []
        for _ in range(2):
            engine = IncrementalTopo()
            for i in range(7):
                engine.add_node(i)
            for op, u, v in script:
                if op == "add":
                    engine.add_edge(u, v)
                else:
                    engine.remove_edge(u, v)
                engine.order() if engine.is_acyclic() else None
            orders.append(engine.order())
        self.assertEqual(orders[0], orders[1])
        # 以每条边最后一次出现的操作为准，直接重建最终图对拍
        final_engine = IncrementalTopo()
        for i in range(7):
            final_engine.add_node(i)
        final_edges = []
        seen = {}
        for op, u, v in script:
            seen[(u, v)] = op
        for (u, v), op in seen.items():
            if op == "add":
                final_edges.append((u, v))
        final_engine.add_edges(final_edges)
        self.assertEqual(orders[0], final_engine.order())


class TestDuplicateJournalEntries(unittest.TestCase):
    """同一条边在日志里重复出现，账本不能歪。"""

    def test_duplicate_adds_count_once(self):
        engine = IncrementalTopo()
        for _ in range(5):
            engine.add_edge("a", "b")
        self.assertTrue(engine.add_edge("a", "c"))
        self.assertEqual(engine.in_degree("b"), 1)
        self.assertEqual(engine.snapshot().edge_count(), 2)
        self.assertEqual(engine.order(), reference_order(engine.snapshot()))

    def test_duplicate_removals_never_go_negative(self):
        engine = build_fresh(["a", "b", "c", "d"],
                             [("a", "c"), ("b", "c"), ("c", "d")])
        engine.order()
        engine.remove_edges([("a", "c"), ("a", "c"), ("a", "c")])
        self.assertEqual(engine.in_degree("c"), 1)
        engine.remove_edge("a", "c")
        self.assertEqual(engine.in_degree("c"), 1)  # 本来就只剩 b
        self.assertFalse(engine.remove_edge("a", "c"))
        engine.remove_edges([("b", "c"), ("b", "c"), ("x", "c")])
        self.assertEqual(engine.in_degree("c"), 0)
        self.assertTrue(engine.is_acyclic())
        self.assertEqual(engine.order(), reference_order(engine.snapshot()))

    def test_remove_then_readd_restores_order(self):
        chain = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")]
        engine = IncrementalTopo()
        engine.add_edges(chain)
        before = engine.order()
        engine.remove_edges(chain + chain)
        engine.add_edges(chain + chain)
        self.assertEqual(engine.in_degree("e"), 1)
        self.assertEqual(engine.order(), before)


class TestCycleBookkeeping(unittest.TestCase):
    """环状态必须跟当前图走，不能粘着某个历史标记。"""

    def test_removing_any_cycle_edge_recovers(self):
        engine = build_fresh(list("abcdef"),
                             [("a", "b"), ("b", "c"), ("c", "d"), ("e", "f")])
        engine.order()
        engine.add_edge("d", "a")
        self.assertFalse(engine.is_acyclic())
        # 先删一条跟封环完全无关的尾巴：环必须还在
        self.assertTrue(engine.remove_edge("e", "f"))
        self.assertFalse(engine.is_acyclic())
        # 再删掉环上的任意一条边（不是记录的“最后一条”），环立即清
        self.assertTrue(engine.remove_edge("b", "c"))
        self.assertTrue(engine.is_acyclic())
        self.assertEqual(engine.order(), reference_order(engine.snapshot()))

    def test_new_cycle_while_cyclic_still_detected(self):
        engine = build_fresh(["x", "y"], [("x", "y")])
        engine.add_edge("y", "x")
        self.assertFalse(engine.is_acyclic())
        engine.remove_edge("x", "y")  # 环破了，图退化成 y -> x 无环
        self.assertTrue(engine.is_acyclic())
        engine.add_edges([("x", "z"), ("z", "y")])  # 又封回环 x->z->y->x
        self.assertFalse(engine.is_acyclic())
        with self.assertRaises(CycleError):
            engine.order()

    def test_self_loop(self):
        engine = IncrementalTopo()
        engine.add_node("a")
        engine.add_edge("a", "a")
        self.assertFalse(engine.is_acyclic())
        self.assertTrue(engine.remove_edge("a", "a"))
        self.assertTrue(engine.is_acyclic())


class TestTieBreakPinned(unittest.TestCase):
    """同层节点必须严格按节点加入先后出队。"""

    def test_tie_break_matches_reference_on_remove(self):
        # 初始：a 挡住 seq 很小的 c；删掉入边后 c 必须抢到最前。
        engine = IncrementalTopo()
        for node in ("c", "b", "a", "d"):
            engine.add_node(node)
        engine.add_edges([("a", "c"), ("b", "d")])
        self.assertEqual(engine.order(), ["b", "a", "c", "d"])
        engine.remove_edge("a", "c")
        self.assertEqual(engine.order(), ["c", "b", "a", "d"])

    def test_backward_add_reorders_to_canonical(self):
        engine = IncrementalTopo()
        for node in range(6):
            engine.add_node(node)
        engine.add_edges([(0, 5), (2, 4)])
        self.assertEqual(engine.order(), [0, 1, 2, 3, 4, 5])
        engine.add_edge(5, 3)  # 反向边：3 要挪到 5 后面
        self.assertEqual(engine.order(), reference_order(engine.snapshot()))
        self.assertEqual(engine.order(), [0, 1, 2, 4, 5, 3])


class TestLocalRepairPerformance(unittest.TestCase):
    """大长链中间删一条边只做局部修补，耗时低一个数量级以上。"""

    def test_chain_middle_remove_is_local(self):
        size = 20000
        pairs = [("t%d" % i, "t%d" % (i + 1)) for i in range(size - 1)]
        engine = IncrementalTopo()
        engine.add_edges(pairs)
        engine.order()
        mid = size // 2

        start = time.perf_counter()
        engine.remove_edge("t%d" % mid, "t%d" % (mid + 1))
        engine.order()
        local = time.perf_counter() - start

        graph = engine.snapshot()
        start = time.perf_counter()
        reference_order(graph)
        full = time.perf_counter() - start

        self.assertLess(local, full * 0.1)
        # 序内容本身也要跟参考一致
        self.assertEqual(engine.order(), reference_order(graph))

    def test_many_scattered_removals_stay_local(self):
        # 一批散落在长链各处的删边不能取窗口并集退化成整图重算。
        size = 20000
        pairs = [("t%d" % i, "t%d" % (i + 1)) for i in range(size - 1)]
        engine = IncrementalTopo()
        engine.add_edges(pairs)
        engine.order()
        rng = random.Random(11)
        cuts = sorted(rng.sample(range(size - 1), 200))

        start = time.perf_counter()
        engine.remove_edges([("t%d" % i, "t%d" % (i + 1)) for i in cuts])
        engine.order()
        local = time.perf_counter() - start

        graph = engine.snapshot()
        start = time.perf_counter()
        ref = reference_order(graph)
        full = time.perf_counter() - start

        self.assertLess(local, full * 0.25)
        self.assertEqual(engine.order(), ref)


if __name__ == "__main__":
    unittest.main()
