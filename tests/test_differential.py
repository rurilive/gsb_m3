"""对拍测试：正式实现必须和朴素参考实现在各种乱序输入下逐字节一致。

参考实现在 tests/reference.py：按 trace_id 分组后照 parent_id 挂树。
这里覆盖乱序、缺父、重传、时钟回拨、成环与跨 trace 指父，外加
几千层深链和十万条 span 的性能验收。
"""

import random
import time
import unittest

import fixtures
import reference

from spanweave import build, critical_path, render_tree, snapshot, summary
from spanweave.store import SpanStore


def rec(span_id, parent_id, trace_id="tr", start_ms=0, end_ms=1,
        service="svc"):
    return fixtures.span_record(span_id, parent_id, start_ms, end_ms,
                                trace_id=trace_id, service=service)


def feed_in_batches(records, batches, rng):
    """把同一批记录切成若干批、按随机切点喂进 SpanStore。"""
    store = SpanStore()
    cuts = sorted(rng.sample(range(len(records) + 1), batches - 1))
    edges = [0] + cuts + [len(records)]
    for index in range(batches):
        store.feed(records[edges[index]:edges[index + 1]])
    return store.traces()


def assert_matches_reference(test_case, records, trees):
    """树形、渲染、快照、汇总、关键路径逐项和参考实现对拍。"""
    expected = reference.reference_build(records)
    test_case.assertEqual(reference.canonical(trees),
                          reference.canonical(expected))
    test_case.assertEqual(len(trees), len(expected))
    for tree, ref_tree in zip(trees, expected):
        test_case.assertEqual(render_tree(tree),
                              reference.reference_render(ref_tree))
        test_case.assertEqual(snapshot(tree),
                              reference.reference_snapshot(ref_tree))
        test_case.assertEqual(summary(tree),
                              reference.reference_summary(ref_tree))
        test_case.assertEqual(critical_path(tree),
                              reference.reference_critical_path(ref_tree))


class TestDeterminism(unittest.TestCase):
    """同一批 span 怎么喂都得逐字节一致。"""

    def test_same_tick_siblings_are_span_id_ordered(self):
        one = build([
            rec("root", None, start_ms=0, end_ms=100),
            rec("b", "root", start_ms=5, end_ms=6),
            rec("a", "root", start_ms=5, end_ms=6),
        ])
        other = build([
            rec("a", "root", start_ms=5, end_ms=6),
            rec("root", None, start_ms=0, end_ms=100),
            rec("b", "root", start_ms=5, end_ms=6),
        ])
        self.assertEqual(snapshot(one[0]), snapshot(other[0]))
        self.assertEqual(
            [c.span.span_id for c in one[0].roots[0].children],
            ["a", "b"])

    def test_all_permutations_of_fixture_are_identical(self):
        import itertools
        base = snapshot(build(fixtures.TRACE)[0])
        for permutation in itertools.permutations(fixtures.TRACE):
            self.assertEqual(snapshot(build(list(permutation))[0]), base)

    def test_split_batches_never_change_output(self):
        rng = random.Random(42)
        records = fixtures.TRACE * 2  # 带重传
        one_shot = snapshot(build(list(records))[0])
        for _ in range(20):
            shuffled = records[:]
            rng.shuffle(shuffled)
            trees = feed_in_batches(shuffled, 3, rng)
            self.assertEqual(snapshot(trees[0]), one_shot)


