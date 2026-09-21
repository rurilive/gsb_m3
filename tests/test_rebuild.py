"""重建正确性的对拍与性能测试。

对拍用的参考实现完全独立书写：按 trace_id 分组、记录去重、找环、
挂树、排序、统计与关键路径全部在本文件里另写一遍，不调用
spanweave.builder，只在最后拿它的输出跟库实现逐项比对。

覆盖乱序、缺父（含跨 trace）、重传、时钟回拨、成环（自环/双环/
大环+引子）、同毫秒并列、多根多 trace 等情况。
"""

import random
import time
import unittest

from spanweave import (
    SpanStore,
    build,
    critical_path,
    render_tree,
    snapshot,
    summary,
)


# ---------------------------------------------------------------- 参考实现


class RefNode:
    def __init__(self, data):
        self.data = data
        self.children = []


def _duration(data):
    raw = data["end_ms"] - data["start_ms"]
    return raw if raw > 0 else 0


def _cycle_members(node_map):
    """返回环上 span_id 的集合。

    每个节点沿 parent 链走一遍，命中本次足迹说明成环，落点之后是环、
    之前是引子。结果记忆化在 state 里（True 在环上 / False 不在），
    走到已定论的节点时直接沿用它的结论，整体 O(n)。
    """
    state = {}
    for first_id in node_map:
        if first_id in state:
            continue
        path = []
        seen_at = {}
        cursor = first_id
        while cursor is not None and cursor in node_map and cursor not in state:
            if cursor in seen_at:
                cut = seen_at[cursor]
                for cyclic_id in path[cut:]:
                    state[cyclic_id] = True
                for feeder_id in path[:cut]:
                    state[feeder_id] = False
                path = []
                break
            seen_at[cursor] = len(path)
            path.append(cursor)
            cursor = node_map[cursor].data["parent_id"]
        for span_id in path:
            state[span_id] = False
    return {span_id for span_id, flag in state.items() if flag}


def reference_build(records):
    """参考重建：返回 {trace_id: {"roots","unresolved"}}。"""
    first_seen = {}
    for record in records:
        span_id = record["span_id"]
        if span_id in first_seen:
            continue
        first_seen[span_id] = {
            "trace_id": record["trace_id"],
            "span_id": span_id,
            "parent_id": record.get("parent_id") or None,
            "name": record.get("name") or span_id,
            "service": record.get("service") or "",
            "start_ms": record["start_ms"],
            "end_ms": record["end_ms"],
        }

    traces = {}
    for data in first_seen.values():
        traces.setdefault(data["trace_id"], {})[data["span_id"]] = RefNode(data)

    result = {}
    for trace_id in sorted(traces):
        node_map = traces[trace_id]
        cyclic = _cycle_members(node_map)
        roots, unresolved = [], []
        for node in node_map.values():
            parent_id = node.data["parent_id"]
            if parent_id is None:
                roots.append(node)
            elif node.data["span_id"] in cyclic or parent_id not in node_map:
                unresolved.append(node)
            else:
                node_map[parent_id].children.append(node)
        for node in node_map.values():
            node.children.sort(
                key=lambda ch: (ch.data["start_ms"], ch.data["span_id"]))
        roots.sort(key=lambda n: (n.data["start_ms"], n.data["span_id"]))
        unresolved.sort(key=lambda n: (n.data["start_ms"], n.data["span_id"]))
        result[trace_id] = {"roots": roots, "unresolved": unresolved}
    return result


def _forest(entries):
    """先序遍历入口森林，产出 (深度, RefNode)。"""
    stack = [(0, entry) for entry in reversed(entries)]
    while stack:
        depth, node = stack.pop()
        yield depth, node
        for child in reversed(node.children):
            stack.append((depth + 1, child))


def ref_render(entries):
    return "\n".join("%s%s (%dms)" % ("  " * depth, node.data["name"],
                                      _duration(node.data))
                     for depth, node in _forest(entries))


def ref_snapshot(trace_id, entries):
    lines = ["trace %s" % trace_id]
    for depth, node in _forest(entries):
        lines.append("%s%s %s %dms" % ("  " * depth, node.data["span_id"],
                                       node.data["service"] or "-",
                                       _duration(node.data)))
    return "\n".join(lines)


