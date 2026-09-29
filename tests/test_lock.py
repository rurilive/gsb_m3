"""MutexLock 现有行为的锁定测试。"""

import threading
import unittest

from lockfolio.lock import MutexLock


class TestMutexLock(unittest.TestCase):
    def test_fresh_lock_is_free(self):
        lock = MutexLock()
        self.assertIsNone(lock.holder("a"))
        self.assertFalse(lock.is_locked("a"))
        self.assertEqual(lock.keys(), [])

    def test_acquire_then_holder(self):
        lock = MutexLock()
        self.assertTrue(lock.acquire("a", "t1"))
        self.assertEqual(lock.holder("a"), "t1")
        self.assertTrue(lock.is_locked("a"))

    def test_acquire_blocked_by_other_owner(self):
        lock = MutexLock()
        lock.acquire("a", "t1")
        self.assertFalse(lock.acquire("a", "t2"))
        self.assertEqual(lock.holder("a"), "t1")

    def test_reacquire_by_same_owner_fails(self):
        lock = MutexLock()
        lock.acquire("a", "t1")
        self.assertFalse(lock.acquire("a", "t1"))
        self.assertEqual(lock.holder("a"), "t1")

    def test_release_by_holder(self):
        lock = MutexLock()
        lock.acquire("a", "t1")
        self.assertTrue(lock.release("a", "t1"))
        self.assertIsNone(lock.holder("a"))
        self.assertFalse(lock.is_locked("a"))

    def test_release_by_other_owner_fails(self):
        lock = MutexLock()
        lock.acquire("a", "t1")
        self.assertFalse(lock.release("a", "t2"))
        self.assertEqual(lock.holder("a"), "t1")

    def test_release_free_key_fails(self):
        lock = MutexLock()
        self.assertFalse(lock.release("ghost", "t1"))

    def test_release_twice_second_fails(self):
        lock = MutexLock()
        lock.acquire("a", "t1")
        self.assertTrue(lock.release("a", "t1"))
        self.assertFalse(lock.release("a", "t1"))

    def test_acquire_after_release_succeeds(self):
        lock = MutexLock()
        lock.acquire("a", "t1")
        lock.release("a", "t1")
        self.assertTrue(lock.acquire("a", "t2"))
        self.assertEqual(lock.holder("a"), "t2")

    def test_keys_are_per_key_independent(self):
        lock = MutexLock()
        lock.acquire("a", "t1")
        lock.acquire("b", "t2")
        self.assertEqual(sorted(lock.keys()), ["a", "b"])
        self.assertFalse(lock.acquire("a", "t2"))
        self.assertTrue(lock.is_locked("b"))

    def test_keys_snapshot_reflects_release(self):
        lock = MutexLock()
        lock.acquire("a", "t1")
        lock.acquire("b", "t2")
        lock.release("a", "t1")
        self.assertEqual(lock.keys(), ["b"])

    def test_holder_missing_returns_none(self):
        lock = MutexLock()
        self.assertIsNone(lock.holder("nope"))

    def test_clock_is_injectable(self):
        lock = MutexLock(clock=lambda: 5.0)
        self.assertTrue(lock.acquire("a", "t1"))
        self.assertEqual(lock.holder("a"), "t1")

    def test_no_expiry_without_release(self):
        # 基线没有租约：时钟怎么走都不会自动释放。
        now = [0.0]
        lock = MutexLock(clock=lambda: now[0])
        lock.acquire("a", "t1")
        now[0] = 10_000.0
        self.assertTrue(lock.is_locked("a"))
        self.assertFalse(lock.acquire("a", "t2"))

    def test_many_keys_consistent(self):
        lock = MutexLock()
        for i in range(50):
            self.assertTrue(lock.acquire(i, "t1"))
        self.assertEqual(len(lock.keys()), 50)
        for i in range(0, 50, 2):
            self.assertTrue(lock.release(i, "t1"))
        for i in range(50):
            self.assertEqual(lock.is_locked(i), i % 2 == 1)

    def test_concurrent_acquire_single_winner_per_key(self):
        lock = MutexLock()
        winners = []
        guard = threading.Lock()
        threads = []

        def worker(name):
            if lock.acquire("hot", name):
                with guard:
                    winners.append(name)

        for t in range(8):
            th = threading.Thread(target=worker, args=(f"t{t}",))
            threads.append(th)
        for th in threads:
            th.start()
        for th in threads:
            th.join(5)
        self.assertEqual(len(winners), 1)


if __name__ == "__main__":
    unittest.main()