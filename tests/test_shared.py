"""SharedLimiter 行为测试：多实例共享额度、本地预领与归还、掉线
回收、时钟不齐下的窗口对齐、存储故障的两种降级口径。

全部用假时钟假存储，不做真实 sleep。
"""
import unittest

from quota import DEFAULT_KEY, InMemoryStore, SharedLimiter


class FakeClock:
    """手动推进的假时钟，避免测试真实 sleep。"""

    def __init__(self, now=1000.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class CountingStore:
    """统计 claim 次数的包装，验证批量预领省了远程往返。"""

    def __init__(self, inner):
        self.inner = inner
        self.claim_calls = 0

    def now(self):
        return self.inner.now()

    def claim(self, *args):
        self.claim_calls += 1
        return self.inner.claim(*args)

    def release(self, *args):
        return self.inner.release(*args)

    def usage(self, *args):
        return self.inner.usage(*args)


class FlakyStore:
    """可开关故障的假存储，down 期间所有操作抛错。"""

    def __init__(self, clock):
        self.inner = InMemoryStore(clock=clock)
        self.down = False

    def _check(self):
        if self.down:
            raise IOError("存储抖动")

    def now(self):
        self._check()
        return self.inner.now()

    def claim(self, *args):
        self._check()
        return self.inner.claim(*args)

    def release(self, *args):
        self._check()
        return self.inner.release(*args)

    def usage(self, *args):
        self._check()
        return self.inner.usage(*args)


class TestSharedQuota(unittest.TestCase):
    def test_six_instances_share_one_quota(self):
        clock = FakeClock()
        store = InMemoryStore(clock=clock)
        nodes = [SharedLimiter(store, limit=12, window=1.0, batch=2,
                               owner="n%d" % i, clock=clock)
                 for i in range(6)]
        results = [node.allow() for _ in range(2) for node in nodes]
        self.assertEqual(results.count(True), 12)
        self.assertFalse(nodes[0].allow())
        self.assertEqual(nodes[0].remaining(), 0)

    def test_batch_prefetch_saves_remote_calls(self):
        clock = FakeClock()
        store = CountingStore(InMemoryStore(clock=clock))
        lim = SharedLimiter(store, limit=100, window=1.0, batch=10,
                            clock=clock)
        self.assertEqual(lim.remaining(), 100)
        self.assertTrue(all(lim.allow() for _ in range(25)))
        self.assertEqual(store.claim_calls, 3)  # 25 次请求只回源 3 次

    def test_close_returns_unspent_quota(self):
        clock = FakeClock()
        store = InMemoryStore(clock=clock)
        a = SharedLimiter(store, limit=10, window=1.0, batch=5,
                          owner="a", clock=clock)
        b = SharedLimiter(store, limit=10, window=1.0, batch=10,
                          owner="b", clock=clock)
        self.assertTrue(a.allow())  # a 领 5 花 1，手里剩 4
        a.close()
        self.assertEqual(store.usage(DEFAULT_KEY, 1000.0), 1)
        self.assertEqual([b.allow() for _ in range(10)].count(True), 9)

    def test_rollover_releases_unspent_to_old_window(self):
        clock = FakeClock()
        store = InMemoryStore(clock=clock)
        lim = SharedLimiter(store, limit=10, window=1.0, batch=6,
                            clock=clock)
        lim.allow()
        lim.allow()  # 领 6 花 2，剩 4
        self.assertEqual(store.usage(DEFAULT_KEY, 1000.0), 6)
        clock.advance(1.0)
        self.assertTrue(lim.allow())  # 跨窗：归还旧窗口 4 个，再领新批
        self.assertEqual(store.usage(DEFAULT_KEY, 1000.0), 2)
        self.assertEqual(store.usage(DEFAULT_KEY, 1001.0), 6)

    def test_crashed_instance_quota_reclaimed_after_lease_expires(self):
        clock = FakeClock()
        store = InMemoryStore(clock=clock)
        a = SharedLimiter(store, limit=10, window=10.0, batch=8,
                          owner="a", lease_ttl=5.0, clock=clock)
        b = SharedLimiter(store, limit=10, window=10.0, batch=4,
                          owner="b", lease_ttl=5.0, clock=clock)
        a.allow()
        a.allow()  # a 领 8 花 2 后宕机（此后不再有任何调用）
        clock.advance(4.0)  # 租约未到期，a 占着的额度还拿不回来
        self.assertEqual([b.allow() for _ in range(3)].count(True), 2)
        clock.advance(2.0)  # 超过租约，a 的租约被回收，额度腾出来了
        # a 认领未归还的 8 个被整批回收（含已花未报的零头，见 README）
        self.assertEqual([b.allow() for _ in range(8)].count(True), 8)

    def test_window_alignment_with_skewed_clocks(self):
        store_clock = FakeClock(1000.0)
        store = InMemoryStore(clock=store_clock)
        # 两台实例本地时钟差 2 秒，窗口仍按存储时钟对齐
        a = SharedLimiter(store, limit=4, window=10.0, batch=1,
                          owner="a", clock=FakeClock(998.0))
        b = SharedLimiter(store, limit=4, window=10.0, batch=1,
                          owner="b", clock=FakeClock(1002.0))
        results = [a.allow(), b.allow(), a.allow(), b.allow(), a.allow()]
        self.assertEqual(results, [True, True, True, True, False])
        self.assertEqual(store.usage(DEFAULT_KEY, 1000.0), 4)
        self.assertEqual(store.usage(DEFAULT_KEY, 990.0), 0)
        self.assertEqual(store.usage(DEFAULT_KEY, 1010.0), 0)
        store_clock.advance(10.0)  # 存储时钟跨窗，配额整体重置
        self.assertTrue(a.allow())
        self.assertEqual(store.usage(DEFAULT_KEY, 1010.0), 1)

    def test_rejects_invalid_args(self):
        store = InMemoryStore(clock=FakeClock())
        with self.assertRaises(ValueError):
            SharedLimiter(store, limit=0)
        with self.assertRaises(ValueError):
            SharedLimiter(store, limit=1, batch=0)
        with self.assertRaises(ValueError):
            SharedLimiter(store, limit=1, on_error="maybe")


class TestStoreFailure(unittest.TestCase):
    def test_fail_closed_by_default(self):
        clock = FakeClock()
        store = FlakyStore(clock)
        lim = SharedLimiter(store, limit=5, window=1.0, batch=1,
                            clock=clock)
        store.down = True
        self.assertFalse(lim.allow())

    def test_fail_open_per_key(self):
        clock = FakeClock()
        store = FlakyStore(clock)
        lim = SharedLimiter(store, limit=5, window=1.0, batch=1,
                            clock=clock, key_on_error={"vip": "open"})
        store.down = True
        self.assertTrue(lim.allow("vip"))
        self.assertFalse(lim.allow("bulk"))
        store.down = False
        self.assertTrue(lim.allow("bulk"))  # 恢复后正常记账
        self.assertEqual(store.usage("bulk", 1000.0), 1)
        self.assertEqual(store.usage("vip", 1000.0), 0)  # 降级放行没记账


if __name__ == "__main__":
    unittest.main()
