"""GenerationalHeap 行为基线。

覆盖：晋升、minor/major 分工、写屏障与记录集边界、长随机序列与
ObjectHeap 对拍、major 后存活集合一致、五万老年代下 minor 扫描量
不随老年代涨、漏记写屏障被 verify 炸出来、收集中途 alloc / 动根 /
钩子复活都不破坏本轮结果。
"""

import random
import unittest

from genheap import (
    BarrierError,
    CollectionError,
    GenerationalHeap,
    ObjectHeap,
    OLD,
    UnknownObject,
    YOUNG,
)


def reachable(heap, roots):
    """参照模型：从 roots 朴素可达集合，不依赖任何 GC 实现。"""
    seen = set()
    stack = [oid for oid in roots if heap.alive(oid)]
    while stack:
        oid = stack.pop()
        if oid in seen:
            continue
        seen.add(oid)
        stack.extend(heap.refs(oid))
    return seen


class TestGenerations(unittest.TestCase):

    def test_new_objects_are_young(self):
        heap = GenerationalHeap()
        oid = heap.alloc("page", {"n": 1})
        self.assertEqual(heap.generation(oid), YOUNG)
        self.assertEqual(heap.generations(), {"young": 1, "old": 0})

    def test_survive_promote_after_rounds_then_old(self):
        heap = GenerationalHeap(promote_after=3)
        oid = heap.alloc()
        heap.add_root(oid)
        for _ in range(2):
            report = heap.minor_collect()
            self.assertEqual(heap.generation(oid), YOUNG)
            self.assertEqual(report["promoted"], [])
        report = heap.minor_collect()
        self.assertEqual(heap.generation(oid), OLD)
        self.assertEqual(report["promoted"], [oid])
        self.assertEqual(heap.generations(), {"young": 0, "old": 1})

    def test_young_garbage_swept_by_minor(self):
        heap = GenerationalHeap(promote_after=3)
        keeper = heap.alloc()
        heap.add_root(keeper)
        ephemeral = heap.alloc()
        # ephemeral 不可达，第一轮 minor 就该走
        report = heap.minor_collect()
        self.assertFalse(heap.alive(ephemeral))
        self.assertTrue(heap.alive(keeper))
        self.assertEqual(report["kind"], "minor")

    def test_invalid_promote_after_rejected(self):
        for bad in (0, -1, 2.0, "2", None):
            with self.assertRaises((ValueError, TypeError)):
                GenerationalHeap(promote_after=bad)

    def test_invalid_major_threshold_rejected(self):
        for bad in (0, -1):
            with self.assertRaises(ValueError):
                GenerationalHeap(major_threshold=bad)

    def test_generation_of_unknown_oid_rejected(self):
        heap = GenerationalHeap()
        with self.assertRaises(UnknownObject):
            heap.generation(999)
        oid = heap.alloc()
        heap.major_collect()
        with self.assertRaises(UnknownObject):
            heap.generation(oid)

    def test_promote_after_one_promotes_immediately(self):
        heap = GenerationalHeap(promote_after=1)
        oid = heap.alloc()
        heap.add_root(oid)
        heap.minor_collect()
        self.assertEqual(heap.generation(oid), OLD)


