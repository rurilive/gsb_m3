"""netpool 语义测试。

用例与 README「语义约定」逐条对应：

- TestBorrowSemantics -> 第 1 条 borrow(timeout=None)
- TestReturnSemantics -> 第 2 条 return_conn(conn)
- TestCloseSemantics  -> 第 3 条 close()
- TestCreatedBound    -> 第 4 条 stats()["created"] <= max_size
- TestConcurrency     -> 真实多线程并发（threading + Event/Barrier 同步）

红用例（源码与 README 有出入，当前必然失败）以 RED #N 编号，每个用例上方
注明「README 期望 / 实际行为」；缺陷汇总与修复方向见 README「测试报告」。

并发用例全部用 Event / Barrier 控制执行节奏，不依赖 sleep 碰运气；
join/超时断言只留宽松上限，避免环境抖动造成误报。
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


def wait_until(predicate, timeout):
    """轮询等待谓词成立，最长 timeout 秒；只用于观察其他线程的状态。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.005)
    return predicate()


def run_in_thread(target, errors):
    """启动捕获异常的 daemon 线程并返回线程对象。

    daemon 仅用于在「等待者被永久挂起」这类缺陷出现时不挂住测试进程；
    正常用例的节奏完全由 join / Event / Barrier 决定，不依赖 daemon 语义。
    """

    def wrapper():
        try:
            target()
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    thread = threading.Thread(target=wrapper, daemon=True)
    thread.start()
    return thread


class ObservableCondition(threading.Condition):
    """带探针的 Condition：wait() 真正进入等待前回调 on_enter_wait。

    回调在持有条件锁时执行，可精确表达「该线程已经进入等待、尚未醒来」
    这一同步点。注意回调不能阻塞等待另一个需要同一把条件锁的线程
    （经典自死锁），所以探针回调里只允许用非阻塞原语（Event.set 等）。
    """

    def __init__(self):
        super().__init__()
        self.on_enter_wait = lambda: None

    def wait(self, timeout=None):
        self.on_enter_wait()
        return super().wait(timeout)


def install_observable_condition(pool):
    """替换池内部 Condition，供并发用例观察「进入等待」时刻。"""
    cond = ObservableCondition()
    pool._cond = cond
    return cond


class TestBorrowSemantics(unittest.TestCase):
    """README 第 1 条：borrow(timeout=None)。"""

    def setUp(self):
        self.pool = ConnectionPool(max_size=2, borrow_timeout=1.0)

    def tearDown(self):
        self.pool.close()

    def test_idle_conn_taken_and_marked_inflight(self):
        conn = self.pool.borrow()
        self.pool.return_conn(conn)
        self.assertEqual(self.pool.stats()["idle"], 1)

        again = self.pool.borrow()
        self.assertIs(again, conn)
        stats = self.pool.stats()
        self.assertEqual(stats["inflight"], 1)
        self.assertEqual(stats["idle"], 0)

    def test_new_conn_created_when_idle_empty_and_not_full(self):
        first = self.pool.borrow()
        second = self.pool.borrow()
        self.assertIsNot(first, second)
        stats = self.pool.stats()
        self.assertEqual(stats["inflight"], 2)
        self.assertEqual(stats["created"], 2)

    def test_factory_receives_sequence_and_builds_conn(self):
        built = []

        def factory(seq):
            conn = FakeConn()
            built.append((seq, conn))
            return conn

        pool = ConnectionPool(factory=factory, max_size=2)
        conn = pool.borrow()
        self.assertEqual(built, [(0, conn)])
        pool.close()

    def test_pool_full_times_out_only_at_deadline(self):
        self.pool.borrow()
        self.pool.borrow()

        start = time.monotonic()
        with self.assertRaises(BorrowTimeout):
            self.pool.borrow(timeout=0.3)
        elapsed = time.monotonic() - start
        self.assertGreaterEqual(elapsed, 0.25)
        self.assertLess(elapsed, 3.0)

    def test_borrow_on_closed_pool_raises_pool_closed(self):
        self.pool.close()
        with self.assertRaises(PoolClosedError):
            self.pool.borrow()

    def test_borrow_without_timeout_uses_default_and_times_out_when_full(self):
        # demo.py 依赖无参 borrow() 在池满时最终超时而不是永久挂起。
        pool = ConnectionPool(max_size=1, borrow_timeout=0.2)
        pool.borrow()
        with self.assertRaises(BorrowTimeout):
            pool.borrow()
        pool.close()

    # ------------------------------------------------------------------
    # RED #1（README 第 1 条）
    # README 期望：池满等待期间只要有连接归还就应立即拿到；没抢到的
    #             等待者继续等下一次归还，到 deadline 仍没有才抛
    #             BorrowTimeout。
    # 实际行为：return_conn 的 notify_all 同时唤醒两个等待者，抢到连接
    #           的拿走；抢输的那个走到 borrow() 末尾「没到 deadline 却
    #           什么都没拿到」分支，被直接 raise BorrowTimeout，不会
    #           继续等待——尽管它的 deadline 是 30s 且下一次归还马上
    #           就会发生。
    # ------------------------------------------------------------------
    def test_loser_of_wakeup_race_keeps_waiting_until_next_return(self):
        pool = ConnectionPool(max_size=1, borrow_timeout=30)
        cond = install_observable_condition(pool)
        holder = pool.borrow()

        parked_count = [0]
        both_parked = threading.Event()
        results = []
        errors = []

        def mark_parked():
            parked_count[0] += 1
            if parked_count[0] >= 2:
                both_parked.set()

        def waiter():
            try:
                results.append(pool.borrow(timeout=30))
            except BaseException as exc:  # noqa: BLE001
                errors.append(exc)

        cond.on_enter_wait = mark_parked
        w1 = run_in_thread(waiter, errors)
        w2 = run_in_thread(waiter, errors)
        # 两个等待者都进入条件变量等待后主线程才归还，节奏与调度无关。
        self.assertTrue(both_parked.wait(timeout=5), "等待者未在时限内全部进入等待")
        cond.on_enter_wait = lambda: None

        pool.return_conn(holder)
        self.assertTrue(
            wait_until(lambda: bool(results) or bool(errors), 5.0),
            "第一次归还后没有任何等待者被唤醒",
        )
        self.assertEqual(len(results), 1)
        winner_conn = results[0]

        # 获胜者线程结束时连接仍在途；主线程替它归还，抢输者应立即接手。
        pool.return_conn(winner_conn)
        w1.join(timeout=5)
        w2.join(timeout=5)
        self.assertFalse(w1.is_alive(), "等待者 w1 异常挂起")
        self.assertFalse(w2.is_alive(), "等待者 w2 异常挂起")

        self.assertEqual(errors, [], "抢输唤醒竞争的等待者不应提前超时")
        self.assertEqual(len(results), 2)
        self.assertEqual({c.cid for c in results}, {winner_conn.cid})
        pool.return_conn(results[1])
        pool.close()


