"""Scheduler 现有行为的锁定测试。

只通过公开接口断言，不碰内部结构。改造之后这些测试必须原样全绿。
"""

import time
import unittest

from tickbase import DailyTrigger, IntervalTrigger, ManualClock, Scheduler

START = 1_700_000_000.0


class Recorder:
    """记录派发的假执行器，submit 时不真正执行。"""

    def __init__(self):
        self.jobs = []

    def submit(self, fn):
        self.jobs.append(fn)


class TestRegistration(unittest.TestCase):
    def test_first_fire_waits_one_interval(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        self.assertEqual(sched.next_fire("beat"), START + 10)

    def test_interval_must_be_positive(self):
        with self.assertRaises(ValueError):
            IntervalTrigger(0)
        with self.assertRaises(ValueError):
            IntervalTrigger(-5)

    def test_daily_arguments_validated(self):
        with self.assertRaises(ValueError):
            DailyTrigger(24)
        with self.assertRaises(ValueError):
            DailyTrigger(9, 60)

    def test_duplicate_name_rejected(self):
        sched = Scheduler(clock=ManualClock(START))
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        with self.assertRaises(ValueError):
            sched.add_task("beat", IntervalTrigger(5), lambda t: None)

    def test_remove_task_stops_dispatch(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        sched.remove_task("beat")
        self.assertEqual(sched.tasks(), [])
        clock.advance(30)
        self.assertEqual(sched.poll(), [])


class TestPolling(unittest.TestCase):
    def test_poll_before_due_does_not_fire(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        clock.advance(9)
        self.assertEqual(sched.poll(), [])

    def test_poll_at_due_instant_fires(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        clock.advance(10)
        self.assertEqual(sched.poll(), ["beat"])
        self.assertEqual(sched.next_fire("beat"), START + 20)

    def test_on_time_polls_keep_the_original_grid(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        seen = []
        sched.add_task("beat", IntervalTrigger(10), seen.append)
        for step in range(1, 5):
            clock.set(START + 10 * step)
            self.assertEqual(sched.poll(), ["beat"])
            self.assertEqual(sched.next_fire("beat"), START + 10 * (step + 1))
        self.assertEqual(seen, [START + 10, START + 20, START + 30, START + 40])

    def test_a_task_fires_at_most_once_per_poll(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        clock.advance(35)
        self.assertEqual(sched.poll(), ["beat"])

    def test_scheduled_time_is_passed_to_the_task(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        seen = []
        sched.add_task("beat", IntervalTrigger(10), seen.append)
        clock.advance(10)
        sched.poll()
        self.assertEqual(seen, [START + 10])

    def test_due_tasks_fire_in_registration_order(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("first", IntervalTrigger(5), lambda t: None)
        sched.add_task("second", IntervalTrigger(5), lambda t: None)
        sched.add_task("third", IntervalTrigger(15), lambda t: None)
        clock.advance(5)
        self.assertEqual(sched.poll(), ["first", "second"])
        clock.advance(10)
        self.assertEqual(sched.poll(), ["first", "second", "third"])


class TestDailyTrigger(unittest.TestCase):
    def test_next_fire_is_the_next_wall_clock_instant(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("report", DailyTrigger(9, 30), lambda t: None)
        nxt = sched.next_fire("report")
        self.assertGreater(nxt, START)
        self.assertLessEqual(nxt - START, 86400)
        lt = time.localtime(nxt)
        self.assertEqual((lt.tm_hour, lt.tm_min, lt.tm_sec), (9, 30, 0))

    def test_daily_fires_once_per_day(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        count = []
        sched.add_task("report", DailyTrigger(9, 30), count.append)
        for _ in range(25):
            clock.advance(3600)
            sched.poll()
        self.assertEqual(len(count), 1)


class TestDispatchAndStats(unittest.TestCase):
    def test_dispatch_goes_through_the_executor(self):
        clock = ManualClock(START)
        recorder = Recorder()
        sched = Scheduler(clock=clock, executor=recorder)
        seen = []
        sched.add_task("beat", IntervalTrigger(10), seen.append)
        clock.advance(10)
        sched.poll()
        self.assertEqual(len(recorder.jobs), 1)
        self.assertEqual(seen, [])
        recorder.jobs[0]()
        self.assertEqual(seen, [START + 10])

    def test_stats_counts_runs(self):
        clock = ManualClock(START)
        sched = Scheduler(clock=clock)
        sched.add_task("beat", IntervalTrigger(10), lambda t: None)
        sched.add_task("slow", IntervalTrigger(60), lambda t: None)
        clock.advance(10)
        sched.poll()
        clock.advance(10)
        sched.poll()
        self.assertEqual(sched.stats()["runs"], 2)
        self.assertEqual(sched.stats()["per_task"], {"beat": 2, "slow": 0})


if __name__ == "__main__":
    unittest.main()
