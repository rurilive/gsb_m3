"""SharedFixedWindowLimiter 新行为：六实例共享一份配额。

全程用假时钟（手动推进，不真 sleep）和进程内假共享存储。
"""
import threading
import unittest

from quota import (
    FAIL_CLOSED,
    FAIL_OPEN,
    MemoryStore,
    SharedFixedWindowLimiter,
)


class FakeClock:
    """手动推进的假时钟。存储时钟与实例时钟各用一个，模拟机器时差。"""

    def __init__(self, now=0.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FlakyStore(MemoryStore):
    """可开关抛异常的假存储，模拟共享存储抖动。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.down = False

    def _check(self):
        if self.down:
            raise RuntimeError("共享存储抖动")

    def acquire(self, *args, **kwargs):
        self._check()
        return super().acquire(*args, **kwargs)

    def renew(self, *args, **kwargs):
        self._check()
        return super().renew(*args, **kwargs)


def make(instance_id, store, clock, **kwargs):
    """构造一个限流器实例。heartbeat_at=0 表示不提前续租，只有掉线
    回收类测试才关心续租。"""
    kwargs.setdefault("batch_size", 1)
    kwargs.setdefault("lease_ttl", 10.0)
    kwargs.setdefault("heartbeat_at", 0.0)
    kwargs.setdefault("window", 10.0)
    return SharedFixedWindowLimiter(
        store,
        limit=kwargs.pop("limit", 6),
        window=kwargs.pop("window"),
        instance_id=instance_id,
        clock=clock,
        **kwargs,
    )


class TestSharedQuota(unittest.TestCase):
    def test_six_instances_share_one_pool(self):
        """多实例共享额度：六台合起来恰好放到 limit，一台多花挤占别人。"""
        store_clock = FakeClock(1000.0)
        store = MemoryStore(window=10.0, clock=store_clock)
        clocks = [FakeClock(1000.0) for _ in range(6)]
        lims = [make("i%d" % i, store, clocks[i]) for i in range(6)]

        granted = []
        for _ in range(2):
            for lim in lims:
                granted.append(lim.allow("k"))

        self.assertEqual(sum(granted), 6)
        self.assertEqual(
            [lim.allow("k") for lim in lims], [False] * 6
        )
        self.assertEqual(store.leased("k"), 6)

        store_clock.advance(10.0)
        for c in clocks:
            c.advance(10.0)
        self.assertEqual(sum(lim.allow("k") for lim in lims), 6)

    def test_keys_are_isolated(self):
        store = MemoryStore(window=10.0, clock=FakeClock(1000.0))
        lim = make("i", store, FakeClock(1000.0), limit=1)
        self.assertTrue(lim.allow("a"))
        self.assertTrue(lim.allow("b"))
        self.assertFalse(lim.allow("a"))

    def test_concurrent_acquire_is_atomic(self):
        """六实例的预领请求并发打向存储，原子计数保证总放行不超 limit。"""
        store = MemoryStore(window=60.0, clock=FakeClock(1000.0))
        granted = []
        lock = threading.Lock()

        def worker(i):
            for _ in range(20):
                grant = store.acquire("k", 60, 1, "i%d" % i, 60.0)
                with lock:
                    granted.append(grant.granted)

        threads = [threading.Thread(target=worker, args=(i,))
                   for i in range(6)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(sum(granted), 60)
        self.assertEqual(store.leased("k"), 60)


class TestLocalPrefetchAndReturn(unittest.TestCase):
    def test_batch_is_spent_locally_with_one_remote_trip(self):
        """预领一批后本地慢慢花，远程调用不随请求数增长。"""
        store = MemoryStore(window=10.0, clock=FakeClock(1000.0))
        lim = make("i", store, FakeClock(1000.0), batch_size=4, limit=10)

        results = [lim.allow("k") for _ in range(4)]
        self.assertEqual(results, [True] * 4)
        self.assertEqual(store.acquire_calls, 1)
        self.assertEqual(store.leased("k"), 4)

        self.assertTrue(lim.allow("k"))
        self.assertEqual(store.acquire_calls, 2)

    def test_batch_grows_after_full_consumption(self):
        """整批花完才领下一批 → 批量翻倍，贴合实际用量。"""
        store = MemoryStore(window=10.0, clock=FakeClock(1000.0))
        lim = make("i", store, FakeClock(1000.0), batch_size=1, limit=10)
        self.assertTrue(lim.allow("k"))
        self.assertTrue(lim.allow("k"))
        self.assertEqual(store.acquire_calls, 2)
        self.assertEqual(store.leased("k"), 3)
        for _ in range(2):
            self.assertTrue(lim.allow("k"))
        self.assertEqual(store.acquire_calls, 3)
        self.assertEqual(store.leased("k"), 7)

    def test_shutdown_returns_unspent_quota(self):
        """主动归还：没花完的额度立刻回到共享池，别人马上能领。"""
        store = MemoryStore(window=10.0, clock=FakeClock(1000.0))
        clock = FakeClock(1000.0)
        lim = make("leaving", store, clock, batch_size=4, limit=4)
        self.assertTrue(lim.allow("k"))
        self.assertEqual(store.leased("k"), 4)

        other = make("other", store, clock, limit=4)
        self.assertFalse(other.allow("k"))

        lim.shutdown("k")
        self.assertEqual(store.release_calls, 1)
        self.assertEqual(store.leased("k"), 1)
        self.assertTrue(other.allow("k"))


class TestDeadInstanceReclaim(unittest.TestCase):
    def test_dead_instance_quota_reclaimed_after_lease_ttl(self):
        """实例掉线没还：租约 TTL 一到，存储收回剩余额度供他人预领。"""
        store_clock = FakeClock(1000.0)
        store = MemoryStore(window=100.0, clock=store_clock)
        inst_clock = FakeClock(1000.0)
        dead = make("dead", store, inst_clock, limit=4, window=100.0,
                    batch_size=4)
        self.assertTrue(dead.allow("k"))
        self.assertEqual(store.leased("k"), 4)

        survivor = make("alive", store, FakeClock(1000.0),
                        limit=4, window=100.0)
        self.assertFalse(survivor.allow("k"))

        store_clock.advance(9.9)
        self.assertFalse(survivor.allow("k"))
        store_clock.advance(0.1)
        self.assertTrue(survivor.allow("k"))
        for _ in range(3):
            self.assertTrue(survivor.allow("k"))
        self.assertEqual(store.leased("k"), 4)
        self.assertFalse(survivor.allow("k"))

    def test_reclaim_only_returns_unspent_part(self):
        """掉线实例已花掉的额度不退回，只回收它手里没花完的。"""
        store_clock = FakeClock(1000.0)
        store = MemoryStore(window=100.0, clock=store_clock)
        inst_clock = FakeClock(1000.0)
        dead = make("dead", store, inst_clock, limit=6, window=100.0,
                    batch_size=4, heartbeat_at=4.0, lease_ttl=5.0)
        self.assertTrue(dead.allow("k"))

        # 花掉 3 个、续一次租（上报还持有 0 个已花 4 个）。
        store_clock.advance(4.0)
        inst_clock.advance(4.0)
        for _ in range(3):
            self.assertTrue(dead.allow("k"))
        self.assertEqual(store.leased("k"), 4)

        alive = make("alive", store, FakeClock(1004.0),
                     limit=6, window=100.0)
        self.assertTrue(alive.allow("k"))
        self.assertTrue(alive.allow("k"))
        self.assertFalse(alive.allow("k"))

        # 掉线实例租约过期：已花的 4 个不退回，窗口不会超放。
        store_clock.advance(1.0)
        self.assertFalse(alive.allow("k"))

    def test_heartbeat_keeps_quota_alive(self):
        """活着的实例按时续租，额度不会被误收；窗口总放行量不破限。"""
        store_clock = FakeClock(1000.0)
        store = MemoryStore(window=100.0, clock=store_clock)
        inst_clock = FakeClock(1000.0)
        lim = make("a", store, inst_clock, limit=6, window=100.0,
                   batch_size=4, heartbeat_at=4.0, lease_ttl=5.0)
        self.assertTrue(lim.allow("k"))

        store_clock.advance(4.0)
        inst_clock.advance(4.0)
        self.assertTrue(lim.allow("k"))
        self.assertEqual(store.renew_calls, 1)

        store_clock.advance(4.0)
        inst_clock.advance(4.0)
        self.assertTrue(lim.allow("k"))
        self.assertTrue(lim.allow("k"))
        self.assertEqual(store.renew_calls, 2)

        other = make("b", store, FakeClock(1008.0), limit=6, window=100.0)
        self.assertTrue(other.allow("k"))
        self.assertTrue(other.allow("k"))
        self.assertFalse(other.allow("k"))
        self.assertEqual(store.leased("k"), 6)


class TestClockSkewWindowAlignment(unittest.TestCase):
    def test_skewed_instances_align_to_store_window(self):
        """实例时钟各差两秒，窗口仍按存储切，不多放跨边界那一批。"""
        store_clock = FakeClock(8.0)
        store = MemoryStore(window=10.0, clock=store_clock)
        ahead = make("ahead", store, FakeClock(10.0), limit=2, batch_size=1)
        behind = make("behind", store, FakeClock(6.0), limit=2, batch_size=1)

        self.assertTrue(ahead.allow("k"))
        self.assertTrue(behind.allow("k"))
        self.assertFalse(ahead.allow("k"))

        # 时钟快的实例本地已到 10.0（它以为新窗口），但存储还在旧窗口。
        ahead._clock.advance(2.0)
        self.assertEqual(ahead._clock(), 12.0)
        self.assertFalse(ahead.allow("k"))

        # 存储时钟跨过真正的边界 10.0，新窗口额度才放出来。
        store_clock.advance(2.0)
        self.assertTrue(ahead.allow("k"))
        self.assertTrue(behind.allow("k"))
        self.assertFalse(behind.allow("k"))

    def test_leftover_quota_cannot_be_spent_next_window(self):
        """旧窗口没花完的本地额度跨窗口作废，不占用新窗口配额。"""
        store_clock = FakeClock(9.0)
        store = MemoryStore(window=10.0, clock=store_clock)
        inst_clock = FakeClock(9.0)
        lim = make("i", store, inst_clock, limit=5, batch_size=3)
        self.assertTrue(lim.allow("k"))
        self.assertTrue(lim.allow("k"))

        store_clock.advance(1.0)
        inst_clock.advance(1.0)
        # 手里剩 1 个旧窗口额度：跨边界作废，新窗口仍可完整放 limit 个。
        results = [lim.allow("k") for _ in range(6)]
        self.assertEqual(results, [True, True, True, True, True, False])


class TestStorageFailurePolicy(unittest.TestCase):
    def test_fail_closed_rejects_when_storage_down(self):
        store = FlakyStore(window=10.0, clock=FakeClock(1000.0))
        lim = make("i", store, FakeClock(1000.0),
                   fail_policy=FAIL_CLOSED)
        store.down = True
        self.assertFalse(lim.allow("k"))

    def test_fail_open_allows_when_storage_down(self):
        store = FlakyStore(window=10.0, clock=FakeClock(1000.0))
        lim = make("i", store, FakeClock(1000.0),
                   fail_policy=FAIL_OPEN)
        store.down = True
        self.assertTrue(lim.allow("k"))
        self.assertTrue(lim.allow("k"))

        store.down = False
        self.assertTrue(lim.allow("k"))

    def test_held_quota_still_spent_during_outage(self):
        """抖动期间已领到手的额度照花，抖动只影响新一批预领。"""
        store = FlakyStore(window=10.0, clock=FakeClock(1000.0))
        lim = make("i", store, FakeClock(1000.0), batch_size=3, limit=5,
                   fail_policy=FAIL_CLOSED)
        for _ in range(2):
            self.assertTrue(lim.allow("k"))
        store.down = True
        self.assertTrue(lim.allow("k"))
        self.assertFalse(lim.allow("k"))

    def test_policy_per_key_dict(self):
        store = FlakyStore(window=10.0, clock=FakeClock(1000.0))
        lim = make("i", store, FakeClock(1000.0),
                   fail_policy={"open": FAIL_OPEN})
        store.down = True
        self.assertTrue(lim.allow("open"))
        self.assertFalse(lim.allow("closed"))

    def test_policy_per_key_callable(self):
        store = FlakyStore(window=10.0, clock=FakeClock(1000.0))
        lim = make(
            "i", store, FakeClock(1000.0),
            fail_policy=lambda key: FAIL_OPEN if key.startswith("o")
            else FAIL_CLOSED,
        )
        store.down = True
        self.assertTrue(lim.allow("open-key"))
        self.assertFalse(lim.allow("tight-key"))

    def test_renew_jitter_does_not_drop_held_quota(self):
        """续租撞上抖动不当作死实例，手里的额度继续花。"""
        store = FlakyStore(window=100.0, clock=FakeClock(1000.0))
        clock = FakeClock(1000.0)
        lim = make("i", store, clock, limit=6, window=100.0,
                   batch_size=3, heartbeat_at=4.0, lease_ttl=5.0)
        self.assertTrue(lim.allow("k"))
        clock.advance(4.0)
        store.down = True
        self.assertTrue(lim.allow("k"))
        self.assertTrue(lim.allow("k"))
        self.assertFalse(lim.allow("k"))


if __name__ == "__main__":
    unittest.main()