def ref_summary(ref):
    spans = total = skew = max_depth = 0
    for depth, node in _forest(ref["roots"]):
        spans += 1
        total += _duration(node.data)
        if node.data["end_ms"] < node.data["start_ms"]:
            skew += 1
        max_depth = max(max_depth, depth)
    unresolved = 0
    for _, node in _forest(ref["unresolved"]):
        unresolved += 1
        if node.data["end_ms"] < node.data["start_ms"]:
            skew += 1
    return {"spans": spans, "roots": len(ref["roots"]),
            "unresolved": unresolved, "clock_skew": skew,
            "total_ms": total, "max_depth": max_depth}


def ref_critical_path(ref):
    """枚举所有根到叶路径，取总耗时最大、并列时 id 序列字典序最小。"""
    candidates = []
    for root in ref["roots"]:
        stack = [(root, _duration(root.data), (root.data["span_id"],))]
        while stack:
            node, total, ids = stack.pop()
            if node.children:
                for child in node.children:
                    stack.append((child, total + _duration(child.data),
                                  ids + (child.data["span_id"],)))
            else:
                candidates.append((total, list(ids)))
    if not candidates:
        return []
    best_total = max(total for total, _ in candidates)
    return min((ids for total, ids in candidates if total == best_total),
               key=tuple)


def ref_shape(entries):
    def shape(node):
        return (node.data["span_id"],
                [shape(child) for child in node.children])
    return [shape(entry) for entry in entries]


# ---------------------------------------------------------------- 随机输入


def generate_case(rng, trace_count=3, max_spans=40):
    """造一份带各种坑的唯一记录列表。"""
    records = []
    all_ids = []
    id_trace = {}
    counter = 0
    for trace_index in range(trace_count):
        trace_id = "tr-%d" % trace_index
        n = rng.randint(1, max_spans)
        ids = []
        for _ in range(n):
            counter += 1
            span_id = "s%04d" % counter
            ids.append(span_id)
            all_ids.append(span_id)
            id_trace[span_id] = trace_id
        foreign_ids = [sid for sid in all_ids if id_trace[sid] != trace_id]
        for span_id in ids:
            choice = rng.random()
            if choice < 0.15:
                parent_id = None
            elif choice < 0.28:
                parent_id = rng.choice(["", "ghost-%d" % rng.randint(0, 99)])
            elif choice < 0.38 and foreign_ids:
                parent_id = rng.choice(foreign_ids)
            else:
                parent_id = rng.choice(ids)
            start = rng.choice([0, 1, 5, 10, 10, rng.randint(0, 50)])
            end = start + rng.randint(0, 30)
            if rng.random() < 0.15:
                end = start - rng.randint(1, 50)
            records.append({
                "trace_id": trace_id,
                "span_id": span_id,
                "parent_id": parent_id,
                "name": span_id if rng.random() < 0.5 else "op-" + span_id,
                "service": rng.choice(["svc", "api", ""]),
                "start_ms": start,
                "end_ms": end,
            })

    return records


def stale_duplicates(unique_records, rng, count=3):
    """造几条被篡改的迟到重传副本（不修改原件）。"""
    stale = []
    for record in rng.sample(unique_records, k=min(count, len(unique_records))):
        duplicate = dict(record)
        duplicate["end_ms"] += 999
        duplicate["name"] = duplicate["name"] + "-stale"
        stale.append(duplicate)
    return stale


def feed_in_batches(records, rng, batch_count, trailing=()):
    """打乱并分若干批喂进一个新 store；trailing 始终在最后一批追加。"""
    shuffled = list(records)
    rng.shuffle(shuffled)
    store = SpanStore()
    cuts = len(shuffled) - 1
    boundaries = (sorted(rng.sample(range(1, len(shuffled)),
                                   k=min(batch_count - 1, cuts)))
                  if cuts else [])
    start = 0
    for boundary in boundaries:
        store.feed(shuffled[start:boundary])
        start = boundary
    store.feed(shuffled[start:] + list(trailing))
    return store.traces()


# ---------------------------------------------------------------- 对拍主体


def lib_shape(node):
    return (node.span.span_id,
            [lib_shape(child) for child in node.children])


