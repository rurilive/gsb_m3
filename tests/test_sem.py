"""weightsem 现有行为的锁定测试（基线，一字不改且必须全绿）。

只断言普通计数信号量现在能做的事：容量校验、取一个许可、还一个许可、
许可耗尽时的报错，以及还满之后的边界。改造之后这些行为一点都不能变。
"""

import unittest

from weightsem.semaphore import Semaphore, SemaphoreBusy


class TestSemaphore(unittest.TestCase):
    def test_capacity_recorded(self):
        sem = Semaphore(3)
        self.assertEqual(sem.capacity, 3)

    def test_starts_full(self):
        sem = Semaphore(3)
        self.assertEqual(sem.available, 3)
        self.assertEqual(sem.held, 0)

    def test_acquire_takes_one(self):
        sem = Semaphore(2)
        sem.acquire()
        self.assertEqual(sem.available, 1)
        self.assertEqual(sem.held, 1)

    def test_release_returns_one(self):
        sem = Semaphore(2)
        sem.acquire()
        sem.acquire()
        self.assertEqual(sem.available, 0)
        sem.release()
        self.assertEqual(sem.available, 1)
        self.assertEqual(sem.held, 1)

    def test_acquire_when_empty_raises_busy(self):
        sem = Semaphore(1)
        sem.acquire()
        with self.assertRaises(SemaphoreBusy):
            sem.acquire()

    def test_exhausted_state_unchanged(self):
        sem = Semaphore(1)
        sem.acquire()
        with self.assertRaises(SemaphoreBusy):
            sem.acquire()
        self.assertEqual(sem.available, 0)
        self.assertEqual(sem.held, 1)

    def test_release_beyond_capacity_rejected(self):
        sem = Semaphore(2)
        with self.assertRaises(ValueError):
            sem.release()

    def test_release_after_busy_still_capped(self):
        sem = Semaphore(1)
        sem.acquire()
        sem.release()
        with self.assertRaises(ValueError):
            sem.release()

    def test_non_int_capacity_rejected(self):
        with self.assertRaises(ValueError):
            Semaphore("3")

    def test_bool_capacity_rejected(self):
        with self.assertRaises(ValueError):
            Semaphore(True)

    def test_zero_capacity_rejected(self):
        with self.assertRaises(ValueError):
            Semaphore(0)

    def test_negative_capacity_rejected(self):
        with self.assertRaises(ValueError):
            Semaphore(-1)

    def test_repr_shows_available_over_capacity(self):
        sem = Semaphore(2)
        sem.acquire()
        self.assertEqual(repr(sem), "<Semaphore available=1/2>")


if __name__ == "__main__":
    unittest.main()