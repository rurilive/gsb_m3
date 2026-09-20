"""进程内租约管理器。

一条租约就是「某个持有者在一段时间内独占某个东西」的凭证：
发放时按 TTL 算好到期时刻，读取时用注入的 clock 判断还活着没有。
过期的条目在读取路径上视同不存在（get 返回 None），由管理器主循环
驱动 reap_expired 统一回收。

持有者可以在到期前 renew 把租约往后延；LeaseWatcher 由外部主循环
按节拍驱动，盯着自己那条租约到点自动续，续不上立刻回调通知持有者。

纯标准库，不碰真实时间：所有时刻都来自构造时传入的 clock，
测试里给个假时钟就能精确断言到期边界。
"""

import threading
import time
import uuid
from dataclasses import dataclass


@dataclass(frozen=True)
class Lease:
    """一条租约的只读快照。

    id:         租约标识
    holder:     持有者标识（谁能续、谁能放）
    ttl:        发放时的租期，单位秒
    expires_at: 到期时刻，落在管理器时钟的时间轴上
    """

    id: str
    holder: str
    ttl: float
    expires_at: float


class _Record:
    """管理器内部的租约记录，外面拿不到。"""

    __slots__ = ("holder", "ttl", "expires_at")

    def __init__(self, holder, ttl, expires_at):
        self.holder = holder
        self.ttl = ttl
        self.expires_at = expires_at


class LeaseManager:
    """内存里的租约表。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    default_ttl: acquire 不传 ttl 时用的默认租期，单位秒。

    内部一把锁保护，单个方法调用对多线程安全。
    """

    def __init__(self, clock=time.monotonic, default_ttl=30.0):
        if default_ttl <= 0:
            raise ValueError("default_ttl must be > 0")
        self._clock = clock
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._leases = {}       # lease_id -> _Record
        self._granted = 0
        self._released = 0
        self._reaped = 0

    @property
    def clock(self):
        """管理器使用的时钟（只读），看护对象拿它安排自己的节拍。"""
        return self._clock

    def acquire(self, holder, ttl=None):
        """发放一条新租约，返回 lease_id。

        ttl 为空就用 default_ttl；同一个 holder 可以同时持有多条租约。
        """
        ttl = self._default_ttl if ttl is None else ttl
        if ttl <= 0:
            raise ValueError("ttl must be > 0")
        lease_id = uuid.uuid4().hex
        with self._lock:
            self._leases[lease_id] = _Record(holder, ttl, self._clock() + ttl)
            self._granted += 1
        return lease_id

    def get(self, lease_id):
        """查租约，返回快照；不存在或已到期都返回 None。"""
        with self._lock:
            return self._snapshot(lease_id)

    def release(self, lease_id, holder):
        """持有者主动归还租约，返回是否真的还上了。

        只有当前持有者能还，且租约得还活着；过期之后再还属于无效操作。
        """
        with self._lock:
            record = self._leases.get(lease_id)
            if record is None or record.holder != holder:
                return False
            if self._clock() >= record.expires_at:
                return False
            del self._leases[lease_id]
            self._released += 1
            return True

    def renew(self, lease_id, holder, ttl=None):
        """把租约的到期时刻往后延，成功返回 True。

        ttl 不传就沿用这条租约上次发放/续期时的租期；显式传了就以
        新的租期为准，同时更新租约快照里的 ttl。

        以下情况一律返回 False 且不改动租约：租约不存在或已过期、
        来者不是当前持有者。ttl 显式给了非正值抛 ValueError。
        """
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be > 0")
        with self._lock:
            record = self._leases.get(lease_id)
            if record is None or record.holder != holder:
                return False
            if self._clock() >= record.expires_at:
                return False
            if ttl is not None:
                record.ttl = ttl
            record.expires_at = self._clock() + record.ttl
            return True

    def reap_expired(self):
        """清掉所有到期未续的租约，返回本次回收的条数。

        和 renew 在同一把锁内各自原子完成，所以「刚续上就被清掉」
        的窗口不存在：要么先看到旧到期时刻被回收、续期随后落空，
        要么先看到续好的新到期时刻而活下来。
        """
        with self._lock:
            now = self._clock()
            expired = [
                lease_id
                for lease_id, record in self._leases.items()
                if now >= record.expires_at
            ]
            for lease_id in expired:
                del self._leases[lease_id]
            self._reaped += len(expired)
            return len(expired)

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            now = self._clock()
            live = sum(1 for r in self._leases.values() if now < r.expires_at)
            return {
                "granted": self._granted,
                "released": self._released,
                "reaped": self._reaped,
                "live": live,
            }

    def _snapshot(self, lease_id):
        """按 id 造一份快照，不存在或已到期返回 None。调用方必须持锁。"""
        record = self._leases.get(lease_id)
        if record is None:
            return None
        if self._clock() >= record.expires_at:
            return None
        return Lease(lease_id, record.holder, record.ttl, record.expires_at)


class LeaseWatcher:
    """盯着自己那条租约、到点自动续期的看护对象。

    由外部主循环按节拍调用 tick 驱动，不起线程、不碰真实时间：
    每过 interval 秒替 holder 向 manager 续一次租约；只要续期失败
    （租约已过期/被回收/持有者不再是自己），立刻调用 on_lost
    通知持有者，之后不再动作。interval 应明显小于租约的 ttl。
    """

    def __init__(self, manager, lease_id, holder, interval, on_lost, ttl=None):
        if interval <= 0:
            raise ValueError("interval must be > 0")
        lease = manager.get(lease_id)
        if lease is None or lease.holder != holder:
            raise ValueError("watcher requires a live lease held by holder")
        self._manager = manager
        self._lease_id = lease_id
        self._holder = holder
        self._interval = interval
        self._on_lost = on_lost
        self._ttl = ttl
        self._next_at = manager.clock() + interval
        self._active = True

    @property
    def active(self):
        """是否还在岗：尚未续期失败、未被 stop。"""
        return self._active

    def tick(self):
        """主循环每拍调用一次；到点就续期，失败立刻通知持有者。"""
        if not self._active:
            return
        now = self._manager.clock()
        if now < self._next_at:
            return
        while now >= self._next_at:
            self._next_at += self._interval
        if not self._manager.renew(self._lease_id, self._holder, self._ttl):
            self._active = False
            self._on_lost(self._lease_id, self._holder)
            return

    def stop(self):
        """主动撤下看护（任务正常结束），不触发丢失通知。"""
        self._active = False
