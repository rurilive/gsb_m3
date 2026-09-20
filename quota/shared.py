"""多实例共享额度的固定窗口限流器，纯标准库。

六个实例挂同一个共享存储（见 quota.store.SharedStore），合起来严格
守住上游给的总量：

- 本地预领：不逐请求远程加一，而是一次从存储原子领一批额度放本地
  慢慢花，花完再领；批量按使用情况自适应（领满一批就翻倍，手里
  剩额度却换窗口/归还就减半），尽量在“烂在手里”和“频繁往返”间贴合；
- 归还与回收：shutdown 时主动归还没花完的额度；实例挂掉来不及还，
  存储等租约 TTL 过期后自动把额度收回，下一批预领就能领到；
- 窗口对齐：窗口边界由存储按它自己的时钟切，实例时钟差两秒也不
  影响——实例用存储回包校掉本地时钟偏差，额度跨不了窗口花；
- 降级口径：存储抖动导致新一批领不出来时，按 key 配 fail_open
  （放行，保可用性）或 fail_closed（拒绝，保配额）。手里已领的
  额度照花，抖动不影响它们。
"""
import threading
import time
import uuid

FAIL_OPEN = "fail_open"
FAIL_CLOSED = "fail_closed"
_POLICIES = (FAIL_OPEN, FAIL_CLOSED)


class SharedFixedWindowLimiter:
    """多实例共享一份配额的固定窗口限流器。"""

    def __init__(
        self,
        store,
        limit,
        window=None,
        batch_size=10,
        lease_ttl=10.0,
        heartbeat_at=None,
        fail_policy=FAIL_CLOSED,
        instance_id=None,
        clock=time.monotonic,
    ):
        if limit <= 0:
            raise ValueError("limit 必须为正数")
        if batch_size <= 0:
            raise ValueError("batch_size 必须为正数")
        if lease_ttl <= 0:
            raise ValueError("lease_ttl 必须为正数")
        self.store = store
        self.limit = int(limit)
        self.window = float(window) if window is not None else store.window
        self.batch_size = min(int(batch_size), self.limit)
        self.lease_ttl = float(lease_ttl)
        self.heartbeat_at = (
            float(heartbeat_at) if heartbeat_at is not None
            else self.lease_ttl / 2.0
        )
        self.fail_policy = fail_policy
        self.instance_id = instance_id or uuid.uuid4().hex
        self._clock = clock
        self._lock = threading.Lock()
        self._offset = 0.0
        self._pools = {}
        self._batch = {}

    def allow(self, key="default"):
        """有本地额度则放行；本地空了才向共享存储预领下一批。"""
        with self._lock:
            now = self._clock()
            pool = self._pools.get(key)
            if pool is not None:
                if self._past_window(key, pool, now):
                    self._drop(key, pool)
                    pool = None
                elif self._renew_due(pool, now):
                    pool = self._heartbeat(key, pool, now)
            if pool is not None and pool["held"] > 0:
                pool["held"] -= 1
                return True
            return self._fetch(key, now)

    def shutdown(self, key=None):
        """主动归还没花完的额度。key 为 None 时归还这个实例所有 key。"""
        with self._lock:
            keys = list(self._pools) if key is None else [key]
            for each in keys:
                pool = self._pools.pop(each, None)
                if pool is None or pool["held"] <= 0:
                    continue
                returned = self.store.release(
                    each, pool["window_start"], self.instance_id, pool["held"]
                )
                if returned:
                    self._shrink(each)

    def _past_window(self, key, pool, now):
        """按校准过的本地时钟判断存储窗口是否已滚动。"""
        del key
        return now + self._offset >= pool["window_end"]

    def _renew_due(self, pool, now):
        """租约剩余时间不够一个续租间隔，续租保命。"""
        if self.heartbeat_at <= 0:
            return False
        return now + self._offset >= pool["lease_end"] - self.heartbeat_at

    def _heartbeat(self, key, pool, now):
        """向存储续租并上报剩余持有量。异常只当瞬时抖动，已领的照花。"""
        try:
            beat = self.store.renew(
                key, pool["window_start"], self.instance_id,
                self.lease_ttl, pool["held"],
            )
        except Exception:
            return pool
        self._offset = beat.store_now - now
        if not beat.ok:
            self._drop(key, pool)
            return None
        pool["lease_end"] = beat.lease_end
        return pool

    def _fetch(self, key, now):
        """本地空了：向共享存储预领下一批；存储抖动按降级口径处置。"""
        want = self._want(key)
        try:
            grant = self.store.acquire(
                key, self.limit, want, self.instance_id, self.lease_ttl
            )
        except Exception:
            return self._policy(key) == FAIL_OPEN
        self._offset = grant.store_now - now
        if grant.granted == 0:
            self._shrink(key)
            self._pools.pop(key, None)
            return False
        if grant.granted >= want:
            self._grow(key)
        self._pools[key] = {
            "held": grant.granted - 1,
            "window_start": grant.window_start,
            "window_end": grant.window_end,
            "lease_end": grant.lease_end,
        }
        return True

    def _want(self, key):
        want = self._batch.get(key)
        if want is None:
            want = self.batch_size
            self._batch[key] = want
        return want

    def _grow(self, key):
        self._batch[key] = min(self.limit, self._want(key) * 2)

    def _shrink(self, key):
        self._batch[key] = max(1, self._want(key) // 2)

    def _drop(self, key, pool):
        """丢弃本地这批额度；换窗口时手里还剩说明批量估大了，调小。"""
        self._pools.pop(key, None)
        if pool["held"] > 0:
            self._shrink(key)

    def _policy(self, key):
        policy = self.fail_policy
        if callable(policy):
            policy = policy(key)
        elif isinstance(policy, dict):
            policy = policy.get(key, FAIL_CLOSED)
        if policy not in _POLICIES:
            raise ValueError("未知降级口径: %r" % (policy,))
        return policy
