"""netpool 语义测试：以 README.md「语义约定」一节为唯一行为标准。

运行方式（仓库根目录）：
    python3 -m unittest discover -s tests -v

并发用例一律用 threading.Event + join 把节奏定死，超时断言留足余量，
可独立重复运行。
"""

import os
import sys
import threading
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from netpool.pool import (  # noqa: E402
    BorrowTimeout,
    ConnectionPool,
    FakeConn,
    PoolClosedError,
)


class TestBorrowSemantics(unittest.TestCase):
    """README 第 1 条：borrow(timeout=None)。"""

    def test_borrow_creates_conn_when_pool_not_full(self):
        # 无空闲且池未满 → 用 factory 新建，并标记为在途
        pool = ConnectionPool(max_size=2)
        conn = pool.borrow()
        self.assertIsInstance(conn, FakeConn)
        stats = pool.stats()
        self.assertEqual(stats["inflight"], 1)
        self.assertEqual(stats["idle"], 0)
        self.assertEqual(stats["created"], 1)
        pool.close()

    def test_borrow_reuses_idle_conn(self):
        # 有空闲连接 → 直接取出（不新建）
        pool = ConnectionPool(max_size=2)
        conn = pool.borrow()
        pool.return_conn(conn)
        again = pool.borrow()
        self.assertIs(again, conn)
        self.assertEqual(pool.stats()["created"], 1)
        pool.close()

    def test_borrow_timeout_raises_borrow_timeout(self):
        # 池满且到 deadline 仍无归还 → 抛 BorrowTimeout，耗时应接近 timeout
        pool = ConnectionPool(max_size=1)
        pool.borrow()  # 占满
        start = time.monotonic()
        with self.assertRaises(BorrowTimeout):
            pool.borrow(timeout=0.5)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.35)
        self.assertLess(elapsed, 1.5)  # 余量，防止偶发调度抖动
        pool.close()

    def test_borrow_after_close_raises_pool_closed(self):
        # 池已关闭 → 抛 PoolClosedError
        pool = ConnectionPool(max_size=1)
        pool.close()
        with self.assertRaises(PoolClosedError):
            pool.borrow()

    def test_waiting_borrower_gets_returned_conn_promptly(self):
        # 池满等待期间只要有连接归还，应立即拿到它（单等待者，真实并发）
        pool = ConnectionPool(max_size=1, borrow_timeout=5.0)
        held = pool.borrow()
        entered = threading.Event()
        result = {}

        def waiter():
            entered.set()
            start = time.monotonic()
            result["conn"] = pool.borrow()
            result["elapsed"] = time.monotonic() - start

        t = threading.Thread(target=waiter)
        t.start()
        self.assertTrue(entered.wait(2.0))
        time.sleep(0.3)  # 确保 waiter 已进入等待
        pool.return_conn(held)
        t.join(3.0)
        self.assertFalse(t.is_alive(), "waiter 没有在归还后及时醒来")
        self.assertIs(result["conn"], held)
        self.assertLess(result["elapsed"], 1.5)
        pool.close()


class TestReturnSemantics(unittest.TestCase):
    """README 第 2 条：return_conn(conn)。"""

    def test_return_goes_back_to_idle(self):
        pool = ConnectionPool(max_size=2)
        conn = pool.borrow()
        pool.return_conn(conn)
        stats = pool.stats()
        self.assertEqual(stats["idle"], 1)
        self.assertEqual(stats["inflight"], 0)
        pool.close()

    def test_return_foreign_conn_raises_value_error(self):
        # 归还非本池借出的连接 → ValueError
        pool = ConnectionPool(max_size=1)
        with self.assertRaises(ValueError):
            pool.return_conn(FakeConn())
        pool.close()

    def test_double_return_raises_value_error(self):
        # 同一连接归还第二次时已不在在途集合 → ValueError
        pool = ConnectionPool(max_size=1)
        conn = pool.borrow()
        pool.return_conn(conn)
        with self.assertRaises(ValueError):
            pool.return_conn(conn)
        pool.close()

    def test_unhealthy_conn_is_closed_and_discarded(self):
        # README 期望：healthy=False 的连接归还时应立即 close() 并丢弃，
        #             绝不回到空闲队列（idle 保持 0，后续 borrow 拿不到它）。
        # 实际发生：return_conn 不检查 healthy，坏连接原样回到空闲队列，
        #          未被 close，下一次 borrow 还会把这条死连接发出去。
        pool = ConnectionPool(max_size=1)
        conn = pool.borrow()
        conn.healthy = False  # 下游健康探测已判死
        pool.return_conn(conn)
        self.assertTrue(conn.closed, "坏连接归还后应立即被 close()")
        self.assertEqual(pool.stats()["idle"], 0, "坏连接绝不应回到空闲队列")
        pool.close()