class TestMissingAndLateParents(unittest.TestCase):
    """缺父、迟到父、跨进程多根。"""

    def test_late_parent_gets_child_attached(self):
        store = SpanStore()
        store.feed([rec("child", "p", start_ms=9, end_ms=12)])
        store.feed([rec("p", None, start_ms=0, end_ms=20)])
        tree = store.traces()[0]
        self.assertEqual(tree.unresolved, [])
        self.assertEqual(
            [c.span.span_id for c in tree.roots[0].children], ["child"])

    def test_grandchild_before_grandparent_is_kept(self):
        store = SpanStore()
        store.feed([rec("gc", "c")])
        store.feed([rec("c", "p"), rec("p", None)])
        tree = store.traces()[0]
        self.assertEqual(tree.unresolved, [])
        self.assertEqual(
            [g.span.span_id
             for g in tree.roots[0].children[0].children],
            ["gc"])

    def test_missing_parent_is_unresolved_not_dropped(self):
        records = [
            rec("root", None),
            rec("orphan", "never-arrived", start_ms=3, end_ms=4),
            rec("orphan-child", "orphan", start_ms=3, end_ms=5),
        ]
        tree = build(records)[0]
        self.assertEqual(summary(tree)["spans"], 1)
        self.assertEqual(
            sorted(n.span.span_id for n in tree.unresolved),
            ["orphan", "orphan-child"])

    def test_span_without_parent_id_is_its_own_root(self):
        records = [
            rec("r1", None, start_ms=0, end_ms=10),
            rec("c1", "r1", start_ms=1, end_ms=2),
            rec("r2", None, start_ms=5, end_ms=9),
        ]
        tree = build(records)[0]
        self.assertEqual(len(tree.roots), 2)
        self.assertEqual(
            [n.span.span_id for n in tree.roots], ["r1", "r2"])

    def test_cross_trace_parent_is_unresolved(self):
        records = [
            rec("a", None, trace_id="tr-a"),
            rec("stray", "a", trace_id="tr-b"),
        ]
        trees = build(records)
        stray_trace = trees[1]
        self.assertEqual(stray_trace.trace_id, "tr-b")
        self.assertEqual(stray_trace.roots, [])
        self.assertEqual(
            [n.span.span_id for n in stray_trace.unresolved], ["stray"])

    def test_self_parent_is_unresolved(self):
        tree = build([rec("loop", "loop")])[0]
        self.assertEqual(tree.roots, [])
        self.assertEqual(
            [n.span.span_id for n in tree.unresolved], ["loop"])

    def test_cycle_members_and_feeder_are_unresolved(self):
        records = [
            rec("root", None),
            rec("x", "y"),
            rec("y", "x"),
            rec("z", "x"),  # 挂在环上，整条链都不能进树
        ]
        tree = build(records)[0]
        self.assertEqual([n.span.span_id for n in tree.roots], ["root"])
        self.assertEqual(
            sorted(n.span.span_id for n in tree.unresolved),
            ["x", "y", "z"])


class TestClockSkew(unittest.TestCase):
    """时钟回拨：负耗时按 0，条数进 clock_skew，关键路径不歪。"""

    def test_negative_duration_renders_zero(self):
        tree = build([
            rec("root", None, start_ms=0, end_ms=100),
            rec("bad", "root", start_ms=80, end_ms=0),
        ])[0]
        bad = tree.roots[0].children[0]
        self.assertEqual(bad.span.duration_ms, 0)
        self.assertIn("bad (0ms)", render_tree(tree))

    def test_clock_skew_count_includes_unresolved(self):
        tree = build([
            rec("root", None, start_ms=0, end_ms=10),
            rec("lost", "ghost", start_ms=9, end_ms=1),
        ])[0]
        self.assertEqual(summary(tree)["clock_skew"], 1)

    def test_critical_path_through_zero_duration_span(self):
        records = [
            rec("root", None, start_ms=0, end_ms=100),
            rec("a", "root", start_ms=10, end_ms=60),
            rec("b", "a", start_ms=80, end_ms=0),
            rec("c", "b", start_ms=90, end_ms=120),
        ]
        self.assertEqual(critical_path(build(records)[0]),
                         ["root", "a", "b", "c"])

    def test_negative_cost_cannot_lift_a_branch(self):
        records = [
            rec("root", None, start_ms=0, end_ms=100),
            rec("good", "root", start_ms=0, end_ms=30),
            rec("bad", "root", start_ms=0, end_ms=-50),
        ]
        self.assertEqual(critical_path(build(records)[0]),
                         ["root", "good"])

    def test_tie_break_is_lexicographic(self):
        records = [
            rec("root", None, start_ms=0, end_ms=10),
            rec("z", "root", start_ms=1, end_ms=6),
            rec("a", "root", start_ms=2, end_ms=7),
        ]
        self.assertEqual(critical_path(build(records)[0]),
                         ["root", "a"])


class TestRetransmission(unittest.TestCase):
    """重传只留先到的一条。"""

    def test_first_arrival_wins_even_with_different_payload(self):
        store = SpanStore()
        store.feed([rec("s1", None, start_ms=0, end_ms=10,
                        service="first")])
        store.feed([rec("s1", None, start_ms=99, end_ms=100,
                        service="second")])
        tree = store.traces()[0]
        self.assertEqual(tree.roots[0].span.service, "first")


