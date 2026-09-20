"""多实例共享配额的固定窗口限流器，纯标准库。

FixedWindowLimiter 只记本进程的账，多实例部署时总量随实例数放大。
SharedLimiter 把记账交给注入的共享存储（lease store）：各实例按批
预领额度、本地消化、用不完归还；实例掉线靠租约 TTL 回收额度。
窗口起点以存储时钟为准，实例间时钟差几秒不影响对齐。
"""
import threading
import time

DEFAULT_KEY = "default"
POLICY_OPEN = "open"
POLICY_CLOSED = "closed"


class InMemoryLeaseStore:
    """租约存储的内存参考实现，供单进程多实例与测试使用。

    真实部署应替换为 Redis 等外部存储（acquire 用 Lua 保证原子性），
    接口只有 now/acquire/release 三个方法，照此实现即可换。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._leases = {}  # (key, window_start) -> {owner: (amount, expiry)}

    def now(self):
        """存储侧时钟读数，是窗口对齐与租约过期的唯一基准。"""
        return self._clock()

    def acquire(self, key, window_start, owner, amount, limit, ttl):
        """原子预领：返回实际批到的额度，可能少于 amount。"""
        with self._lock:
            leases = self._active(key, window_start)
            used = sum(held for held, _exp in leases.values())
            grant = max(0, min(int(amount), int(limit) - used))
            if grant:
                prev, _exp = leases.get(owner, (0, 0.0))
                leases[owner] = (prev + grant, self._clock() + ttl)
            return grant

    def release(self, key, window_start, owner, amount):
        """归还额度；owner 没有租约或还超了都按实际持有的还。"""
        with self._lock:
            leases = self._leases.get((key, window_start))
            if not leases or owner not in leases:
                return
            held, expiry = leases[owner]
            left = max(0, held - int(amount))
            if left:
                leases[owner] = (left, expiry)
            else:
                del leases[owner]

    def held(self, key, window_start):
        """该窗口当前被预领走的总量（观测与测试用）。"""
        with self._lock:
            return sum(held for held, _exp in self._active(key, window_start).values())

    def _active(self, key, window_start):
        """取 (key, window) 下未过期的租约，顺手清掉过期的（调用方持锁）。"""
        now = self._clock()
        leases = {o: (a, e) for o, (a, e) in
                  self._leases.get((key, window_start), {}).items() if e > now}
        self._leases[(key, window_start)] = leases
        return leases


class SharedLimiter:
    """多实例共享一份配额的固定窗口限流器。

    每个窗口内向存储按 batch 预领一批额度，本地扣减，花完再领；
    窗口结束或 close() 时把没用完的还回去。租约带 lease_ttl，
    实例掉线后存储侧到期自动回收。存储故障时按 key 配置的口径
    降级：open 放行、closed 拒绝（默认 closed）。
    """

    def __init__(self, limit, window=1.0, store=None, clock=time.monotonic,
                 batch=None, lease_ttl=None, owner=None,
                 failure_policy=POLICY_CLOSED, key_policies=None):
        if limit <= 0:
            raise ValueError("limit 必须为正数")
        if window <= 0:
            raise ValueError("window 必须为正数")
        if store is None:
            raise ValueError("store 必须提供")
        if batch is None:
            batch = max(1, int(limit) // 10)
        if batch <= 0:
            raise ValueError("batch 必须为正数")
        if lease_ttl is None:
            lease_ttl = max(5.0, 2.0 * float(window))
        if lease_ttl <= 0:
            raise ValueError("lease_ttl 必须为正数")
        if failure_policy not in (POLICY_OPEN, POLICY_CLOSED):
            raise ValueError("failure_policy 只能是 open 或 closed")
        self.limit = int(limit)
        self.window = float(window)
        self.store = store
        self.batch = int(batch)
        self.lease_ttl = float(lease_ttl)
        self.owner = owner or "instance-%x" % id(self)
        self.failure_policy = failure_policy
        self.key_policies = dict(key_policies or {})
        self._clock = clock
        self._lock = threading.Lock()
        self._offset = 0.0  # 存储时钟 - 本地时钟，最近一次预领时测得
        self._local = {}    # key -> [window_start, batch_left, lease_expiry_local]

    def allow(self, key=DEFAULT_KEY):
        """共享额度还有剩则放行并计数，否则拒绝；存储故障按 key 的口径降级。"""
        with self._lock:
            now = self._clock()
            state = self._local.get(key)
            if state is not None:
                window_start, left, expiry = state
                rolled = self._window_start(now) != window_start
                expired = now >= expiry
                if rolled:
                    self._release_quiet(key, window_start, left)
                if rolled or expired:
                    # 跨窗口归还上一批；租约过期的剩余额度作废（存储侧已回收）
                    state = None
                elif left > 0:
                    state[1] = left - 1
                    return True
                else:
                    state = None
            if state is None:
                return self._acquire_and_take(key, now)
            return False

    def remaining(self, key=DEFAULT_KEY):
        """本实例手里还没用的预领额度（不含存储中未领的与其他实例持有的）。"""
        with self._lock:
            state = self._local.get(key)
            if state is None:
                return 0
            window_start, left, expiry = state
            now = self._clock()
            if self._window_start(now) != window_start or now >= expiry:
                return 0
            return left

    def close(self):
        """主动归还所有没用完的额度（优雅下线）；掉线场景靠租约 TTL 回收。"""
        with self._lock:
            for key, (window_start, left, _exp) in list(self._local.items()):
                self._release_quiet(key, window_start, left)
            self._local.clear()

    def _acquire_and_take(self, key, now):
        """向存储预领一批并立刻扣掉本次（调用方持锁）。"""
        try:
            store_now = self.store.now()
            self._offset = store_now - now
            window_start = self._align(store_now)
            grant = self.store.acquire(key, window_start, self.owner,
                                       self.batch, self.limit, self.lease_ttl)
        except Exception:
            return self._policy(key) == POLICY_OPEN
        if grant <= 0:
            self._local.pop(key, None)
            return False
        self._local[key] = [window_start, grant - 1, now + self.lease_ttl]
        return True

    def _window_start(self, local_now):
        """按存储时钟推算本地当前所处的窗口起点（调用方持锁）。"""
        return self._align(local_now + self._offset)

    def _align(self, store_now):
        return store_now - (store_now % self.window)

    def _release_quiet(self, key, window_start, amount):
        """尽力归还；失败不致命，租约到期后存储侧自行回收。"""
        if amount <= 0:
            return
        try:
            self.store.release(key, window_start, self.owner, amount)
        except Exception:
            pass

    def _policy(self, key):
        return self.key_policies.get(key, self.failure_policy)