class TestReturnSemantics(unittest.TestCase):
    """README 第 2 条：return_conn(conn)。"""

    def setUp(self):
        self.pool = ConnectionPool(max_size=2, borrow_timeout=1.0)

    def tearDown(self):
        self.pool.close()

    def test_healthy_return_enters_idle_queue(self):
        conn = self.pool.borrow()
        self.pool.return_conn(conn)
        stats = self.pool.stats()
        self.assertEqual(stats["idle"], 1)
        self.assertEqual(stats["inflight"], 0)
        self.assertFalse(conn.closed)
        self.assertIs(self.pool.borrow(), conn)

    def test_return_foreign_connection_raises_value_error(self):
        other = ConnectionPool(max_size=2)
        foreign = other.borrow()
        with self.assertRaises(ValueError):
            self.pool.return_conn(foreign)
        with self.assertRaises(ValueError):
            self.pool.return_conn(FakeConn())
        other.close()

    def test_double_return_raises_value_error(self):
        conn = self.pool.borrow()
        self.pool.return_conn(conn)
        with self.assertRaises(ValueError):
            self.pool.return_conn(conn)

    # ------------------------------------------------------------------
    # RED #2（README 第 2 条）
    # README 期望：conn.healthy 为 False 的连接归还时立即 close() 并
    #             丢弃，绝不回到空闲队列。
    # 实际行为：return_conn 根本不检查 healthy，坏连接被原样 append 进
    #           空闲队列，conn.closed 保持 False，下一次 borrow 会把这
    #           条已被下游健康探测判死的连接再次发给调用方。
    # ------------------------------------------------------------------
    def test_unhealthy_return_is_closed_and_never_reused(self):
        conn = self.pool.borrow()
        conn.healthy = False
        self.pool.return_conn(conn)

        self.assertTrue(conn.closed, "坏连接归还后应被立即 close()")
        self.assertEqual(
            self.pool.stats()["idle"], 0, "坏连接绝不允许回到空闲队列"
        )

        replacement = self.pool.borrow()
        self.assertIsNot(replacement, conn, "不应再次借出已判死的连接")
        self.assertTrue(replacement.healthy)
        self.pool.return_conn(replacement)


