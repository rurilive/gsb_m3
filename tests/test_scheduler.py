"""Scheduler 的验收测试：预算、公平、互斥、崩溃恢复、对拍、写峰延迟。"""

import random
import unittest

from segpile import MemoryBackend, Scheduler, SimDevice, Store


def fill(store, count, prefix="a", start=0):
    for i in range(count):
        store.put("%s%02d" % (prefix, start + i), start + i)


def percentile(values, q):
    ordered = sorted(values)
    return 0.0 if not ordered else ordered[int(round(q * (len(ordered) - 1)))]


def make(limit=8):
    device = SimDevice()
    return Store(MemoryBackend(), device, segment_limit=limit), device


class TestBudget(unittest.TestCase):
    def test_step_never_exceeds_budget(self):
        store, _ = make()
        fill(store, 36)
        sched = Scheduler(store, budget=4)
        for _ in range(30):
            sched.step()
            self.assertLessEqual(sched.last_units, 4)

    def test_budget_must_be_positive(self):
        store, _ = make()
        with self.assertRaises(ValueError):
            Scheduler(store, budget=0)

    def test_merge_completes_over_multiple_rounds(self):
        store, _ = make()
        fill(store, 36)
        sched = Scheduler(store, budget=4)
        before = len(store.segments())
        report = None
        for _ in range(50):
            report = sched.step()
            if report is not None:
                break
        self.assertIsNotNone(report)
        self.assertEqual(len(store.segments()), before - 1)
        self.assertEqual(report.units, 1 + 16 + 16 + 1)
        self.assertEqual(store.get("a00"), 0)
        self.assertEqual(store.get("a35"), 35)

    def test_idle_when_nothing_to_merge(self):
        store, _ = make(4)
        fill(store, 5)
        sched = Scheduler(store)
        self.assertIsNone(sched.step())
        self.assertEqual(sched.last_units, 0)


class TestPickPolicy(unittest.TestCase):
    def test_small_tier_first(self):
        store, _ = make(4)
        fill(store, 12)
        sched = Scheduler(store, budget=64)
        report = sched.step()
        while report is None:
            report = sched.step()
        self.assertEqual(list(report.inputs), [0, 1])

    def test_big_segment_eventually_picked(self):
        store, _ = make(4)
        fill(store, 12)
        sched = Scheduler(store, budget=64)
        while sched.step() is None:
            pass
        big = [s for s in store.segments() if s.size == 8][0]
        fill(store, 8, prefix="b")
        sched._skips[big.sid] = sched.max_skips
        while sched.step() is None:
            pass
        self.assertNotIn(big.sid, [s.sid for s in store.segments()])

    def test_skips_never_exceed_cap_under_continuous_writes(self):
        store, device = make(4)
        sched = Scheduler(store, budget=64)
        worst = 0
        for i in range(300):
            sched.step()
            store.put("k%03d" % i, i)
            device.advance(1.0)
            worst = max(worst, max(sched._skips.values(), default=0))
        self.assertLessEqual(worst, sched.max_skips)
        self.assertLessEqual(len(store.segments()), 8)


class TestMutualExclusion(unittest.TestCase):
    def test_compact_once_yields_to_claimed_segments(self):
        store, _ = make(4)
        fill(store, 12)
        store.claim_segments([0, 1], owner="test")
        self.assertIsNone(store.compact_once())
        store.release_segments([0, 1], owner="test")
        self.assertIsNotNone(store.compact_once())

    def test_compact_once_yields_to_inflight_merge(self):
        store, _ = make(4)
        fill(store, 12)
        sched = Scheduler(store, budget=1)
        sched.step()
        self.assertIsNotNone(store.pending_merge)
        self.assertIsNone(store.compact_once())

    def test_double_claim_rejected(self):
        store, _ = make(4)
        fill(store, 12)
        store.claim_segments([0], owner="a")
        with self.assertRaises(RuntimeError):
            store.claim_segments([0], owner="b")