class TestMinorCollect(unittest.TestCase):

    def test_minor_sweeps_only_young_garbage(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        anchor = heap.alloc("anchor")
        heap.add_root(anchor)
        heap.minor_collect()
        self.assertEqual(heap.generation(anchor), OLD)

        # 老年代垃圾：minor 一轮轮过都不许碰
        old_garbage = heap.alloc("old-garbage")
        heap.add_root(old_garbage)
        heap.minor_collect()
        self.assertEqual(heap.generation(old_garbage), OLD)
        heap.drop_root(old_garbage)
        for _ in range(3):
            report = heap.minor_collect()
            self.assertEqual(report["swept"], 0)
            self.assertTrue(heap.alive(old_garbage))

        # 年轻代垃圾当场收掉
        trash = heap.alloc("trash")
        report = heap.minor_collect()
        self.assertEqual(report["kind"], "minor")
        self.assertFalse(heap.alive(trash))
        self.assertTrue(heap.alive(old_garbage))
        self.assertEqual(report["swept"], 1)

        # 老年代垃圾等 major
        report = heap.major_collect()
        self.assertFalse(heap.alive(old_garbage))

    def test_minor_does_not_walk_into_old_generation(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        chain_head = heap.alloc()
        heap.store(elder, "chain", chain_head)
        cur = chain_head
        for _ in range(10):
            nxt = heap.alloc()
            heap.store(cur, "next", nxt)
            cur = nxt
        heap.major_collect()
        self.assertEqual(heap.generations()["old"], 12)
        # elder->chain_head 是老->老，记录集为空
        self.assertEqual(heap.remembered(), ())

        baby = heap.alloc()
        report = heap.minor_collect()
        self.assertFalse(heap.alive(baby))
        self.assertEqual(report["young_scanned"], 0)
        self.assertEqual(report["old_scanned"], 0)


class TestWriteBarrier(unittest.TestCase):

    def test_old_to_young_keeps_young_alive(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc("elder")
        heap.add_root(elder)
        heap.minor_collect()
        baby = heap.alloc("baby")
        orphan = heap.alloc("orphan")
        heap.store(elder, "baby", baby)
        self.assertEqual(heap.remembered(), (elder,))
        report = heap.minor_collect()
        self.assertTrue(heap.alive(baby))
        self.assertFalse(heap.alive(orphan))
        self.assertEqual(report["swept"], 1)

    def test_remembered_set_folded_by_source(self):
        heap = GenerationalHeap(promote_after=1)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        for _ in range(500):
            target = heap.alloc()
            heap.store(elder, "hot", target)
        self.assertEqual(len(heap.remembered()), 1)

    def test_remembered_set_shrinks_when_ref_cleared(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        baby = heap.alloc()
        heap.store(elder, "baby", baby)
        self.assertEqual(heap.remembered(), (elder,))
        heap.store(elder, "baby", None)
        self.assertEqual(heap.remembered(), ())
        heap.minor_collect()
        self.assertFalse(heap.alive(baby))

    def test_remembered_set_bounded_by_old_generation(self):
        heap = GenerationalHeap(promote_after=1)
        dummy_root = heap.alloc()
        heap.add_root(dummy_root)
        heap.minor_collect()
        elders = []
        for _ in range(20):
            e = heap.alloc()
            heap.add_root(e)
            elders.append(e)
        heap.minor_collect()
        for i in range(2000):
            e = elders[i % 20]
            target = heap.alloc()
            heap.store(e, "slot%d" % (i % 8), target)
        self.assertLessEqual(len(heap.remembered()), len(elders))

    def test_old_to_old_does_not_register(self):
        heap = GenerationalHeap(promote_after=1)
        a = heap.alloc()
        b = heap.alloc()
        heap.add_root(a)
        heap.add_root(b)
        heap.minor_collect()
        heap.store(a, "b", b)
        self.assertEqual(heap.remembered(), ())

    def test_young_to_old_needs_no_barrier(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        baby = heap.alloc()
        heap.store(baby, "back", elder)
        self.assertEqual(heap.remembered(), ())
        heap.minor_collect()
        self.assertFalse(heap.alive(baby))

    def test_promoted_object_with_young_target_is_remembered(self):
        heap = GenerationalHeap(promote_after=2, verify=True)
        parent = heap.alloc()
        heap.add_root(parent)
        child = heap.alloc()
        heap.store(parent, "child", child)
        heap.minor_collect()
        # 第一轮：父子都还年轻，年龄 1
        self.assertEqual(heap.generation(parent), YOUNG)
        self.assertEqual(heap.generation(child), YOUNG)
        heap.minor_collect()
        # 第二轮：父子一起到年龄晋升
        self.assertEqual(heap.generation(parent), OLD)
        self.assertEqual(heap.generation(child), OLD)

    def test_promoted_old_pointing_new_baby_is_remembered(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        parent = heap.alloc()
        heap.add_root(parent)
        heap.minor_collect()
        self.assertEqual(heap.generation(parent), OLD)
        baby = heap.alloc()
        heap.store(parent, "baby", baby)
        self.assertIn(parent, heap.remembered())
        heap.minor_collect()
        self.assertTrue(heap.alive(baby))
        heap.minor_collect()
        self.assertTrue(heap.alive(baby))

    def test_old_remembered_without_root_still_keeps_young(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        baby = heap.alloc()
        heap.store(elder, "b", baby)
        heap.drop_root(elder)
        heap.minor_collect()
        self.assertTrue(heap.alive(baby))


class TestMajorCollect(unittest.TestCase):

    def test_major_sweeps_old_garbage(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        a = heap.alloc()
        b = heap.alloc()
        c = heap.alloc()
        heap.store(a, "b", b)
        heap.store(b, "c", c)
        heap.store(c, "a", a)
        heap.add_root(a)
        heap.minor_collect()
        self.assertEqual(set(heap.ids()), {a, b, c})
        heap.drop_root(a)
        self.assertEqual(heap.minor_collect()["swept"], 0)
        report = heap.major_collect()
        self.assertEqual(report["kind"], "major")
        self.assertEqual(report["swept"], 3)
        self.assertEqual(heap.ids(), ())

    def test_major_rebuilds_remembered_set(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        baby = heap.alloc()
        heap.store(elder, "baby", baby)
        heap._remembered.add(999999)
        heap.major_collect()
        # baby survive 了两轮 minor + major，major 时年龄到 2，随父同在老年代
        self.assertEqual(heap.remembered(), ())
        self.assertTrue(heap.alive(baby))

    def test_major_agrees_with_mark_sweep_on_survivors(self):
        for seed in range(5):
            rng = random.Random(seed)
            promote_after = rng.choice([1, 2, 3])
            gen = GenerationalHeap(promote_after=promote_after)
            ref = ObjectHeap()
            ops = _random_world_ops(rng)
            _apply_ops(gen, ops)
            _apply_ops(ref, ops)
            for _ in range(rng.randint(1, 4)):
                gen.minor_collect()
            gen.major_collect()
            ref.collect()
            self.assertEqual(
                set(gen.ids()), set(ref.ids()),
                "seed=%s survivor mismatch" % seed)

    def test_collect_auto_major_after_old_grows_enough(self):
        heap = GenerationalHeap(promote_after=1, major_threshold=3)
        for _ in range(3):
            oid = heap.alloc()
            heap.add_root(oid)
            heap.collect()
        report = heap.collect()
        self.assertEqual(report["kind"], "major")
        self.assertEqual(heap.stats()["major_collections"], 1)
        report = heap.collect()
        self.assertEqual(report["kind"], "minor")


class TestCrossGenerationGraphs(unittest.TestCase):

    def test_cross_generation_cycle_kept(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        youth = heap.alloc()
        heap.store(elder, "down", youth)
        heap.store(youth, "up", elder)
        heap.minor_collect()
        self.assertTrue(heap.alive(youth))
        self.assertTrue(heap.alive(elder))
        heap.minor_collect()
        self.assertEqual(heap.remembered(), ())

    def test_dropped_cross_generation_cycle_swept_by_major(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        youth = heap.alloc()
        heap.store(elder, "down", youth)
        heap.store(youth, "up", elder)
        heap.minor_collect()
        heap.minor_collect()
        heap.drop_root(elder)
        heap.minor_collect()
        self.assertTrue(heap.alive(elder))
        heap.major_collect()
        self.assertFalse(heap.alive(elder))
        self.assertFalse(heap.alive(youth))

    def test_diamond_across_generations(self):
        heap = GenerationalHeap(promote_after=2, verify=True)
        top = heap.alloc()
        heap.add_root(top)
        heap.minor_collect()
        heap.minor_collect()
        self.assertEqual(heap.generation(top), OLD)
        left = heap.alloc()
        right = heap.alloc()
        bottom = heap.alloc()
        heap.store(top, "l", left)
        heap.store(top, "r", right)
        heap.store(left, "b", bottom)
        heap.store(right, "b", bottom)
        heap.minor_collect()
        self.assertTrue(heap.alive(bottom))
        self.assertEqual(heap.generation(bottom), YOUNG)
        heap.store(left, "b", None)
        heap.store(right, "b", None)
        heap.minor_collect()
        self.assertFalse(heap.alive(bottom))


def _random_world_ops(rng, n=60):
    """生成一份与堆无关的操作脚本，两个堆各演一遍。"""
    ops = [("alloc", "n%d" % i) for i in range(n)]
    for i in range(n):
        if i < 8 or rng.random() < 0.15:
            ops.append(("root", i + 1))
    for i in range(n):
        for slot in ("a", "b", "c"):
            if rng.random() < 0.35:
                ops.append(("store", i + 1, slot, rng.randint(1, n)))
    return ops


def _apply_ops(heap, ops):
    oids = {}
    for op in ops:
        if op[0] == "alloc":
            oid = heap.alloc(op[1])
            oids[oid] = oid
        elif op[0] == "root":
            heap.add_root(op[1])
        else:
            heap.store(op[1], op[2], op[3])


class TestDifferentialFuzz(unittest.TestCase):
    """长随机序列与全量标记清除对拍：任何时刻可达对象不许误收。"""

    def test_random_sequence_never_frees_reachable(self):
        for seed in range(40):
            rng = random.Random(seed)
            promote_after = rng.choice([1, 2, 3])
            gen = GenerationalHeap(promote_after=promote_after, verify=True)
            ref = ObjectHeap()
            live = []

            def drop_one(some_id):
                if some_id in ref.roots():
                    ref.drop_root(some_id)
                if some_id in gen.roots():
                    gen.drop_root(some_id)

            for step in range(900):
                roll = rng.random()
                if roll < 0.30 or not live:
                    kind = rng.choice(["page", "block", "cursor"])
                    live.append((gen.alloc(kind, step), ref.alloc(kind, step)))
                elif roll < 0.55 and live:
                    gs, rs = rng.choice(live)
                    slot = rng.choice(["a", "b", "c", "d"])
                    if rng.random() < 0.8:
                        gd, rd = rng.choice(live)
                        gen.store(gs, slot, gd)
                        ref.store(rs, slot, rd)
                    else:
                        gen.store(gs, slot, None)
                        ref.store(rs, slot, None)
                elif roll < 0.68 and live:
                    gs, rs = rng.choice(live)
                    if gen.alive(gs) and gs not in gen.roots():
                        gen.add_root(gs)
                        ref.add_root(rs)
                elif roll < 0.78 and ref.roots():
                    rs = rng.choice(ref.roots())
                    match = [(g, r) for g, r in live if r == rs and g in gen.ids()]
                    if match:
                        gs, _ = match[0]
                        drop_one(gs)
                elif roll < 0.96:
                    # 回收；每若干轮做一次 major 对齐
                    if step % 7 == 0:
                        gen.major_collect()
                        ref.collect()
                        live = [(g, r) for g, r in live
                                if gen.alive(g) and ref.alive(r)]
                        self.assertEqual(
                            set(gen.ids()), set(ref.ids()),
                            "seed=%s step=%s major mismatch" % (seed, step))
                    else:
                        gen.minor_collect()
                        live = [(g, r) for g, r in live if gen.alive(g)]
                        # 分代堆只可能更保守：可达集合一个都不能少
                        reach = reachable(ref, ref.roots())
                        self.assertTrue(
                            reach.issubset(set(gen.ids())),
                            "seed=%s step=%s reachable freed" % (seed, step))
                else:
                    gen.verify_barrier()

            gen.major_collect()
            ref.collect()
            self.assertEqual(set(gen.ids()), set(ref.ids()))

    def test_long_run_promotions_actually_happen(self):
        rng = random.Random(1234)
        heap = GenerationalHeap(promote_after=2, verify=True)
        anchor = heap.alloc()
        heap.add_root(anchor)
        persistent = [heap.alloc() for _ in range(10)]
        for oid in persistent:
            heap.store(anchor, "p%d" % oid, oid)
        for _ in range(60):
            for _ in range(rng.randint(1, 6)):
                heap.alloc("tmp")
            heap.minor_collect()
        self.assertTrue(all(heap.alive(o) for o in persistent))
        self.assertTrue(all(heap.generation(o) == OLD for o in persistent))
        stats = heap.stats()
        self.assertGreater(stats["promotions"], 10)
        self.assertGreater(stats["minor_collections"], 10)


class LeakyGenerationalHeap(GenerationalHeap):
    """故意漏掉写屏障：老->年轻的新引用不进记录集。"""

    def store(self, src, slot, dst):
        old = super(GenerationalHeap, self).store(src, slot, dst)
        # 只做“老->老”的部分记账，老->年轻一律不记
        if src in self._old and dst is not None and dst in self._old:
            self._remembered.add(src)
        return old


class TestBarrierFaults(unittest.TestCase):
    """漏记写屏障必须能炸出来，而不是静默误收。"""

    def test_missing_barrier_frees_reachable_without_verify(self):
        heap = LeakyGenerationalHeap(promote_after=1)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        baby = heap.alloc()
        heap.store(elder, "baby", baby)
        heap.minor_collect()
        # 漏屏障的直接后果：可达的 baby 被误收（证明这条路径真的靠屏障）
        self.assertFalse(heap.alive(baby))

    def test_missing_barrier_raises_in_verify_mode(self):
        heap = LeakyGenerationalHeap(promote_after=1, verify=True)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        baby = heap.alloc()
        heap.store(elder, "baby", baby)
        with self.assertRaises(BarrierError):
            heap.minor_collect()

    def test_verify_barrier_explicit_call(self):
        heap = GenerationalHeap(promote_after=1)
        elder = heap.alloc()
        heap.add_root(elder)
        heap.minor_collect()
        baby = heap.alloc()
        heap.store(elder, "baby", baby)
        heap.verify_barrier()
        heap.store(elder, "baby", None)
        heap.verify_barrier()


class TestMinorScaling(unittest.TestCase):
    """五万老年代、几百年轻代时，minor 扫描量是年轻代常数倍。"""

    def test_scanned_independent_of_old_generation(self):
        heap = GenerationalHeap(promote_after=1, verify=True)
        elders = []
        for _ in range(50000):
            oid = heap.alloc("elder")
            heap.add_root(oid)
            elders.append(oid)
        heap.minor_collect()
        self.assertEqual(heap.generations(), {"young": 0, "old": 50000})

        def run_round(n_young):
            young = []
            for _ in range(n_young):
                oid = heap.alloc("young")
                heap.add_root(oid)
                young.append(oid)
            # 五万个老年代根一直挂着；极少量跨代引用
            heap.store(elders[0], "y0", young[0])
            heap.store(elders[1], "y1", young[1])
            report = heap.minor_collect()
            return report

        small = run_round(200)
        large = run_round(400)
        # old_scanned 只数记录集源对象，与 50000 无关
        self.assertLessEqual(small["old_scanned"], 2)
        self.assertLessEqual(large["old_scanned"], 2)
        # young_scanned 只跟年轻代活对象数同阶
        self.assertLessEqual(small["young_scanned"], 200)
        self.assertLessEqual(large["young_scanned"], 400)
        self.assertLessEqual(
            large["scanned"], 4 * small["scanned"] + 4,
            "minor 扫描量应随年轻代线性，不随老年代膨胀")
        # 决定性断言：扫描量远小于老年代规模
        self.assertLess(large["scanned"], 500)


class TestMidCollectionSafety(unittest.TestCase):
    """收集中途 alloc、动根、递归回收、钩子跨代复活。"""

    def test_alloc_in_hook_survives_this_minor_round(self):
        born = []

        def hook(heap, oid, kind, payload):
            born.append(heap.alloc("late"))

        heap = GenerationalHeap(on_free=hook, promote_after=1, verify=True)
        elder = heap.alloc("elder")
        heap.add_root(elder)
        heap.minor_collect()
        heap.alloc("trash")
        report = heap.minor_collect()
        self.assertEqual(report["swept"], 1)
        self.assertEqual(len(born), 1)
        self.assertTrue(heap.alive(born[0]))
        self.assertEqual(heap.generation(born[0]), YOUNG)

    def test_alloc_in_hook_attached_from_old_is_remembered(self):
        state = {}

        def hook(heap, oid, kind, payload):
            baby = heap.alloc("reborn")
            heap.store(state["elder"], "baby", baby)
            state["baby"] = baby

        heap = GenerationalHeap(on_free=hook, promote_after=1, verify=True)
        elder = heap.alloc("elder")
        state["elder"] = elder
        heap.add_root(elder)
        heap.minor_collect()
        heap.alloc("trash")
        heap.minor_collect()
        # 钩子里建的年轻对象被老对象挂上，下一轮 minor 必须保得住
        self.assertTrue(heap.alive(state["baby"]))
        heap.minor_collect()
        self.assertTrue(heap.alive(state["baby"]))

    def test_root_change_in_hook_takes_effect_next_round(self):
        state = {}

        def hook(heap, oid, kind, payload):
            if oid != state["victim"]:
                heap.drop_root(state["victim"])

        heap = GenerationalHeap(on_free=hook, promote_after=5)
        victim = heap.alloc("victim")
        state["victim"] = victim
        heap.add_root(victim)
        trash = heap.alloc("trash")
        report = heap.minor_collect()
        self.assertEqual(report["swept"], 1)
        self.assertFalse(heap.alive(trash))
        self.assertTrue(heap.alive(victim))
        self.assertEqual(heap.roots(), ())
        heap.minor_collect()
        self.assertFalse(heap.alive(victim))

    def test_root_drop_of_old_object_in_hook_waits_for_major(self):
        state = {}

        def hook(heap, oid, kind, payload):
            if oid != state["victim"]:
                heap.drop_root(state["victim"])

        heap = GenerationalHeap(on_free=hook, promote_after=1)
        victim = heap.alloc("victim")
        state["victim"] = victim
        heap.add_root(victim)
        heap.minor_collect()
        self.assertEqual(heap.generation(victim), OLD)
        heap.alloc("trash")
        heap.minor_collect()
        self.assertEqual(heap.roots(), ())
        self.assertTrue(heap.alive(victim))
        heap.major_collect()
        self.assertFalse(heap.alive(victim))

    def test_alloc_mid_collection_does_not_change_sweep_report(self):
        # 对照 ObjectHeap 语义：本轮报告在钩子前已定稿
        made = []

        def hook(heap, oid, kind, payload):
            made.append(heap.alloc())

        heap = GenerationalHeap(on_free=hook, promote_after=2)
        for _ in range(3):
            heap.alloc("trash")
        report = heap.minor_collect()
        self.assertEqual(report["swept"], 3)
        self.assertEqual(report["marked"], 0)
        self.assertEqual(len(made), 3)

    def test_reentrant_collect_inside_hook_rejected(self):
        def hook(heap, oid, kind, payload):
            heap.minor_collect()

        heap = GenerationalHeap(on_free=hook, promote_after=1)
        heap.alloc("trash")
        with self.assertRaises(CollectionError):
            heap.minor_collect()
        self.assertEqual(heap.ids(), ())

        def major_hook(h, oid, kind, payload):
            h.major_collect()

        heap2 = GenerationalHeap(on_free=major_hook, promote_after=1)
        heap2.alloc("trash")
        with self.assertRaises(CollectionError):
            heap2.major_collect()

    def test_hook_exception_propagates_and_heap_recovers(self):
        calls = []

        def hook(heap, oid, kind, payload):
            calls.append(oid)
            if len(calls) == 2:
                raise RuntimeError("boom")

        heap = GenerationalHeap(on_free=hook, promote_after=1)
        root = heap.alloc("root")
        heap.add_root(root)
        for _ in range(4):
            heap.alloc("trash")
        with self.assertRaises(RuntimeError):
            heap.minor_collect()
        self.assertEqual(len(calls), 2)
        # 继续用：root 与它的自引用还在
        heap.store(root, "me", root)
        report = heap.major_collect()
        self.assertEqual(report["swept"], 0)
        self.assertEqual(heap.ids(), (root,))

    def test_hook_resurrection_chain_across_generations(self):
        """跨代引用 + 钩子复活一起造：老对象收掉时复活年轻代链条。"""
        state = {"chains": 0}

        def hook(heap, oid, kind, payload):
            if kind != "seed":
                return
            anchor = heap.alloc("anchor")
            heap.add_root(anchor)
            prev = anchor
            for i in range(3):
                node = heap.alloc("link", i)
                heap.store(prev, "next", node)
                prev = node
            state["chains"] += 1
            state["tail"] = prev

        heap = GenerationalHeap(on_free=hook, promote_after=1, verify=True)
        seed = heap.alloc("seed")
        heap.minor_collect()
        self.assertTrue(heap.alive(state["tail"]))
        heap.minor_collect()
        self.assertTrue(heap.alive(state["tail"]))
        # 链条最终晋升老年代且记账清空，major 后存活集合稳定
        heap.minor_collect()
        heap.major_collect()
        self.assertTrue(heap.alive(state["tail"]))
        self.assertEqual(heap.remembered(), ())


if __name__ == "__main__":
    unittest.main()
