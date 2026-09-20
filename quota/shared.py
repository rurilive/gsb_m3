"""多实例共享一份限额的固定窗口限流，纯标准库。

计数放在共享存储（InMemoryStore 或同接口的远程实现），各实例按批
预领、本地消化、用不完归还；实例崩溃时其租约到期由存储回收。窗口
边界以存储侧时钟为准，实例本地时钟只决定何时回存储对账，因此各
实例时钟不齐不会把窗口划岔。存储故障时按 key 配置的口径降级
（fail-open 放行 / fail-closed 拒绝）。
"""
import threading
import time
import uuid

from .limiter import DEFAULT_KEY

OPEN = "open"
CLOSED = "closed"


class InMemoryStore:
    """进程内共享存储参考实现，语义对标可原子读改写的外部存储。

    真实部署可换成 Redis 等共享存储（同样的 now/claim/release/usage
    接口，用 Lua 保证原子性）；这里用锁模拟原子性，并注入时钟，
    供测试与 demo 使用。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._used = {}    # (key, window_start) -> 已发出的额度总数
        self._leases = {}  # (key, window_start, owner) -> [未归还量, 过期时刻]

    def now(self):
        """存储侧权威时钟：窗口对齐、租约过期都以它为准。"""
        return self._clock()

    def claim(self, key, window, limit, owner, amount, ttl):
        """原子认领：先回收过期租约，再从剩余额度里发，返回实发数。"""
        with self._lock:
            self._sweep(key, window)
            slot = (key, window)
            used = self._used.get(slot, 0)
            grant = max(0, min(int(amount), limit - used))
            if grant:
                lease_key = (key, window, owner)
                held, _expires = self._leases.get(lease_key, (0, 0.0))
                self._leases[lease_key] = [held + grant, self._clock() + ttl]
                self._used[slot] = used + grant
            return grant

    def release(self, key, window, owner, amount):
        """归还未用额度，返回实际回收数（不超过持有者剩余量）。"""
        with self._lock:
            lease_key = (key, window, owner)
            lease = self._leases.get(lease_key)
            if lease is None:
                return 0
            back = min(int(amount), lease[0])
            lease[0] -= back
            self._used[(key, window)] -= back
            if lease[0] == 0:
                del self._leases[lease_key]
            return back

    def usage(self, key, window):
        """当前窗口已发出的额度（含各实例手里未花的）。"""
        with self._lock:
            self._sweep(key, window)
            return self._used.get((key, window), 0)

    def _sweep(self, key, window):
        """回收该窗口下已过期租约的未归还额度（调用方持锁）。"""
        now = self._clock()
        expired = [k for k, v in self._leases.items()
                   if k[0] == key and k[1] == window and v[1] <= now]
        for lease_key in expired:
            held, _expires = self._leases.pop(lease_key)
            self._used[(key, window)] -= held


class SharedLimiter:
    """多实例共享限额的固定窗口限流器。

    本地额度花完才向存储认领一批（batch），跨窗口或 close() 时归还
    剩余；本地超过 lease_ttl 未对账的批次不再使用，交由存储回收，
    避免崩溃实例的额度被整窗空占、也避免同一批被重复计算。
    """

    def __init__(self, store, limit, window=1.0, batch=1, owner=None,
                 lease_ttl=None, clock=time.monotonic,
                 on_error=CLOSED, key_on_error=None):
        if limit <= 0:
            raise ValueError("limit 必须为正数")
        if window <= 0:
            raise ValueError("window 必须为正数")
        if batch <= 0:
            raise ValueError("batch 必须为正数")
        if on_error not in (OPEN, CLOSED):
            raise ValueError("on_error 只能是 'open' 或 'closed'")
        overrides = dict(key_on_error or {})
        for policy in overrides.values():
            if policy not in (OPEN, CLOSED):
                raise ValueError("key_on_error 的值只能是 'open' 或 'closed'")
        self.store = store
        self.limit = int(limit)
        self.window = float(window)
        self.batch = int(batch)
        self.owner = owner or "node-%s" % uuid.uuid4().hex[:8]
        self.lease_ttl = (float(lease_ttl) if lease_ttl is not None
                          else self.window * 2)
        self._clock = clock
        self._on_error = on_error
        self._key_on_error = overrides
        self._lock = threading.Lock()
        self._local = {}  # key -> [window_start, 本地剩余, 本地截止时刻]

    def allow(self, key=DEFAULT_KEY):
        """全局额度还有剩则放行；存储故障按 key 配置的口径降级。"""
        with self._lock:
            return self._allow(key)

    def remaining(self, key=DEFAULT_KEY):
        """全局剩余额度的估计：存储侧未发出的 + 本实例手里没花的。"""
        with self._lock:
            local = self._local_remaining(key)
            try:
                used = self.store.usage(key, self._store_window())
            except Exception:
                return local
            return local + max(0, self.limit - used)

    def close(self):
        """归还所有本地未花额度；存储故障时残留部分等租约到期回收。"""
        with self._lock:
            pending = [(key, state[0], state[1])
                       for key, state in self._local.items() if state[1] > 0]
            self._local.clear()
        for key, start, left in pending:
            try:
                self.store.release(key, start, self.owner, left)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()

    def _allow(self, key):
        now = self._clock()
        state = self._local.get(key)
        if (state is not None and state[1] > 0
                and now < state[0] + self.window and now < state[2]):
            state[1] -= 1
            return True
        try:
            start = self._store_window()
            if state is not None and state[0] != start and state[1] > 0:
                self.store.release(key, state[0], self.owner, state[1])
            granted = self.store.claim(key, start, self.limit, self.owner,
                                       self.batch, self.lease_ttl)
        except Exception:
            return self._degrade(key)
        self._local[key] = [start, max(0, granted - 1), now + self.lease_ttl]
        return granted > 0

    def _local_remaining(self, key):
        state = self._local.get(key)
        now = self._clock()
        if (state is not None and state[1] > 0
                and now < state[0] + self.window and now < state[2]):
            return state[1]
        return 0

    def _store_window(self):
        now = self.store.now()
        return now - (now % self.window)

    def _degrade(self, key):
        return self._key_on_error.get(key, self._on_error) == OPEN