class TestCloseSemantics(unittest.TestCase):
    """README 第 3 条：close()。"""

    def test_close_is_idempotent(self):
        pool = ConnectionPool(max_size=2)
        pool.close()
        pool.close()
        self.assertTrue(pool.stats()["closed"])

    def test_close_closes_all_idle_conns(self):
        pool = ConnectionPool(max_size=3)
        conns = [pool.borrow() for _ in range(3)]
        for conn in conns:
            pool.return_conn(conn)
        pool.close()
        self.assertTrue(all(conn.closed for conn in conns))

    def test_inflight_conn_returned_after_close_is_discarded(self):
        pool = ConnectionPool(max_size=2)
        conn = pool.borrow()
        pool.close()
        self.assertFalse(conn.closed)
        pool.return_conn(conn)
        self.assertTrue(conn.closed)
        self.assertEqual(pool.stats()["idle"], 0)

    def test_borrow_after_close_raises_pool_closed(self):
        pool = ConnectionPool(max_size=1)
        pool.close()
        with self.assertRaises(PoolClosedError):
            pool.borrow()

    # ------------------------------------------------------------------
    # RED #3（README 第 3 条）
    # README 期望：close() 后正在 borrow 中等待的调用方必须立即收到
    #             PoolClosedError，不允许等到超时。
    # 实际行为：close() 只置 _closed 并关闭空闲连接，没有 notify_all()；
    #           等待者一直阻塞到自身 timeout（本用例给 30s）才醒来看到
    #           _closed。缺陷存在时 join(6) 超时、is_alive() 为真，
    #           用例失败，不会挂死进程（等待线程是 daemon）。
    # ------------------------------------------------------------------
    def test_waiting_borrower_raises_immediately_when_pool_closed(self):
        pool = ConnectionPool(max_size=1, borrow_timeout=30)
        cond = install_observable_condition(pool)
        holder = pool.borrow()

        parked = threading.Event()
        errors = []
        cond.on_enter_wait = parked.set
        waiter = run_in_thread(lambda: pool.borrow(timeout=30), errors)
        self.assertTrue(parked.wait(timeout=5), "等待者未在时限内进入等待")

        start = time.monotonic()
        pool.close()
        waiter.join(timeout=6)
        elapsed = time.monotonic() - start

        self.assertFalse(waiter.is_alive(), "close 后等待者仍被挂起")
        self.assertLess(elapsed, 3.0, "等待者必须被立即唤醒，而不是等满 30s")
        self.assertEqual(len(errors), 1)
        self.assertIsInstance(errors[0], PoolClosedError)
        pool.return_conn(holder)


class TestCreatedBound(unittest.TestCase):
    """README 第 4 条：连接创建总数不超过 max_size。"""

    def test_initial_created_is_zero(self):
        pool = ConnectionPool(max_size=2)
        self.assertEqual(pool.stats()["created"], 0)
        pool.close()

    def test_created_never_exceeds_max_size_with_reuse_loop(self):
        pool = ConnectionPool(max_size=3, borrow_timeout=0.1)
        for _ in range(20):
            try:
                conn = pool.borrow(timeout=0.05)
            except BorrowTimeout:
                continue
            pool.return_conn(conn)
        self.assertLessEqual(pool.stats()["created"], 3)
        pool.close()