def _generate_case(rng):
    """造一批故意脏的记录：多 trace、缺父、环、回拨、重传、同刻兄弟。"""
    trace_count = rng.randint(1, 3)
    trace_ids = ["tr-%d" % i for i in range(trace_count)]
    records = []
    live_ids = []
    for trace_id in trace_ids:
        count = rng.randint(1, 8)
        ids = ["%s-s%d" % (trace_id, i) for i in range(count)]
        for index, span_id in enumerate(ids):
            if index == 0 or rng.random() < 0.2:
                parent_id = None
            else:
                parent_id = ids[rng.randrange(index)]
            start_ms = rng.choice([0, 1, 1, 2, 5])
            end_ms = start_ms + rng.choice([0, 1, 3, 10])
            if rng.random() < 0.15:
                end_ms = start_ms - rng.randint(1, 9)
            records.append(rec(span_id, parent_id, trace_id=trace_id,
                               start_ms=start_ms, end_ms=end_ms))
            live_ids.append(span_id)
    # 随机摘掉一部分 span，制造永远不到的父
    for _ in range(rng.randint(0, 2)):
        victim = rng.choice(live_ids)
        records = [record for record in records
                   if record["span_id"] != victim]
    # 把几条 span 的父改成另一个 trace 的 id（跨进程错指）
    for record in rng.sample(records, min(2, len(records))):
        other = rng.choice(trace_ids)
        if other != record["trace_id"]:
            record["parent_id"] = "%s-s0" % other
    # 再造一个互指环
    if len(records) >= 2:
        a, b = rng.sample(records, 2)
        if a["trace_id"] == b["trace_id"]:
            a["parent_id"] = b["span_id"]
            b["parent_id"] = a["span_id"]
    # 重传：原样重复几条（先到的一份已在册，重复忽略）
    for record in rng.sample(records, min(3, len(records))):
        records.append(dict(record))
    return records


class TestFuzzAgainstReference(unittest.TestCase):
    """几百组随机脏数据下，正式实现与参考实现逐项对拍。"""

    def test_fuzz(self):
        rng = random.Random(20240921)
        for trial in range(300):
            records = _generate_case(rng)
            expected_trees = reference.reference_build(records)

            arrangements = [records, list(reversed(records))]
            shuffled = records[:]
            rng.shuffle(shuffled)
            arrangements.append(shuffled)

            snapshots = set()
            for arrangement in arrangements:
                store = SpanStore()
                cut = len(arrangement) // 2
                store.feed(arrangement[:cut])
                store.feed(arrangement[cut:])
                trees = store.traces()
                assert_matches_reference(self, records, trees)
                snapshots.add("\n".join(snapshot(t) for t in trees))
            self.assertEqual(
                len(snapshots), 1,
                "trial %d: 不同喂法结果不一致" % trial)

            self.assertEqual(
                reference.canonical(build(records)),
                reference.canonical(expected_trees))


class TestDeepChainAndScale(unittest.TestCase):
    """几千层深链渲染/统计不撞递归；十万 span 重建五秒内。"""

    def test_thousands_deep_chain(self):
        depth = 4000
        records = [rec("n0", None, start_ms=0, end_ms=depth * 2)]
        for i in range(1, depth + 1):
            records.append(rec("n%d" % i, "n%d" % (i - 1),
                               start_ms=i, end_ms=i + 1))
        shuffled = records[:]
        random.Random(7).shuffle(shuffled)
        tree = build(shuffled)[0]
        self.assertEqual(summary(tree)["max_depth"], depth)
        self.assertEqual(critical_path(tree)[-1], "n%d" % depth)
        rendered = render_tree(tree)
        self.assertEqual(len(rendered.splitlines()), depth + 1)
        self.assertIn("  " * depth + "n%d (1ms)" % depth, rendered)

    def test_hundred_thousand_spans_within_five_seconds(self):
        total = 100_000
        rng = random.Random(99)
        records = [
            rec("s0000000", None, start_ms=0, end_ms=1_000_000),
        ]
        for i in range(1, total):
            start_ms = rng.randint(0, 1_000_000)
            records.append(rec(
                "s%07d" % i,
                "s%07d" % rng.randrange(0, i),
                start_ms=start_ms,
                end_ms=start_ms + rng.randint(0, 100),
            ))
        rng.shuffle(records)

        began = time.perf_counter()
        store = SpanStore()
        store.feed(records)
        tree = store.traces()[0]
        stats = summary(tree)
        path = critical_path(tree)
        elapsed = time.perf_counter() - began

        self.assertEqual(stats["spans"], total)
        self.assertEqual(stats["roots"], 1)
        self.assertEqual(path[0], "s0000000")
        self.assertLess(elapsed, 5.0, "重建+统计+关键路径耗时 %.2fs" % elapsed)


if __name__ == "__main__":
    unittest.main()