class TestDifferential(unittest.TestCase):
    def assert_tree_matches_ref(self, tree, refs):
        expected = refs[tree.trace_id]
        self.assertEqual([lib_shape(root) for root in tree.roots],
                         ref_shape(expected["roots"]))
        self.assertEqual([lib_shape(entry) for entry in tree.unresolved],
                         ref_shape(expected["unresolved"]))
        self.assertEqual(render_tree(tree), ref_render(expected["roots"]))
        self.assertEqual(snapshot(tree),
                         ref_snapshot(tree.trace_id, expected["roots"]))
        self.assertEqual(summary(tree), ref_summary(expected))
        self.assertEqual(critical_path(tree), ref_critical_path(expected))

    def test_random_cases_match_reference(self):
        rng = random.Random(20260921)
        for _ in range(60):
            unique = generate_case(rng)
            stale = stale_duplicates(unique, rng)
            refs = reference_build(unique)
            one_shot = build(list(unique) + stale)
            self.assertEqual([tree.trace_id for tree in one_shot], sorted(refs))
            for tree in one_shot:
                self.assert_tree_matches_ref(tree, refs)

            batched_a = feed_in_batches(unique, rng, 5, trailing=stale)
            batched_b = feed_in_batches(unique, rng, 12, trailing=stale)
            for trees in (batched_a, batched_b):
                self.assertEqual([tree.trace_id for tree in trees],
                                 sorted(refs))
                for tree in trees:
                    self.assert_tree_matches_ref(tree, refs)

            by_id = {tree.trace_id: tree for tree in one_shot}
            for trees in (batched_a, batched_b):
                for tree in trees:
                    other = by_id[tree.trace_id]
                    self.assertEqual(snapshot(tree), snapshot(other))
                    self.assertEqual(render_tree(tree), render_tree(other))
                    self.assertEqual(summary(tree), summary(other))
                    self.assertEqual(critical_path(tree),
                                     critical_path(other))

    def test_retransmit_first_record_wins(self):
        rng = random.Random(7)
        unique = generate_case(rng, trace_count=2, max_spans=20)
        stale = stale_duplicates(unique, rng)
        refs = reference_build(unique)
        for tree in feed_in_batches(unique, rng, 3, trailing=stale):
            self.assert_tree_matches_ref(tree, refs)


# ------------------------------------------------------- 契约样例与性能边界


def _rec(span_id, parent_id, start, end, name=None, service="svc",
         trace_id="tr-1"):
    return {"trace_id": trace_id, "span_id": span_id, "parent_id": parent_id,
            "name": name or span_id, "service": service,
            "start_ms": start, "end_ms": end}


