"""多实例共享配额的固定窗口限流，纯标准库。

设计要点：

- 额度记账在共享存储一侧：每个 (key, 窗口) 记录已批出的总额度和各
  实例持有的租约，申领是原子的，六台实例合起来不会突破 limit。
- 实例每次向存储预领 batch 个额度，批内放行不走存储；批用完或窗口
  滚动时再申领。batch 是可调的折中：大了会有额度烂在手里（靠归还和
  租约回收兜底），小了退化成每请求一次远程往返。
- 未用完的额度可主动归还（release_unused / close / 窗口滚动时自动
  归还）；实例掉线时，其租约到期，由其他实例申领时顺带回收。
- 窗口边界以存储时钟为准。申领响应携带存储当前时刻，实例据此把窗口
  结束时刻换算到本地时钟上，本地时钟差几秒不会各划各的边界。
- 存储故障时按 key 降级：FAIL_OPEN 放行、FAIL_CLOSED 拒绝，可逐 key
  配置。手里还有本地批时不访问存储，不受抖动影响。
"""
import os
import socket
import threading
import time

from .limiter import DEFAULT_KEY

FAIL_OPEN = "allow"
FAIL_CLOSED = "deny"


class StoreError(Exception):
    """共享存储不可用。"""


class InMemoryLeaseStore:
    """进程内租约存储，供演示与测试；生产换成同接口的远程实现。

    窗口边界由本存储的时钟划定，所有实例对齐到同一份窗口。接口：

    - acquire(key, amount, limit, node_id, lease_ttl)
      原子申领：先回收到期租约，再从剩余额度里批出至多 amount 个。
      返回 (window_start, granted, remaining, now)，now 是存储时钟读数。
    - release(key, window_start, node_id, amount)
      归还本窗口未用额度；窗口已滚动则丢弃。
    """

    def __init__(self, window, clock=time.monotonic):
        if window <= 0:
            raise ValueError("window 必须为正数")
        self.window = float(window)
        self._clock = clock
        self._lock = threading.Lock()
        # key -> [window_start, granted, {node_id: [held, expiry]}]
        self._state = {}

    def acquire(self, key, amount, limit, node_id, lease_ttl):
        with self._lock:
            now = self._clock()
            start = now - (now % self.window)
            state = self._state.get(key)
            if state is None or state[0] != start:
                state = [start, 0, {}]
                self._state[key] = state
            leases = state[2]
            for node, lease in list(leases.items()):
                held, expiry = lease
                if expiry <= now:
                    state[1] -= held
                    del leases[node]
            granted = max(0, min(amount, limit - state[1]))
            if granted:
                state[1] += granted
                held, _expiry = leases.get(node_id, (0, 0.0))
                leases[node_id] = (held + granted, now + lease_ttl)
            return start, granted, max(0, limit - state[1]), now

    def release(self, key, window_start, node_id, amount):
        if amount <= 0:
            return
        with self._lock:
            state = self._state.get(key)
            if state is None or state[0] != window_start:
                return
            lease = state[2].get(node_id)
            if lease is None:
                return
            held, expiry = lease
            back = min(amount, held)
            state[1] -= back
            if held - back:
                state[2][node_id] = (held - back, expiry)
            else:
                del state[2][node_id]


class SharedWindowLimiter:
    """多实例共享一份配额的固定窗口限流器。"""

    def __init__(self, limit, window=1.0, store=None, node_id=None,
                 batch=1, lease_ttl=30.0, clock=time.monotonic,
                 on_error=FAIL_CLOSED, key_policies=None):
        if limit <= 0:
            raise ValueError("limit 必须为正数")
        if window <= 0:
            raise ValueError("window 必须为正数")
        if batch <= 0:
            raise ValueError("batch 必须为正数")
        if lease_ttl <= 0:
            raise ValueError("lease_ttl 必须为正数")
        if on_error not in (FAIL_OPEN, FAIL_CLOSED):
            raise ValueError("on_error 只能是 FAIL_OPEN 或 FAIL_CLOSED")
        self.limit = int(limit)
        self.window = float(window)
        self.store = store if store is not None else InMemoryLeaseStore(window, clock=clock)
        self.node_id = node_id or "%s:%d" % (socket.gethostname(), os.getpid())
        self.batch = int(batch)
        self.lease_ttl = float(lease_ttl)
        self._clock = clock
        self.on_error = on_error
        self._key_policies = dict(key_policies or {})
        for policy in self._key_policies.values():
            if policy not in (FAIL_OPEN, FAIL_CLOSED):
                raise ValueError("key_policies 的值只能是 FAIL_OPEN 或 FAIL_CLOSED")
        self._lock = threading.Lock()
        # key -> [window_start, held, store_remaining, local_expiry]
        self._local = {}

    def allow(self, key=DEFAULT_KEY):
        """共享额度内还有余量则放行，否则拒绝；存储故障按 key 口径降级。"""
        with self._lock:
            entry = self._local.get(key)
            if entry is not None and self._clock() >= entry[3]:
                self._release_locked(key, entry)
                entry = None
            if entry is None or entry[1] == 0:
                try:
                    start, granted, remaining, now = self.store.acquire(
                        key, self.batch, self.limit, self.node_id, self.lease_ttl)
                except StoreError:
                    return self._policy(key) == FAIL_OPEN
                # 存储窗口结束时刻换算到本地时钟，吸收实例间时钟差。
                local_expiry = start + self.window - (now - self._clock())
                entry = [start, granted, remaining, local_expiry]
                self._local[key] = entry
            if entry[1] == 0:
                return False
            entry[1] -= 1
            return True

    def remaining(self, key=DEFAULT_KEY):
        """当前窗口的剩余额度：本地持有 + 存储侧未批出。"""
        with self._lock:
            entry = self._local.get(key)
            held = entry[1] if entry is not None else 0
            try:
                _start, _granted, remaining, _now = self.store.acquire(
                    key, 0, self.limit, self.node_id, self.lease_ttl)
            except StoreError:
                return held
            return held + remaining

    def release_unused(self, key=DEFAULT_KEY):
        """把本 key 本地未用完的额度归还存储。"""
        with self._lock:
            entry = self._local.pop(key, None)
            if entry is not None:
                self._release_locked(key, entry)

    def close(self):
        """归还所有 key 的本地余额，实例下线前调用。"""
        with self._lock:
            for key, entry in self._local.items():
                self._release_locked(key, entry)
            self._local.clear()

    def _release_locked(self, key, entry):
        try:
            self.store.release(key, entry[0], self.node_id, entry[1])
        except StoreError:
            pass  # 还不回去的额度随租约到期被回收

    def _policy(self, key):
        return self._key_policies.get(key, self.on_error)
