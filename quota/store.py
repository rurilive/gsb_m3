"""共享额度存储协议与进程内参考实现，纯标准库。

多个限流实例共享一份额度时，不逐个请求远程加一，而是向共享存储批量
预领一批额度存在本地花。存储侧保证每次预领原子，并记录每批额度挂在
哪个实例名下（租约）：

- 实例活着就定期续租，说明手里的额度还在花；
- 实例挂掉导致租约过期，存储把它没花完的额度自动收回，重新可被预领；
- 实例主动 shutdown 时可提前归还没花完的额度，不必等租约过期。

窗口由存储按自己的时钟切分。实例时钟不齐没关系：额度属于哪个窗口
存储说了算，实例只认存储返回的窗口边界。
"""
import threading
import time
from collections import namedtuple

Grant = namedtuple(
    "Grant",
    ["granted", "window_start", "window_end", "store_now", "lease_end"],
)
Heartbeat = namedtuple("Heartbeat", ["ok", "store_now", "lease_end"])


class SharedStore:
    """共享存储协议。生产环境用 Redis/数据库等实现同一接口即可。"""

    def acquire(self, key, limit, amount, instance_id, lease_ttl):
        """在 key 的当前窗口原子预领至多 amount 个额度并挂到实例租约上。

        返回 Grant：granted 为实际领到的数量（窗口余量不足时小于 amount，
        窗口耗尽时为 0），并带上存储认定的窗口边界、存储当前时间与租约
        到期时间。
        """
        raise NotImplementedError

    def renew(self, key, window_start, instance_id, lease_ttl, held):
        """续租：证明实例还活着，并上报它手里还没花完的额度 held。

        存储据此把已花掉的部分从预领计数里扣掉；这样租约将来若过期，
        只回收真正没花完的额度。租约已过期被回收，或 window_start 已不
        是存储当前窗口时 ok=False。
        """
        raise NotImplementedError

    def release(self, key, window_start, instance_id, amount):
        """主动归还 amount 个没花完的额度，返回实际归还数量。"""
        raise NotImplementedError


class MemoryStore(SharedStore):
    """进程内参考实现：一把锁保证所有操作原子，时钟可注入。

    测试里用它当假共享存储；它的 clock 就是“权威时钟”，各实例自己的
    时钟可以与它有偏差，用来模拟机器时间不齐。
    """

    def __init__(self, window, clock=time.monotonic):
        if window <= 0:
            raise ValueError("window 必须为正数")
        self.window = float(window)
        self._clock = clock
        self._lock = threading.Lock()
        self._windows = {}
        self.acquire_calls = 0
        self.renew_calls = 0
        self.release_calls = 0

    def _tick(self):
        """返回存储认定的当前窗口起点与当前时间，并清理过期窗口（持锁）。"""
        now = self._clock()
        start = now - (now % self.window)
        stale = [wk for wk in self._windows if wk[1] < start]
        for wk in stale:
            del self._windows[wk]
        return start, now

    def _state(self, key, start):
        state = self._windows.get((key, start))
        if state is None:
            state = {"taken": 0, "leases": {}}
            self._windows[(key, start)] = state
        return state

    @staticmethod
    def _reap(state, now):
        """回收租约已过期实例手里没花完的额度（持锁）。

        taken 是窗口累计已领（含已花掉的），只有真正没花完的 held 能
        从 taken 里退回；租约存活期间上报的已花部分不退。
        """
        dead = [iid for iid, (_held, end) in state["leases"].items()
                if now >= end]
        for iid in dead:
            held, _end = state["leases"].pop(iid)
            state["taken"] -= held

    def leased(self, key, at=None):
        """查看 key 在存储当前窗口累计已领额度（含已花，监控/测试用）。"""
        with self._lock:
            if at is None:
                start, _now = self._tick()
            else:
                start = at - (at % self.window)
            state = self._windows.get((key, start))
            return state["taken"] if state else 0

    def acquire(self, key, limit, amount, instance_id, lease_ttl):
        with self._lock:
            self.acquire_calls += 1
            start, now = self._tick()
            state = self._state(key, start)
            self._reap(state, now)
            available = max(0, int(limit) - state["taken"])
            granted = max(0, min(int(amount), available))
            if granted:
                state["taken"] += granted
                held, old_end = state["leases"].get(instance_id, (0, start))
                lease_end = max(old_end, now + lease_ttl)
                state["leases"][instance_id] = [held + granted, lease_end]
                return Grant(granted, start, start + self.window, now, lease_end)
            lease = state["leases"].get(instance_id)
            lease_end = lease[1] if lease else now + lease_ttl
            return Grant(0, start, start + self.window, now, lease_end)

    def renew(self, key, window_start, instance_id, lease_ttl, held):
        with self._lock:
            self.renew_calls += 1
            start, now = self._tick()
            if window_start != start:
                return Heartbeat(False, now, 0.0)
            state = self._windows.get((key, start))
            if state is not None:
                self._reap(state, now)
                lease = state["leases"].get(instance_id)
                if lease is not None:
                    lease[0] = max(0, min(int(held), lease[0]))
                    lease[1] = now + lease_ttl
                    return Heartbeat(True, now, lease[1])
            return Heartbeat(False, now, 0.0)

    def release(self, key, window_start, instance_id, amount):
        with self._lock:
            self.release_calls += 1
            start, now = self._tick()
            if window_start != start:
                return 0
            state = self._windows.get((key, start))
            if state is None:
                return 0
            self._reap(state, now)
            lease = state["leases"].get(instance_id)
            if lease is None:
                return 0
            returned = min(max(0, int(amount)), lease[0])
            lease[0] -= returned
            state["taken"] -= returned
            if lease[0] == 0:
                del state["leases"][instance_id]
            return returned
