"""SharedWindowLimiter 行为：多实例共享一份配额。"""
import unittest

from quota import (
    FAIL_CLOSED,
    FAIL_OPEN,
    InMemoryLeaseStore,
    SharedWindowLimiter,
    StoreError,
)


class FakeClock:
    """手动推进的假时钟，避免测试真实 sleep。"""

    def __init__(self, now=1000.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class CountingStore(InMemoryLeaseStore):
    """记录 acquire 调用次数，验证本地预领省掉了远程往返。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.acquire_calls = 0

    def acquire(self, *args, **kwargs):
        self.acquire_calls += 1
        return super().acquire(*args, **kwargs)


class FlakyStore(InMemoryLeaseStore):
    """可开关故障的存储，down 期间一切操作抛 StoreError。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.down = False

    def acquire(self, *args, **kwargs):
        if self.down:
            raise StoreError("存储不可用")
        return super().acquire(*args, **kwargs)

    def release(self, *args, **kwargs):
        if self.down:
            raise StoreError("存储不可用")
        return super().release(*args, **kwargs)


def make_node(store, node_id, clock, limit=6, window=10.0, batch=1,
              lease_ttl=30.0, **kwargs):
    return SharedWindowLimiter(limit=limit, window=window, store=store,
                               node_id=node_id, batch=batch,
                               lease_ttl=lease_ttl, clock=clock, **kwargs)


class TestSharedQuota(unittest.TestCase):
    def test_instances_share_one_quota(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(window=10.0, clock=clock)
        nodes = [make_node(store, "n%d" % i, clock) for i in range(6)]
        results = [node.allow() for _ in range(4) for node in nodes]
        self.assertEqual(results.count(True), 6)
        self.assertEqual(results.count(False), 18)

    def test_keys_are_isolated_across_instances(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(window=10.0, clock=clock)
        a = make_node(store, "a", clock, limit=1)
        b = make_node(store, "b", clock, limit=1)
        self.assertTrue(a.allow("k1"))
        self.assertTrue(b.allow("k2"))
        self.assertFalse(b.allow("k1"))


class TestBatching(unittest.TestCase):
    def test_local_batch_skips_store_roundtrip(self):
        clock = FakeClock()
        store = CountingStore(window=10.0, clock=clock)
        node = make_node(store, "a", clock, limit=100, batch=4)
        for _ in range(4):
            self.assertTrue(node.allow())
        self.assertEqual(store.acquire_calls, 1)
        self.assertTrue(node.allow())  # 批用完，再领一批
        self.assertEqual(store.acquire_calls, 2)

    def test_unused_batch_returned_to_pool(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(window=10.0, clock=clock)
        a = make_node(store, "a", clock, limit=10, batch=6)
        b = make_node(store, "b", clock, limit=10, batch=10)
        self.assertTrue(a.allow())  # a 领走 6 个，只用 1 个
        self.assertEqual(a.remaining(), 9)  # 本地 5 + 存储侧未批出 4
        self.assertTrue(b.allow())  # b 只能领到剩下的 4 个
        self.assertEqual(b.remaining(), 3)
        a.release_unused()  # 归还 5 个
        self.assertEqual(b.remaining(), 8)

    def test_close_returns_all_keys(self):
        clock = FakeClock()
        store = InMemoryLeaseStore(window=10.0, clock=clock)
        a = make_node(store, "a", clock, limit=10, batch=5)
        b = make_node(store, "b", clock, limit=10, batch=5)
        a.allow("k1")
        a.allow("k2")
        a.close()  # 每个 key 各还回 4 个未用的，已消费的 1 个留在账上
        self.assertEqual(b.remaining("k1"), 9)
        self.assertEqual(b.remaining("k2"), 9)


class TestLeaseReclaim(unittest.TestCase):
    def test_dead_node_quota_reclaimed_after_ttl(self):
        store_clock = FakeClock()
        store = InMemoryLeaseStore(window=100.0, clock=store_clock)
        a = make_node(store, "a", FakeClock(), limit=5, batch=5, lease_ttl=10.0)
        b = make_node(store, "b", FakeClock(), limit=5, batch=5, lease_ttl=10.0)
        for _ in range(5):
            self.assertTrue(a.allow())  # a 领走全部额度
        self.assertFalse(b.allow())
        # a 掉线（不再归还），租约到期后 b 申领时顺带回收
        store_clock.advance(10.0)
        self.assertTrue(b.allow())
        self.assertEqual(b.remaining(), 4)

    def test_live_node_lease_not_reclaimed(self):
        store_clock = FakeClock()
        store = InMemoryLeaseStore(window=100.0, clock=store_clock)
        a = make_node(store, "a", FakeClock(), limit=5, batch=5, lease_ttl=10.0)
        b = make_node(store, "b", FakeClock(), limit=5, batch=5, lease_ttl=10.0)
        a.allow()
        store_clock.advance(9.0)  # 租约还没到期
        self.assertFalse(b.allow())


class TestClockSkewAlignment(unittest.TestCase):
    def test_skewed_clocks_share_store_window(self):
        store_clock = FakeClock(1000.0)
        store = InMemoryLeaseStore(window=10.0, clock=store_clock)
        clock_a = FakeClock(1000.0)
        clock_b = FakeClock(1002.0)  # 本地时钟快 2 秒
        a = make_node(store, "a", clock_a, limit=4, batch=2)
        b = make_node(store, "b", clock_b, limit=4, batch=2)

        granted = [a.allow(), a.allow(), b.allow(), b.allow()]
        self.assertEqual(granted, [True] * 4)
        self.assertFalse(a.allow())  # 本存储窗口已空，谁再来都拒
        self.assertFalse(b.allow())

        # b 的本地时钟先跨过自己算的边界，但存储窗口没滚动，不多放
        clock_b.advance(8.5)  # b 本地 1010.5，存储还在 1008.5
        self.assertFalse(b.allow())

        # 存储窗口滚动后，两个实例各自按本地换算时刻进入新窗口
        store_clock.advance(10.0)  # 存储 1010
        clock_a.advance(10.0)
        clock_b.advance(1.5)  # b 本地 1012
        granted = [a.allow(), a.allow(), b.allow(), b.allow()]
        self.assertEqual(granted, [True] * 4)
        self.assertFalse(a.allow())
        self.assertFalse(b.allow())


class TestStoreFailure(unittest.TestCase):
    def test_fail_closed_by_default(self):
        clock = FakeClock()
        store = FlakyStore(window=10.0, clock=clock)
        node = make_node(store, "a", clock, limit=5)
        store.down = True
        self.assertFalse(node.allow())

    def test_fail_open_per_key(self):
        clock = FakeClock()
        store = FlakyStore(window=10.0, clock=clock)
        node = make_node(store, "a", clock, limit=5, on_error=FAIL_CLOSED,
                         key_policies={"vip": FAIL_OPEN})
        store.down = True
        self.assertTrue(node.allow("vip"))
        self.assertFalse(node.allow("guest"))

    def test_local_batch_survives_store_flap(self):
        clock = FakeClock()
        store = FlakyStore(window=10.0, clock=clock)
        node = make_node(store, "a", clock, limit=5, batch=3)
        self.assertTrue(node.allow())  # 领 3 个
        store.down = True
        self.assertTrue(node.allow())  # 批内放行不碰存储
        self.assertTrue(node.allow())
        self.assertFalse(node.allow())  # 批用完才走降级口径

    def test_rejects_invalid_policy(self):
        with self.assertRaises(ValueError):
            make_node(InMemoryLeaseStore(window=1.0), "a", FakeClock(),
                      on_error="maybe")
        with self.assertRaises(ValueError):
            make_node(InMemoryLeaseStore(window=1.0), "a", FakeClock(),
                      key_policies={"vip": "maybe"})


if __name__ == "__main__":
    unittest.main()