class TestContractExamples(unittest.TestCase):
    def test_same_tick_siblings_order_independent(self):
        root = _rec("root", None, 0, 100, name="handle", service="api")
        first = build([root, _rec("b", "root", 10, 10),
                       _rec("a", "root", 10, 10)])[0]
        second = build([root, _rec("a", "root", 10, 10),
                        _rec("b", "root", 10, 10)])[0]
        self.assertEqual(snapshot(first), snapshot(second))
        self.assertEqual([n.span.span_id for n in first.roots[0].children],
                         ["a", "b"])

    def test_late_parent_gets_attached(self):
        store = SpanStore()
        store.feed([_rec("child", "root", 5, 9)])
        store.feed([_rec("root", None, 0, 10)])
        tree = store.traces()[0]
        self.assertEqual([n.span.span_id for n in tree.roots], ["root"])
        self.assertEqual([n.span.span_id for n in tree.roots[0].children],
                         ["child"])
        self.assertEqual(tree.unresolved, [])

    def test_never_arriving_parent_is_kept(self):
        child = _rec("child", "ghost", 5, 9)
        grandchild = _rec("grandchild", "child", 6, 8)
        tree = build([child, grandchild])[0]
        self.assertEqual(tree.roots, [])
        self.assertEqual(lib_shape(tree.unresolved[0]),
                         ("child", [("grandchild", [])]))
        self.assertEqual(summary(tree)["unresolved"], 2)
        self.assertEqual(critical_path(tree), [])

    def test_missing_parent_id_is_a_separate_root(self):
        records = [_rec("root", None, 0, 100, name="handle"),
                   _rec("child", "root", 5, 9),
                   _rec("foreign", None, 12, 15, service="worker")]
        tree = build(records)[0]
        self.assertEqual([n.span.span_id for n in tree.roots],
                         ["root", "foreign"])
        self.assertEqual(summary(tree)["roots"], 2)

    def test_cross_trace_parent_is_unresolved_not_grafted(self):
        records = [_rec("root", None, 0, 10, trace_id="tr-a"),
                   _rec("stray", "root", 1, 9, trace_id="tr-b")]
        trees = {tree.trace_id: tree for tree in build(records)}
        self.assertEqual([n.span.span_id for n in trees["tr-a"].roots], ["root"])
        self.assertEqual([n.span.span_id for n in trees["tr-b"].unresolved],
                         ["stray"])

    def test_negative_duration_counts_zero_and_skew(self):
        records = [_rec("root", None, 0, 100),
                   _rec("bad", "root", 80, 0)]
        tree = build(records)[0]
        stats = summary(tree)
        self.assertEqual(stats["clock_skew"], 1)
        self.assertEqual(stats["total_ms"], 100)
        self.assertIn("bad (0ms)", render_tree(tree))
        self.assertIn("bad svc 0ms", snapshot(tree))

    def test_self_cycle_is_cut_not_dropped(self):
        records = [_rec("root", None, 0, 100), _rec("loop", "loop", 1, 2),
                   _rec("feeder", "loop", 3, 4)]
        tree = build(records)[0]
        self.assertEqual(lib_shape(tree.roots[0]), ("root", []))
        self.assertEqual(lib_shape(tree.unresolved[0]),
                         ("loop", [("feeder", [])]))

    def test_pair_cycle_is_cut_and_kept(self):
        records = [_rec("a", "b", 0, 10), _rec("b", "a", 2, 8)]
        tree = build(records)[0]
        self.assertEqual(tree.roots, [])
        self.assertEqual(sorted(n.span.span_id for n in tree.unresolved),
                         ["a", "b"])
        for entry in tree.unresolved:
            self.assertEqual(entry.children, [])
        self.assertEqual(summary(tree)["unresolved"], 2)

    def test_critical_path_tie_picks_smallest_id_sequence(self):
        records = [_rec("root", None, 0, 10),
                   _rec("b", "root", 1, 11),
                   _rec("a", "root", 1, 11)]
        self.assertEqual(critical_path(build(records)[0]), ["root", "a"])

    def test_generator_feed_order_invariance(self):
        rng = random.Random(99)
        records = generate_case(rng, trace_count=4, max_spans=30)
        refs = reference_build(records)
        trees = build(record for record in records)
        for tree in trees:
            expected = refs[tree.trace_id]
            self.assertEqual(snapshot(tree),
                             ref_snapshot(tree.trace_id, expected["roots"]))


class TestPerformance(unittest.TestCase):
    def test_100k_spans_under_five_seconds(self):
        rng = random.Random(4242)
        n = 100_000
        records = [_rec("span-0", None, 0, 1_000_000)]
        for index in range(1, n):
            parent_index = rng.randint(0, index - 1)
            parent_id = "span-%d" % parent_index
            start = rng.randint(0, 1_000_000)
            end = start + rng.randint(0, 100)
            if rng.random() < 0.01:
                end = start - 1
            records.append(_rec("span-%d" % index, parent_id, start, end))
        rng.shuffle(records)

        store = SpanStore()
        started = time.perf_counter()
        for offset in range(0, len(records), 4096):
            store.feed(records[offset:offset + 4096])
        trees = store.traces()
        tree = trees[0]
        render_tree(tree)
        snapshot(tree)
        stats = summary(tree)
        critical_path(tree)
        elapsed = time.perf_counter() - started

        self.assertEqual(stats["spans"], n)
        self.assertLess(elapsed, 5.0, "重建耗时 %.2fs 超过 5s" % elapsed)

    def test_deep_chain_does_not_blow_the_stack(self):
        depth = 5000
        records = [_rec("d0", None, 0, depth + 1)]
        for index in range(1, depth + 1):
            records.append(_rec("d%d" % index, "d%d" % (index - 1),
                                index, index + 1))
        tree = build(reversed(records))[0]
        self.assertEqual(summary(tree)["max_depth"], depth)
        self.assertEqual(render_tree(tree).count("\n"), depth)
        self.assertEqual(critical_path(tree)[-1], "d%d" % depth)


if __name__ == "__main__":
    unittest.main()
