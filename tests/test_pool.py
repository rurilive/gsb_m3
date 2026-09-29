"""SyncPool 现状行为的锁定测试（改造前基线，不许改）。"""

import unittest

from poolx.pool import SyncPool


class TestSubmit(unittest.TestCase):
    def test_submit_returns_index_in_order(self):
        pool = SyncPool()
        self.assertEqual(pool.submit(lambda x: x * x, 3), 0)
        self.assertEqual(pool.submit(lambda x: x * x, 4), 1)
        self.assertEqual(pool.submit(lambda x: x * x, 5), 2)

    def test_submit_runs_synchronously(self):
        pool = SyncPool()
        seen = []
        pool.submit(lambda x: seen.append(x), 7)
        # 同步执行：submit 返回时任务已经跑过。
        self.assertEqual(seen, [7])

    def test_submit_rejects_non_callable(self):
        pool = SyncPool()
        with self.assertRaises(TypeError):
            pool.submit(123, 1)


class TestResults(unittest.TestCase):
    def test_results_returns_all_in_order(self):
        pool = SyncPool()
        pool.submit(lambda x: x + 1, 10)
        pool.submit(lambda x: x + 1, 20)
        pool.submit(lambda x: x + 1, 30)
        self.assertEqual(pool.results(), [11, 21, 31])

    def test_results_is_a_copy(self):
        pool = SyncPool()
        pool.submit(lambda x: x, 1)
        got = pool.results()
        got.append(999)
        self.assertEqual(pool.results(), [1])

    def test_results_empty_initially(self):
        self.assertEqual(SyncPool().results(), [])


class TestGet(unittest.TestCase):
    def test_get_returns_indexed_result(self):
        pool = SyncPool()
        pool.submit(lambda x: x * 2, 5)
        pool.submit(lambda x: x * 2, 6)
        self.assertEqual(pool.get(0), 10)
        self.assertEqual(pool.get(1), 12)

    def test_get_out_of_range_raises_index_error(self):
        pool = SyncPool()
        pool.submit(lambda x: x, 1)
        with self.assertRaises(IndexError):
            pool.get(5)

    def test_get_negative_index(self):
        pool = SyncPool()
        pool.submit(lambda x: x, "a")
        pool.submit(lambda x: x, "b")
        self.assertEqual(pool.get(-1), "b")


class TestWaitAndSize(unittest.TestCase):
    def test_wait_is_a_noop(self):
        pool = SyncPool()
        pool.submit(lambda x: x, 1)
        self.assertIsNone(pool.wait())

    def test_size_counts_submitted(self):
        pool = SyncPool()
        self.assertEqual(pool.size(), 0)
        pool.submit(lambda x: x, 1)
        pool.submit(lambda x: x, 2)
        self.assertEqual(pool.size(), 2)


class TestShutdown(unittest.TestCase):
    def test_shutdown_is_a_noop(self):
        pool = SyncPool()
        pool.submit(lambda x: x, 1)
        self.assertIsNone(pool.shutdown())
        # 当前口径下，关闭没有副作用，仍可继续提交。
        self.assertEqual(pool.submit(lambda x: x, 2), 1)
        self.assertEqual(pool.size(), 2)


if __name__ == "__main__":
    unittest.main()
