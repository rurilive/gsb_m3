"""全堆标记清除的行为基线：可达性、回收顺序、钩子语义、账目。"""

import unittest

from genheap import CollectionError, ObjectHeap, UnknownObject


def reachable_from(heap, roots):
    """朴素可达性：从根出发顺着槽位走，返回可达 oid 集合。

    不依赖堆的回收实现，测试里当作参照模型用。
    """
    seen = set()
    stack = [oid for oid in roots if heap.alive(oid)]
    while stack:
        oid = stack.pop()
        if oid in seen:
            continue
        seen.add(oid)
        for dst in heap.refs(oid):
            if dst not in seen:
                stack.append(dst)
    return seen


class Recorder:
    """on_free 回调记录器。"""

    def __init__(self):
        self.calls = []
        self.alive_at_call = []

    def __call__(self, heap, oid, kind, payload):
        self.calls.append((oid, kind, payload))
        self.alive_at_call.append(heap.alive(oid))


class TestReachability(unittest.TestCase):

    def test_unreachable_object_swept(self):
        heap = ObjectHeap()
        keep = heap.alloc("keep")
        trash = heap.alloc("trash")
        heap.add_root(keep)
        report = heap.collect()
        self.assertFalse(heap.alive(trash))
        self.assertEqual(heap.ids(), (keep,))
        self.assertEqual(report["marked"], 1)
        self.assertEqual(report["swept"], 1)

    def test_long_chain_kept_then_swept_after_root_dropped(self):
        heap = ObjectHeap()
        root = heap.alloc()
        heap.add_root(root)
        head = root
        for _ in range(3000):
            nxt = heap.alloc()
            heap.store(head, "next", nxt)
            head = nxt
        self.assertEqual(heap.collect()["swept"], 0)
        self.assertEqual(len(heap.ids()), 3001)
        heap.drop_root(root)
        report = heap.collect()
        self.assertEqual(report["swept"], 3001)
        self.assertEqual(heap.ids(), ())

    def test_unreachable_cycle_swept(self):
        heap = ObjectHeap()
        a = heap.alloc("a")
        b = heap.alloc("b")
        c = heap.alloc("c")
        heap.store(a, "next", b)
        heap.store(b, "next", c)
        heap.store(c, "next", a)
        report = heap.collect()
        self.assertEqual(report["swept"], 3)
        self.assertEqual(heap.ids(), ())

    def test_unreachable_self_loop_swept(self):
        heap = ObjectHeap()
        lone = heap.alloc("lone")
        heap.store(lone, "me", lone)
        report = heap.collect()
        self.assertEqual(report["swept"], 1)
        self.assertFalse(heap.alive(lone))

    def test_rooted_self_loop_kept(self):
        heap = ObjectHeap()
        lone = heap.alloc("lone")
        heap.store(lone, "me", lone)
        heap.add_root(lone)
        report = heap.collect()
        self.assertEqual(report["swept"], 0)
        self.assertTrue(heap.alive(lone))

    def test_shared_subgraph_kept_while_one_path_remains(self):
        heap = ObjectHeap()
        left = heap.alloc("left")
        right = heap.alloc("right")
        shared = heap.alloc("shared")
        heap.add_root(left)
        heap.add_root(right)
        heap.store(left, "s", shared)
        heap.store(right, "s", shared)
        heap.collect()
        self.assertTrue(heap.alive(shared))
        heap.drop_root(right)
        heap.store(left, "s", None)
        report = heap.collect()
        self.assertEqual(report["swept"], 2)
        self.assertEqual(heap.ids(), (left,))

    def test_matches_naive_model_on_mixed_graph(self):
        heap = ObjectHeap()
        root = heap.alloc("root")
        heap.add_root(root)
        nodes = [heap.alloc("n%d" % i) for i in range(12)]
        for i, oid in enumerate(nodes):
            heap.store(root, "child%d" % i, oid)
        heap.store(nodes[0], "peer", nodes[1])
        heap.store(nodes[1], "peer", nodes[2])
        heap.store(nodes[2], "peer", nodes[0])
        heap.store(nodes[5], "me", nodes[5])
        for i in range(9, 12):
            heap.store(nodes[i], "peer", nodes[i - 1])
        for gap in ("child3", "child4", "child7"):
            heap.store(root, gap, None)
        report = heap.collect()
        self.assertEqual(set(heap.ids()), reachable_from(heap, heap.roots()))
        self.assertEqual(report["swept"], 3)


