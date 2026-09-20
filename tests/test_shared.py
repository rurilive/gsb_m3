"""SharedLimiter 行为：多实例共享一份配额，假时钟假存储，不真 sleep。"""
import unittest

from quota import InMemoryLeaseStore, SharedLimiter


class FakeClock:
    """手动推进的假时钟。"""

    def __init__(self, now=1000.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class SkewedClock:
    """跟着基准时钟走、但带固定偏移的实例本地时钟。"""

    def __init__(self, base, skew):
        self.base = base
        self.skew = skew

    def __call__(self):
        return self.base.now + self.skew


class FlakyStore:
    """包装 InMemoryLeaseStore，可开关故障注入。"""

    def __init__(self, inner):
        self.inner = inner
        self.healthy = True

    def now(self):
        if not self.healthy:
            raise ConnectionError("store down")
        return self.inner.now()

    def acquire(self, *args):
        if not self.healthy:
            raise ConnectionError("store down")
        return self.inner.acquire(*args)

    def release(self, *args):
        if not self.healthy:
            raise ConnectionError("store down")
        return self.inner.release(*args)


def make_limiter(store, clock, owner, **kw):
    args = dict(limit=6, window=1.0, store=store, clock=clock,
                batch=2, lease_ttl=10.0, owner=owner)
    args.update(kw)
    return SharedLimiter(**args)


class TestSharedQuota(unittest.TestCase):
    def test_instances_share_one_quota(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(clock=clock)
        nodes = [make_limiter(store, clock, "node-%d" % i) for i in range(6)]
        granted = [n.allow() for n in nodes for _ in range(2)]
        self.assertEqual(granted.count(True), 6)
        self.assertFalse(nodes[0].allow())

    def test_keys_are_isolated(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(clock=clock)
        node = make_limiter(store, clock, "node-0", limit=1, batch=1)
        self.assertTrue(node.allow("a"))
        self.assertTrue(node.allow("b"))
        self.assertFalse(node.allow("a"))


class TestBatchLease(unittest.TestCase):
    def test_prefetch_batch_then_consume_locally(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(clock=clock)
        node = make_limiter(store, clock, "node-0", limit=10, batch=4)
        self.assertTrue(node.allow())
        self.assertEqual(store.held("default", 1000.0), 4)  # 一次远程预领 4 个
        for _ in range(3):
            self.assertTrue(node.allow())
        self.assertEqual(store.held("default", 1000.0), 4)  # 本地消化，不再远程
        self.assertEqual(node.remaining(), 0)
        self.assertTrue(node.allow())  # 花完再领一批
        self.assertEqual(store.held("default", 1000.0), 8)

    def test_close_returns_unused_quota(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(clock=clock)
        holder = make_limiter(store, clock, "holder", limit=4, batch=4)
        other = make_limiter(store, clock, "other", limit=4, batch=4)
        self.assertTrue(holder.allow())          # 领走 4，只用 1
        self.assertFalse(other.allow())          # 额度被预领光
        holder.close()                           # 主动归还没用完的 3 个
        self.assertEqual(store.held("default", 1000.0), 1)
        self.assertTrue(other.allow())

    def test_window_rollover_returns_and_renews(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(clock=clock)
        node = make_limiter(store, clock, "node-0", limit=2, batch=2)
        self.assertTrue(node.allow())            # 窗口 1000：领 2 用 1
        clock.advance(1.0)
        self.assertTrue(node.allow())            # 跨窗口：归还旧的 1 个，新窗口再领
        self.assertEqual(store.held("default", 1000.0), 1)
        self.assertEqual(store.held("default", 1001.0), 2)


class TestCrashReclaim(unittest.TestCase):
    def test_dead_instance_quota_reclaimed_after_ttl(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(clock=clock)
        dead = make_limiter(store, clock, "dead", limit=4, window=100.0,
                            batch=4, lease_ttl=5.0)
        live = make_limiter(store, clock, "live", limit=4, window=100.0,
                            batch=4, lease_ttl=5.0)
        self.assertTrue(dead.allow())            # dead 领走全部 4 个后挂掉（不 close）
        self.assertFalse(live.allow())           # 租约没到期，别人拿不到
        clock.advance(5.0)                       # 租约到期，存储侧回收
        self.assertTrue(live.allow())
        self.assertFalse(dead.allow())           # dead 若复活，旧租约已作废也领不到


class TestClockSkewAlignment(unittest.TestCase):
    def test_skewed_instances_align_to_store_window(self):
        base = FakeClock(1000.2)
        store = InMemoryLeaseStore(clock=base)
        ahead = make_limiter(store, SkewedClock(base, +1.0), "ahead",
                             limit=4, batch=4, lease_ttl=50.0)
        behind = make_limiter(store, SkewedClock(base, -1.0), "behind",
                              limit=4, batch=4, lease_ttl=50.0)
        self.assertTrue(ahead.allow())           # 本地时钟快 1s，仍落在存储窗口 1000
        self.assertFalse(behind.allow())         # 慢 1s 的也是同一个窗口，额度共享
        base.advance(1.0)                        # 存储时钟跨过窗口边界
        self.assertTrue(behind.allow())          # 新窗口对齐放开
        self.assertFalse(ahead.allow())          # ahead 也按存储时钟切窗口，不多放


class TestStoreFailurePolicy(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.store = FlakyStore(InMemoryLeaseStore(clock=self.clock))
        self.node = make_limiter(self.store, self.clock, "node-0",
                                 limit=2, batch=1,
                                 key_policies={"vip": "open"})

    def test_fail_closed_by_default(self):
        self.store.healthy = False
        self.assertFalse(self.node.allow())

    def test_fail_open_per_key(self):
        self.store.healthy = False
        self.assertTrue(self.node.allow("vip"))  # vip 配了 open，放行
        self.assertFalse(self.node.allow())      # 默认 closed，拒绝

    def test_recovers_when_store_back(self):
        self.store.healthy = False
        self.assertFalse(self.node.allow())
        self.store.healthy = True
        self.assertTrue(self.node.allow())
        self.assertTrue(self.node.allow())
        self.assertFalse(self.node.allow())      # 恢复后正常计数


class TestArgs(unittest.TestCase):
    def test_rejects_invalid_args(self):
        store = InMemoryLeaseStore(clock=FakeClock())
        with self.assertRaises(ValueError):
            SharedLimiter(limit=0, store=store)
        with self.assertRaises(ValueError):
            SharedLimiter(limit=1, window=0, store=store)
        with self.assertRaises(ValueError):
            SharedLimiter(limit=1, store=None)
        with self.assertRaises(ValueError):
            SharedLimiter(limit=1, store=store, batch=0)
        with self.assertRaises(ValueError):
            SharedLimiter(limit=1, store=store, lease_ttl=0)
        with self.assertRaises(ValueError):
            SharedLimiter(limit=1, store=store, failure_policy="maybe")


if __name__ == "__main__":
    unittest.main()
