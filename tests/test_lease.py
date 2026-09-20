"""LeaseElection / FencedStore 行为测试。

覆盖租约选举的核心语义：续约失败的判定尺度、候选者静默观察窗口、
fencing token 挡过期主、时钟异常下的安全性、主备切换时的状态交接。
"""
import os
import tempfile
import time
import unittest

from lease import (
    FencedStore,
    LeaseElection,
    LeaseLostError,
    StaleFencingTokenError,
)


class FakeClock:
    def __init__(self, t=1000.0):
        self.t = t

    def __call__(self):
        return self.t


class LeaseCase(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "primary.lease")
        self.clock = FakeClock()
        self.wall = FakeClock()

    def make(self, node_id, clock=None):
        return LeaseElection(self.path, node_id, lease_duration=10.0,
                             renew_interval=3.0,
                             clock=clock or self.clock, wall_clock=self.wall)


class TestAcquire(LeaseCase):
    def test_first_acquire_wins(self):
        a = self.make("node-a")
        self.assertTrue(a.try_acquire())
        self.assertTrue(a.is_primary())
        self.assertEqual(a.fencing_token, 1)

    def test_reacquire_by_holder_is_idempotent(self):
        a = self.make("node-a")
        a.try_acquire()
        self.clock.t += 5
        self.assertTrue(a.try_acquire())
        self.assertEqual(a.fencing_token, 1)

    def test_takeover_requires_full_silence_window(self):
        """候选者必须观察到记录静止满一个租约期才能接手。"""
        a = self.make("node-a")
        b = self.make("node-b")
        a.try_acquire()
        self.assertFalse(b.try_acquire())   # 第一次看到记录，开始计时
        self.clock.t += 5
        a.renew()                            # 记录变了，窗口重算
        self.clock.t += 6                    # 距首次观察已 11s，但记录 6s 前才动过
        self.assertFalse(b.try_acquire())
        self.clock.t += 10.1                 # a 一直没再续租，静默满一个租约期
        self.assertTrue(b.try_acquire())
        self.assertEqual(b.fencing_token, 2)

    def test_live_holder_keeps_standby_out(self):
        """主正常续租时，备机无论等多久、墙钟怎么偏都抢不走。"""
        a = self.make("node-a")
        b = self.make("node-b")
        a.try_acquire()
        b.try_acquire()                      # 开始观察
        for _ in range(10):
            self.clock.t += 5
            self.wall.t += 15                # 备机视角墙钟快得离谱也没用
            a.renew()
            self.assertFalse(b.try_acquire())
        self.assertTrue(a.is_primary())

    def test_corrupt_record_blocks_takeover(self):
        """记录读不出来时按状况不明处理：宁可无主。"""
        a = self.make("node-a")
        b = self.make("node-b")
        a.try_acquire()
        with open(self.path, "wb") as f:
            f.write(b"\xff\xfe not json")
        self.clock.t += 30
        self.assertFalse(b.try_acquire())


class TestRenew(LeaseCase):
    def test_renew_extends_lease(self):
        a = self.make("node-a")
        a.try_acquire()
        for _ in range(6):
            self.clock.t += 5                # 每次都在截止前续上
            self.assertTrue(a.renew())
            self.assertTrue(a.is_primary())

    def test_lease_expires_without_renew(self):
        """模拟 GC 停顿：过了租约期没续上，自动认输。"""
        a = self.make("node-a")
        a.try_acquire()
        self.clock.t += 30                   # 进程像被 GC 卡住 30s
        self.assertFalse(a.is_primary())
        self.assertIsNone(a.fencing_token)
        with self.assertRaises(LeaseLostError):
            a.assert_primary()

    def test_single_renew_failure_is_tolerated(self):
        """一次 IO 抖动不判负，只要在截止前续上就还是主。"""
        a = self.make("node-a")
        a.try_acquire()
        original = a._fenced_update

        def boom(*args, **kw):
            raise OSError("抖一下")

        a._fenced_update = boom
        self.clock.t += 3
        self.assertFalse(a.renew())          # 这次失败了
        self.assertTrue(a.is_primary())      # 但租约还在
        a._fenced_update = original
        self.clock.t += 3
        self.assertTrue(a.renew())           # 截止前续上，一切照旧

    def test_renew_after_expiry_is_refused(self):
        """租约已过期就不许续命，只能走 try_acquire 重新抢。"""
        a = self.make("node-a")
        a.try_acquire()
        self.clock.t += 11
        self.assertFalse(a.renew())
        self.assertFalse(a.is_primary())
        b = self.make("node-b")
        self.assertEqual(b.current_holder(), "node-a")  # 记录没被偷偷续上

    def test_renew_conflict_forfeits_immediately(self):
        """续租时发现记录已属他人，立即认输，不等本地截止。"""
        clock_a = FakeClock()
        clock_b = FakeClock()
        a = self.make("node-a", clock=clock_a)
        b = self.make("node-b", clock=clock_b)
        a.try_acquire()
        clock_b.t += 11
        b.try_acquire()                      # 开始观察静止的记录
        clock_b.t += 10.1                    # 静默满一个租约期
        b.try_acquire()                      # b 接手，token = 2
        self.assertTrue(a.is_primary())      # a 的钟没动，自以为还是主
        self.assertFalse(a.renew())          # 一续租就撞见记录易主
        self.assertFalse(a.is_primary())     # 立即认输


