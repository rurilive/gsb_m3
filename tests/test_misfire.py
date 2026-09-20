"""状态恢复、misfire 策略、网格节奏、回拨防护与调度性能的测试。

不碰 tests/test_scheduler.py 里的行为基线，只测新增能力。
"""

import json
import os
import tempfile
import time
import unittest

from tickbase import IntervalTrigger, ManualClock, Scheduler

START = 1_700_000_000.0


class Recorder:
    """记录派发的假执行器，submit 时不真正执行。"""

    def __init__(self):
        self.jobs = []

    def submit(self, fn):
        self.jobs.append(fn)


class StateDirMixin(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.state_path = os.path.join(self._tmp.name, "state.json")


class TestRecovery(StateDirMixin):
    def test_resume_continues_grid_not_reanchor(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock, state_path=self.state_path)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        clock.advance(10)
        self.assertEqual(sched.poll(), ["beat"])
        self.assertTrue(os.path.exists(self.state_path))

        # 模拟重启：新进程、新时钟，当前时刻已是 START+55
        sched2 = Scheduler(clock=ManualClock(START + 55), state_path=self.state_path)
        sched2.add_task("beat", IntervalTrigger(10), lambda t: None)
        # 接着上次落盘的计划时间，而不是从当前时刻重排成 START+65
        self.assertEqual(sched2.next_fire("beat"), START + 20)

    def test_coalesce_after_downtime_fires_once_then_back_on_grid(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock, state_path=self.state_path)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        clock.advance(10)
        sched.poll()

        seen = []
        sched2 = Scheduler(clock=ManualClock(START + 55), state_path=self.state_path)
        sched2.add_task("beat", IntervalTrigger(10), seen.append, misfire="coalesce")
        # 停机错过 20/30/40/50 四个点：合并补跑一次，参数是最早错过的计划点
        self.assertEqual(sched2.poll(), ["beat"])
        self.assertEqual(seen, [START + 20])
        # 补完回到原节奏，下一次是严格晚于当前时刻的网格点
        self.assertEqual(sched2.next_fire("beat"), START + 60)
        self.assertEqual(sched2.stats()["coalesced"], 3)
        self.assertEqual(sched2.stats()["skipped"], 0)

    def test_skip_after_downtime_drops_missed_points(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock, state_path=self.state_path)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        clock.advance(10)
        sched.poll()

        seen = []
        sched2 = Scheduler(clock=ManualClock(START + 55), state_path=self.state_path)
        sched2.add_task("beat", IntervalTrigger(10), seen.append, misfire="skip")
        # 错过的点直接丢，不补跑
        self.assertEqual(sched2.poll(), [])
        self.assertEqual(seen, [])
        self.assertEqual(sched2.next_fire("beat"), START + 60)
        self.assertEqual(sched2.stats()["skipped"], 4)
        self.assertEqual(sched2.stats()["coalesced"], 0)
        # 丢掉之后回到原节奏，到点照常触发
        sched2._clock.set(START + 60)
        self.assertEqual(sched2.poll(), ["beat"])
        self.assertEqual(seen, [START + 60])

    def test_state_survives_restart_without_poll(self):
        sched = Scheduler(clock=ManualClock(START), state_path=self.state_path)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        sched.flush()
        sched2 = Scheduler(clock=ManualClock(START + 5), state_path=self.state_path)
        sched2.add_task("beat", IntervalTrigger(10), lambda t: None)
        self.assertEqual(sched2.next_fire("beat"), START + 10)

    def test_remove_task_drops_persisted_state(self):
        sched = Scheduler(clock=ManualClock(START), state_path=self.state_path)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        sched.remove_task("beat")
        sched.flush()
        sched2 = Scheduler(clock=ManualClock(START + 5), state_path=self.state_path)
        sched2.add_task("beat", IntervalTrigger(10), lambda t: None)
        self.assertEqual(sched2.next_fire("beat"), START + 15)

    def test_corrupt_state_file_starts_clean(self):
        with open(self.state_path, "w", encoding="utf-8") as fh:
            fh.write("this is not json {{{")
        sched = Scheduler(clock=ManualClock(START), state_path=self.state_path)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        self.assertEqual(sched.next_fire("beat"), START + 10)
        clock = sched._clock
        clock.advance(10)
        self.assertEqual(sched.poll(), ["beat"])

    def test_truncated_state_file_starts_clean(self):
        sched = Scheduler(clock=ManualClock(START), state_path=self.state_path)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        sched.flush()
        with open(self.state_path, "r+", encoding="utf-8") as fh:
            content = fh.read()
            fh.seek(0)
            fh.truncate()
            fh.write(content[: len(content) // 2])
        sched2 = Scheduler(clock=ManualClock(START), state_path=self.state_path)
        sched2.add_task("beat", IntervalTrigger(10), lambda t: None)
        self.assertEqual(sched2.next_fire("beat"), START + 10)

    def test_state_file_with_wrong_shape_starts_clean(self):
        with open(self.state_path, "w", encoding="utf-8") as fh:
            json.dump({"tasks": {"beat": {"next_fire": "not-a-number"}}}, fh)
        sched = Scheduler(clock=ManualClock(START), state_path=self.state_path)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        self.assertEqual(sched.next_fire("beat"), START + 10)


class TestMisfirePolicy(unittest.TestCase):
    def test_default_policy_is_coalesce(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        seen = []
        sched.add_task("beat", IntervalTrigger(10), seen.append)
        clock.advance(35)
        self.assertEqual(sched.poll(), ["beat"])
        self.assertEqual(seen, [START + 10])
        self.assertEqual(sched.next_fire("beat"), START + 40)
        self.assertEqual(sched.stats()["coalesced"], 2)

    def test_skip_drops_points_without_firing(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        seen = []
        sched.add_task("beat", IntervalTrigger(10), seen.append, misfire="skip")
        clock.advance(35)
        self.assertEqual(sched.poll(), [])
        self.assertEqual(seen, [])
        self.assertEqual(sched.next_fire("beat"), START + 40)
        self.assertEqual(sched.stats()["skipped"], 3)

    def test_single_due_point_fires_normally_under_both_policies(self):
        for policy in ("coalesce", "skip"):
            clock = ManualClock(START)
            sched = Scheduler(clock=clock)
            seen = []
            sched.add_task("beat", IntervalTrigger(10), seen.append, misfire=policy)
            clock.advance(11)
            self.assertEqual(sched.poll(), ["beat"])
            self.assertEqual(seen, [START + 10])
            stats = sched.stats()
            self.assertEqual(stats["skipped"], 0)
            self.assertEqual(stats["coalesced"], 0)

    def test_unknown_policy_rejected(self):
        sched = Scheduler(clock=ManualClock(START))
        with self.assertRaises(ValueError):
            sched.add_task("beat", IntervalTrigger(10), lambda t: None, misfire="boom")


class TestGridAndConcurrency(unittest.TestCase):
    def test_long_task_does_not_skew_the_grid(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        seen = []

        def slow(t):
            seen.append(t)
            clock.advance(25)  # 跑得比间隔还长

        sched.add_task("slow", IntervalTrigger(10), slow)
        clock.advance(10)
        sched.poll()
        # 下一次仍按计划网格走，不从跑完的时刻重算
        self.assertEqual(sched.next_fire("slow"), START + 20)
        sched.poll()  # 此刻时钟已到 START+35，错过 20、30 两点
        self.assertEqual(seen, [START + 10, START + 20])
        self.assertEqual(sched.next_fire("slow"), START + 40)
        self.assertEqual(sched.stats()["coalesced"], 1)

    def test_same_task_never_runs_twice_in_parallel(self):
        clock = ManualClock(START)
        recorder = Recorder()
        sched = Scheduler(clock=clock, executor=recorder)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        clock.advance(10)
        self.assertEqual(sched.poll(), ["beat"])
        self.assertEqual(len(recorder.jobs), 1)
        # 上一份还没跑完（执行器攒着没执行），到点也不再派第二份
        clock.advance(10)
        self.assertEqual(sched.poll(), [])
        self.assertEqual(len(recorder.jobs), 1)
        # 跑完之后，挂起的计划点按 coalesce 补一次
        recorder.jobs[0]()
        clock.advance(10)
        self.assertEqual(sched.poll(), ["beat"])
        self.assertEqual(len(recorder.jobs), 2)
        self.assertEqual(sched.stats()["coalesced"], 1)

    def test_clock_rollback_does_not_refire_or_storm(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        seen = []
        sched.add_task("beat", IntervalTrigger(10), seen.append)
        clock.advance(10)
        sched.poll()
        self.assertEqual(seen, [START + 10])
        # 时钟往回拨：跑过的点不许重跑
        clock.set(START + 5)
        self.assertEqual(sched.poll(), [])
        clock.set(START + 11)
        self.assertEqual(sched.poll(), [])
        # 再往前走：只触发新的计划点，不补旧账、不触发风暴
        clock.set(START + 25)
        self.assertEqual(sched.poll(), ["beat"])
        self.assertEqual(seen, [START + 10, START + 20])
        clock.set(START + 100)
        self.assertEqual(sched.poll(), ["beat"])
        self.assertEqual(seen, [START + 10, START + 20, START + 30])

    def test_rollback_before_first_fire_waits(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        clock.set(START - 1000)
        self.assertEqual(sched.poll(), [])
        clock.set(START + 10)
        self.assertEqual(sched.poll(), ["beat"])


class TestPerformance(unittest.TestCase):
    def test_ten_thousand_tasks_one_day_of_seconds(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        fired = [0]

        def make_fn():
            def fn(t):
                fired[0] += 1

            return fn

        for i in range(10_000):
            sched.add_task(f"task-{i}", IntervalTrigger(60 + i % 3540), make_fn())
        start = time.monotonic()
        for _ in range(86_400):
            clock.advance(1)
            sched.poll()
        elapsed = time.monotonic() - start
        self.assertGreater(fired[0], 0)
        self.assertLess(elapsed, 5.0, f"一天的秒级 poll 跑了 {elapsed:.1f}s")


if __name__ == "__main__":
    unittest.main()