class TestRecovery(unittest.TestCase):
    def test_rollforward_when_output_already_written(self):
        backend = MemoryBackend()
        device = SimDevice()
        store = Store(backend, device, segment_limit=4)
        fill(store, 9)
        # journal(1) + 读 8 + 写 8 = 17，一轮正好停在 commit 前
        sched = Scheduler(store, budget=17)
        self.assertIsNone(sched.step())
        self.assertIsNotNone(store.pending_merge)

        reopened = Store(backend, device, segment_limit=4)
        self.assertIsNone(reopened.pending_merge)
        self.assertEqual(
            [(s.seq, s.size) for s in reopened.segments()],
            [(1, 8), (2, 1)],
        )
        for i in range(9):
            self.assertEqual(reopened.get("a%02d" % i), i)
        self.assertEqual(
            set(backend.segment_ids()),
            {s.sid for s in reopened.segments()},
        )

    def test_resume_mid_merge_after_crash(self):
        backend = MemoryBackend()
        device = SimDevice()
        store = Store(backend, device, segment_limit=4)
        fill(store, 9)
        sched = Scheduler(store, budget=3)
        sched.step()
        sched.step()
        self.assertIsNotNone(store.pending_merge)

        reopened = Store(backend, device, segment_limit=4)
        self.assertIsNotNone(reopened.pending_merge)
        sched2 = Scheduler(reopened, budget=4)
        report = None
        for _ in range(20):
            report = sched2.step()
            if report is not None:
                break
        self.assertIsNotNone(report)
        self.assertIsNone(reopened.pending_merge)
        self.assertEqual(
            [(s.seq, s.size) for s in reopened.segments()],
            [(1, 8), (2, 1)],
        )
        for i in range(9):
            self.assertEqual(reopened.get("a%02d" % i), i)

    def test_crash_before_journal_is_a_noop(self):
        backend = MemoryBackend()
        device = SimDevice()
        store = Store(backend, device, segment_limit=4)
        fill(store, 9)
        Scheduler(store, budget=4)
        reopened = Store(backend, device, segment_limit=4)
        self.assertIsNone(reopened.pending_merge)
        self.assertEqual(len(reopened.segments()), 3)


class TestAgainstReference(unittest.TestCase):
    def test_randomized_interleaving_matches_dict(self):
        rng = random.Random(20260922)
        backend = MemoryBackend()
        device = SimDevice()
        store = Store(backend, device, segment_limit=4)
        sched = Scheduler(store, budget=4)
        ref = {}
        for i in range(600):
            move = rng.random()
            if move < 0.55:
                key = "k%02d" % rng.randrange(30)
                value = rng.randrange(1000)
                store.put(key, value)
                ref[key] = value
            elif move < 0.8:
                sched.step()
            elif move < 0.9:
                store.compact_once()
            else:
                # 模拟进程被杀：同一份 backend 重新打开，调度器重来
                store = Store(backend, device, segment_limit=4)
                sched = Scheduler(store, budget=4)
            device.advance(0.5)
            if i % 17 == 0:
                self.assertEqual(store.snapshot(), ref)
        self.assertEqual(store.snapshot(), ref)
        for key, value in ref.items():
            self.assertEqual(store.get(key), value)


class TestWritePeak(unittest.TestCase):
    def test_p95_back_to_single_digits(self):
        device = SimDevice()
        store = Store(MemoryBackend(), device, segment_limit=8)
        sched = Scheduler(store, budget=4)
        latencies = []
        merges = 0
        for i in range(200):
            if sched.step() is not None:
                merges += 1
            latencies.append(store.put("hot:%03d" % i, i))
            device.advance(1.0)
        self.assertGreater(merges, 0)
        self.assertLess(percentile(latencies, 0.95), 10.0)
        # 不调度的话 200 笔会滚出 26 段，调度后明显更少
        self.assertLessEqual(len(store.segments()), 15)


if __name__ == "__main__":
    unittest.main()