class TestFencing(LeaseCase):
    def test_fenced_store_rejects_stale_primary(self):
        """GC 停顿醒来的旧主，拿着老 token 写不进存储层。"""
        a = self.make("node-a")
        b = self.make("node-b")
        store = FencedStore()
        a.try_acquire()
        store.write("order-1", "paid", a.assert_primary())
        self.clock.t += 30                   # a 被 GC 卡住
        b.try_acquire()                      # 开始观察静止的记录
        self.clock.t += 10.1                 # 静默满一个租约期
        b.try_acquire()                      # b 接手，token = 2
        with self.assertRaises(LeaseLostError):
            a.assert_primary()               # 第一关：a 本地已认输
        with self.assertRaises(StaleFencingTokenError):
            store.write("order-1", "refunded", 1)  # 第二关：老 token 被挡
        store.write("order-1", "shipped", b.assert_primary())
        self.assertEqual(store.read("order-1"), "shipped")

    def test_assert_primary_returns_fencing_token(self):
        a = self.make("node-a")
        a.try_acquire()
        self.assertEqual(a.assert_primary(), 1)
        self.assertEqual(a.assert_primary(), a.fencing_token)


class TestRelease(LeaseCase):
    def test_release_allows_immediate_handover(self):
        """主动让位写了标记，备机不必等满静默窗口。"""
        a = self.make("node-a")
        b = self.make("node-b")
        a.try_acquire()
        a.release()
        self.assertFalse(a.is_primary())
        self.assertIsNone(a.current_holder())
        self.assertTrue(b.try_acquire())     # 第一次尝试就成功
        self.assertEqual(b.fencing_token, 2)  # token 仍然单调递增

    def test_release_is_idempotent(self):
        a = self.make("node-a")
        a.release()
        a.try_acquire()
        a.release()
        a.release()
        self.assertFalse(a.is_primary())


class TestHandover(LeaseCase):
    def test_state_handover_on_failover(self):
        """主把交接状态写进租约记录，新主接手后读出来继续。"""
        a = self.make("node-a")
        b = self.make("node-b")
        a.try_acquire()
        self.assertTrue(a.update_state({"last_order_id": 42}))
        self.clock.t += 30                   # a 宕机
        b.try_acquire()                      # 开始观察静止的记录
        self.clock.t += 10.1                 # 静默满一个租约期
        self.assertTrue(b.try_acquire())
        self.assertEqual(b.handover_state(), {"last_order_id": 42})

    def test_handover_state_empty_without_record(self):
        self.assertEqual(self.make("node-a").handover_state(), {})


class TestClockAnomaly(LeaseCase):
    def test_wall_clock_jump_does_not_affect_validity(self):
        """墙钟被回拨/拨快都不影响本地租约判断（只看单调时钟）。"""
        a = self.make("node-a")
        a.try_acquire()
        self.wall.t -= 500                   # 墙钟被拨回去
        self.assertTrue(a.is_primary())
        self.clock.t += 3
        self.assertTrue(a.renew())
        self.wall.t += 100000                # 墙钟被拨到未来
        self.assertTrue(a.is_primary())

    def test_skewed_node_cannot_take_over_early(self):
        """时钟偏快的节点也抢不走还在续租的主。"""
        clock_fast = FakeClock(t=1000.0)
        a = self.make("node-a")
        b = LeaseElection(self.path, "node-b", lease_duration=10.0,
                          clock=clock_fast, wall_clock=self.wall)
        a.try_acquire()
        b.try_acquire()
        for _ in range(5):
            self.clock.t += 2
            clock_fast.t += 20               # b 的钟跑得飞快
            a.renew()
            self.assertFalse(b.try_acquire())


class TestBackgroundRenewal(unittest.TestCase):
    def test_background_thread_keeps_lease_alive(self):
        path = os.path.join(tempfile.mkdtemp(), "bg.lease")
        a = LeaseElection(path, "node-a", lease_duration=0.4,
                          renew_interval=0.1)
        self.assertTrue(a.try_acquire())
        a.start()
        try:
            time.sleep(0.6)                  # 超过一个租约期，靠后台续租保持
            self.assertTrue(a.is_primary())
            a.stop()
            time.sleep(0.5)                  # 停租后自然到期
            self.assertFalse(a.is_primary())
        finally:
            a.close()


if __name__ == "__main__":
    unittest.main()