class TestHooks(unittest.TestCase):

    def test_hooks_fire_in_ascending_oid_after_removal(self):
        rec = Recorder()
        heap = ObjectHeap(on_free=rec)
        doomed = [heap.alloc("t%d" % i, i) for i in range(3)]
        heap.collect()
        self.assertEqual([oid for oid, _, _ in rec.calls], doomed)
        self.assertEqual([kind for _, kind, _ in rec.calls], ["t0", "t1", "t2"])
        self.assertEqual([payload for _, _, payload in rec.calls], [0, 1, 2])
        self.assertEqual(rec.alive_at_call, [False, False, False])

    def test_alloc_inside_hook_survives_this_round(self):
        born = []

        def hook(heap, oid, kind, payload):
            born.append(heap.alloc("late"))

        heap = ObjectHeap(on_free=hook)
        heap.alloc("trash")
        report = heap.collect()
        self.assertEqual(len(born), 1)
        self.assertTrue(heap.alive(born[0]))
        self.assertEqual(report["swept"], 1)
        heap.collect()
        self.assertFalse(heap.alive(born[0]))

    def test_root_change_inside_hook_takes_effect_next_round(self):
        state = {}

        def hook(heap, oid, kind, payload):
            if oid != state["victim"]:
                heap.drop_root(state["victim"])

        heap = ObjectHeap(on_free=hook)
        state["victim"] = heap.alloc("victim")
        heap.add_root(state["victim"])
        heap.alloc("trash")
        report = heap.collect()
        self.assertEqual(report["swept"], 1)
        self.assertTrue(heap.alive(state["victim"]))
        self.assertEqual(heap.roots(), ())
        heap.collect()
        self.assertFalse(heap.alive(state["victim"]))

    def test_store_to_freed_oid_inside_hook_rejected(self):
        state = {}

        def hook(heap, oid, kind, payload):
            try:
                heap.store(state["keeper"], "bad", oid)
            except UnknownObject as exc:
                state["error"] = exc

        heap = ObjectHeap(on_free=hook)
        keeper = heap.alloc("keeper")
        state["keeper"] = keeper
        heap.add_root(keeper)
        heap.alloc("trash")
        heap.collect()
        self.assertIn("error", state)
        self.assertEqual(heap.slots(keeper), ())

    def test_recursive_collect_inside_hook_rejected(self):
        state = {}

        def hook(heap, oid, kind, payload):
            try:
                heap.collect()
            except CollectionError as exc:
                state["error"] = exc

        heap = ObjectHeap(on_free=hook)
        heap.alloc("trash")
        report = heap.collect()
        self.assertIn("error", state)
        self.assertEqual(report["swept"], 1)
        self.assertEqual(heap.stats()["collections"], 1)

    def test_hook_exception_propagates_and_heap_recovers(self):
        calls = []

        def hook(heap, oid, kind, payload):
            calls.append(oid)
            if len(calls) == 2:
                raise RuntimeError("boom")

        heap = ObjectHeap(on_free=hook)
        for _ in range(4):
            heap.alloc("trash")
        with self.assertRaises(RuntimeError):
            heap.collect()
        self.assertEqual(calls, [1, 2])
        self.assertEqual(heap.ids(), ())
        self.assertEqual(heap.stats()["freed"], 4)

        root = heap.alloc("root")
        heap.add_root(root)
        heap.store(root, "me", root)
        report = heap.collect()
        self.assertEqual(report["swept"], 0)
        self.assertEqual(heap.ids(), (root,))

    def test_recursive_collect_error_propagates(self):
        def hook(heap, oid, kind, payload):
            heap.collect()

        heap = ObjectHeap(on_free=hook)
        heap.alloc("trash")
        with self.assertRaises(CollectionError):
            heap.collect()
        self.assertEqual(heap.ids(), ())
        self.assertEqual(heap.stats()["alive"], 0)


class TestAccounting(unittest.TestCase):

    def test_report_counts(self):
        heap = ObjectHeap()
        root = heap.alloc()
        heap.add_root(root)
        a = heap.alloc()
        b = heap.alloc()
        heap.store(root, "a", a)
        heap.store(a, "b", b)
        heap.alloc()
        heap.alloc()
        report = heap.collect()
        self.assertEqual(report["marked"], 3)
        self.assertEqual(report["swept"], 2)
        self.assertEqual(report["scanned"], 3)

    def test_stats_are_cumulative(self):
        heap = ObjectHeap()
        root = heap.alloc()
        heap.add_root(root)
        heap.alloc()
        heap.collect()
        heap.alloc()
        heap.collect()
        stats = heap.stats()
        self.assertEqual(stats["allocated"], 3)
        self.assertEqual(stats["freed"], 2)
        self.assertEqual(stats["collections"], 2)
        self.assertEqual(stats["scanned"], 2)
        self.assertEqual(stats["alive"], 1)
        self.assertEqual(stats["roots"], 1)

    def test_second_collect_is_idle_without_changes(self):
        heap = ObjectHeap()
        root = heap.alloc()
        heap.add_root(root)
        heap.store(root, "me", root)
        heap.collect()
        before = heap.stats()["scanned"]
        report = heap.collect()
        self.assertEqual(report["swept"], 0)
        self.assertEqual(heap.stats()["scanned"], before + 1)


if __name__ == "__main__":
    unittest.main()