class TestConcurrency(unittest.TestCase):
    """真实多线程场景；节奏全部由 Event/Barrier + join 定死。"""

    def test_parallel_borrow_return_created_bounded(self):
        # 线程数 == max_size：不经过池满等待分支，纯粹并发借还，
        # 钉住 created 上限与空闲/在途记账（8 线程各 100 轮真实并发）。
        thread_count = 8
        pool = ConnectionPool(max_size=thread_count, borrow_timeout=5.0)
        start_gate = threading.Barrier(thread_count)
        errors = []

        def worker():
            start_gate.wait()
            for _ in range(100):
                conn = pool.borrow(timeout=5)
                pool.return_conn(conn)

        threads = [run_in_thread(worker, errors) for _ in range(thread_count)]
        for thread in threads:
            thread.join(timeout=30)

        self.assertFalse(any(t.is_alive() for t in threads), "有工作线程挂起")
        self.assertEqual(errors, [])
        stats = pool.stats()
        self.assertEqual(stats["inflight"], 0)
        self.assertEqual(stats["idle"], stats["created"])
        self.assertLessEqual(stats["created"], thread_count)
        pool.close()

    def test_serial_handoff_chain_wakes_each_waiter_immediately(self):
        # 真实多线程 + 池满等待：池容量 1，初始连接在主线程手里。
        # 5 个工作线程严格接力：先放行线程 i 进入等待（探针确认），
        # 再由当前持有者归还，线程 i 立即拿到连接成为新持有者；
        # 任一时刻最多一个等待者，从而隔离 RED #1 的多等待者唤醒
        # 竞争路径，单独钉住 README 第 1 条「等待期间只要有连接
        # 归还，应立即拿到它」。
        pool = ConnectionPool(max_size=1, borrow_timeout=5.0)
        cond = install_observable_condition(pool)
        holder = pool.borrow()

        worker_count = 5
        start_signals = [threading.Event() for _ in range(worker_count)]
        borrowed_events = [threading.Event() for _ in range(worker_count)]
        release_events = [threading.Event() for _ in range(worker_count)]
        errors = []
        conns = []
        conn_lock = threading.Lock()
        parked = threading.Event()

        def worker(index):
            try:
                start_signals[index].wait(timeout=10)
                # 池满：必然进入条件变量等待，直到当前持有者归还。
                conn = pool.borrow(timeout=5)
                with conn_lock:
                    conns.append((index, conn))
                borrowed_events[index].set()
                # 连接暂由该工作线程持有，直到主线程安排它归还。
                release_events[index].wait(timeout=10)
                pool.return_conn(conn)
            except BaseException as exc:  # noqa: BLE001
                errors.append((index, exc))

        threads = [
            run_in_thread(lambda i=i: worker(i), errors)
            for i in range(worker_count)
        ]

        current = holder
        for i in range(worker_count):
            # 清探针并放行线程 i：它只能在池满分支等待。
            parked.clear()
            cond.on_enter_wait = parked.set
            start_signals[i].set()
            self.assertTrue(
                parked.wait(timeout=5), "第 %d 个工作线程未进入等待" % i
            )
            cond.on_enter_wait = lambda: None

            # 当前持有者归还（i==0 时由主线程归还初始连接）。
            if i == 0:
                pool.return_conn(current)
            else:
                release_events[i - 1].set()

            self.assertTrue(
                borrowed_events[i].wait(timeout=5),
                "第 %d 个等待者未在归还后立即拿到连接" % i,
            )
            self.assertEqual(errors, [])
            current = next(c for idx, c in conns if idx == i)

        # 末位工作线程归还，全部线程收尾。
        release_events[worker_count - 1].set()
        for thread in threads:
            thread.join(timeout=5)
            self.assertFalse(thread.is_alive(), "有工作线程挂起")
        self.assertEqual(errors, [])
        # 同一条连接在主线程 + 5 个工作线程间接力，全程只创建了 1 条。
        self.assertEqual(len(conns), worker_count)
        self.assertTrue(
            wait_until(lambda: pool.stats()["idle"] == 1, 5.0),
            "末位工作线程归还后连接应回到空闲队列",
        )
        self.assertEqual(pool.stats()["created"], 1)
        self.assertEqual({c.cid for _, c in conns}, {holder.cid})
        pool.close()

    def test_concurrent_borrowers_after_close_all_get_pool_closed(self):
        # 池容量 2，4 个线程同时借：2 个拿到连接进入在途，2 个等待。
        # close() 后：等待者必须立即收到 PoolClosedError（README 第 3 条
        # 的并发版本，对应 RED #3）；在途者之后归还时连接被 close 丢弃
        # （README 第 3 条第 3 点）。
        pool = ConnectionPool(max_size=2, borrow_timeout=30)
        cond = install_observable_condition(pool)

        borrower_count = 4
        start_gate = threading.Barrier(borrower_count)
        parked_count = [0]
        two_parked = threading.Event()
        borrowed = []
        errors = []
        list_lock = threading.Lock()

        def mark_parked():
            parked_count[0] += 1
            if parked_count[0] >= 2:
                two_parked.set()

        def borrower():
            start_gate.wait()
            try:
                conn = pool.borrow(timeout=30)
            except BaseException as exc:  # noqa: BLE001
                with list_lock:
                    errors.append(exc)
                return
            with list_lock:
                borrowed.append(conn)

        cond.on_enter_wait = mark_parked
        threads = [run_in_thread(borrower, errors) for _ in range(borrower_count)]
        self.assertTrue(two_parked.wait(timeout=5), "等待的两个线程未全部挂起")
        cond.on_enter_wait = lambda: None
        self.assertTrue(
            wait_until(lambda: len(borrowed) == 2, 5.0),
            "应有两个线程借到连接",
        )

        start = time.monotonic()
        pool.close()
        for thread in threads:
            thread.join(timeout=6)
        elapsed = time.monotonic() - start

        for thread in threads:
            self.assertFalse(thread.is_alive(), "close 后仍有线程挂起")
        self.assertLess(elapsed, 3.0, "等待者必须在 close 后立即收到异常")
        self.assertEqual(len(errors), 2)
        self.assertTrue(all(isinstance(e, PoolClosedError) for e in errors))
        for conn in borrowed:
            pool.return_conn(conn)
            self.assertTrue(conn.closed, "在途连接关闭后归还应被立即 close")
        self.assertEqual(pool.stats()["idle"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