class TestCloseSemantics(unittest.TestCase):
    """README 第 3 条：close()。"""

    def test_close_is_idempotent(self):
        pool = ConnectionPool(max_size=1)
        pool.close()
        pool.close()  # 不抛异常即幂等
        self.assertTrue(pool.stats()["closed"])

    def test_close_closes_all_idle_conns(self):
        pool = ConnectionPool(max_size=2)
        conns = [pool.borrow() for _ in range(2)]
        for c in conns:
            pool.return_conn(c)
        pool.close()
        for c in conns:
            self.assertTrue(c.closed)
        self.assertEqual(pool.stats()["idle"], 0)

    def test_inflight_conn_returned_after_close_is_discarded(self):
        # 在途连接随后归还时：直接 close() 丢弃，不进池
        pool = ConnectionPool(max_size=1)
        conn = pool.borrow()
        pool.close()
        pool.return_conn(conn)
        self.assertTrue(conn.closed)
        self.assertEqual(pool.stats()["idle"], 0)

    def test_close_wakes_waiting_borrower_immediately(self):
        # README 期望：正在 borrow 中等待的调用方必须立即收到
        #             PoolClosedError，不允许等到超时。
        # 实际发生：close() 不做 notify，等待者要睡满整个 timeout
        #          （本用例 2s）才醒来发现池已关闭。
        pool = ConnectionPool(max_size=1)
        pool.borrow()  # 占满，让下面的 borrow 进入等待
        entered = threading.Event()
        result = {}

        def waiter():
            entered.set()
            try:
                pool.borrow(timeout=2.0)
                result["error"] = None
            except PoolClosedError as e:
                result["error"] = e
            finally:
                result["elapsed"] = time.monotonic() - result["start"]

        result["start"] = time.monotonic()
        t = threading.Thread(target=waiter)
        t.start()
        self.assertTrue(entered.wait(2.0))
        time.sleep(0.3)  # 确保 waiter 已进入等待
        pool.close()
        t.join(5.0)
        self.assertFalse(t.is_alive())
        self.assertIsInstance(result["error"], PoolClosedError)
        self.assertLess(
            result["elapsed"], 1.0,
            "close() 后等待者应立即收到 PoolClosedError，而不是等满 timeout",
        )


class TestConcurrency(unittest.TestCase):
    """README 第 1、4 条在多线程真实并发下的表现。"""

    def test_concurrent_waiters_are_all_served_before_deadline(self):
        # README 期望：等待期间只要有连接归还就应立即拿到；只有到
        #             deadline 仍没有才允许抛 BorrowTimeout。两个等待者
        #             先后都应拿到连接（一个归还后另一个接着拿到）。
        # 实际发生：borrow 只 wait 一次，return_conn 的 notify_all 把两个
        #          等待者同时唤醒，没抢到连接的那个不等自己的 deadline，
        #          立刻（远早于 5s 超时）抛出 BorrowTimeout。
        pool = ConnectionPool(max_size=1)
        held = pool.borrow()
        started = [threading.Event(), threading.Event()]
        results = []
        lock = threading.Lock()

        def waiter(idx):
            started[idx].set()
            try:
                conn = pool.borrow(timeout=5.0)
                with lock:
                    results.append(("ok", idx))
                time.sleep(0.2)  # 模拟使用
                pool.return_conn(conn)
            except BorrowTimeout:
                with lock:
                    results.append(("timeout", idx))

        threads = [
            threading.Thread(target=waiter, args=(i,)) for i in range(2)
        ]
        for t in threads:
            t.start()
        for e in started:
            self.assertTrue(e.wait(2.0))
        time.sleep(0.3)  # 确保两个 waiter 都已进入等待
        pool.return_conn(held)  # 第一次归还：唤醒等待者
        for t in threads:
            t.join(8.0)
        for t in threads:
            self.assertFalse(t.is_alive())
        self.assertEqual(
            sorted(results), [("ok", 0), ("ok", 1)],
            "两个等待者都应在 deadline 前拿到连接，不允许提前 BorrowTimeout",
        )
        pool.close()

    def test_stress_borrow_return_and_created_capped(self):
        # README 第 4 条：连接创建总数不超过 max_size。
        # 4 线程 x 50 轮真实并发借还，不应有任何异常。
        pool = ConnectionPool(max_size=4, borrow_timeout=5.0)
        errors = []
        lock = threading.Lock()
        barrier = threading.Barrier(4)

        def worker():
            try:
                barrier.wait(timeout=5.0)  # 同时起跑，制造真实竞争
                for _ in range(50):
                    conn = pool.borrow()
                    pool.return_conn(conn)
            except Exception as e:  # noqa: BLE001
                with lock:
                    errors.append(e)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(15.0)
        for t in threads:
            self.assertFalse(t.is_alive())
        self.assertEqual(errors, [])
        stats = pool.stats()
        self.assertLessEqual(stats["created"], 4)
        self.assertGreaterEqual(stats["created"], 1)
        pool.close()


if __name__ == "__main__":
    unittest.main()
