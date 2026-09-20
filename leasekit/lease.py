"""进程内租约管理器。

一条租约就是「某个持有者在一段时间内独占某个东西」的凭证：
发放时按 TTL 算好到期时刻，读取时用注入的 clock 判断还活着没有。
过期的条目在读取路径上视同不存在（get 返回 None），但不会被顺手
删掉——清理由主循环显式驱动 reap_expired 完成。

持有者可以在到期前 renew 把到期点往后延；renew 与回收共用同一把锁，
在同一次持锁内完成「看死没死 -> 改/删」，不存在刚续上就被回收的窗口。
长任务配一个 LeaseWatchdog，由外部主循环 tick 驱动，到点自动续，
续不上立刻回调通知持有者，全程不起真线程。

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
        """管理器使用的时钟，看护对象拿它判断何时该续。"""
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

    def renew(self, lease_id, holder, ttl=None):
        """持有者在到期前把租约往后延，成功返回 True。

        租约不存在、已到期，或来者不是当前持有者，一律返回 False
        且不改动租约（包括 ttl）。ttl 不传就沿用这条租约当前的租期；
        显式传 ttl 则以后续期都按新租期算。新的到期点 = 现在 + ttl，
        不是在旧到期点上累加。
        """
        if ttl is not None and ttl <= 0:
            raise ValueError("ttl must be > 0")
        with self._lock:
            record = self._leases.get(lease_id)
            if record is None or record.holder != holder:
                return False
            if self._clock() >= record.expires_at:
                return False
            next_ttl = record.ttl if ttl is None else ttl
            record.ttl = next_ttl
            record.expires_at = self._clock() + next_ttl
            return True

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

    def reap_expired(self):
        """清掉所有到期未续的租约，返回被回收的 lease_id 列表。

        由主循环周期性驱动，不自己起线程。回收只认当下的到期点：
        刚 renew 过的租约 expires_at 已在锁内推后，不会被误清。
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
            return expired

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


class LeaseWatchdog:
    """盯着一条租约、到点替持有者自动续期的看护对象。

    不起线程：由外部主循环周期性调用 tick(now=None) 驱动。每隔
    renew_interval 秒调一次 manager.renew；续期失败（租约已过期、
    被回收，或持有者已经不是自己）只通知一次，随后看护对象停摆。

    on_lost: 续期失败时的回调，签名 on_lost(lease_id, holder, reason)，
             reason 为 "gone"（租约没了/已过期）或 "wrong_holder"。
    ttl:     每次续期带上的租期；None 表示沿用租约当前租期。
    """

    def __init__(self, manager, lease_id, holder, renew_interval,
                 on_lost, ttl=None):
        if renew_interval <= 0:
            raise ValueError("renew_interval must be > 0")
        self._manager = manager
        self._lease_id = lease_id
        self._holder = holder
        self._interval = renew_interval
        self._on_lost = on_lost
        self._ttl = ttl
        self._next_renew_at = manager.clock() + renew_interval
        self._lost = False

    @property
    def lease_id(self):
        return self._lease_id

    @property
    def lost(self):
        """是否已经收到过续期失败通知；失活后 tick 不再动作。"""
        return self._lost

    def tick(self, now=None):
        """主循环驱动：到续期点就续一次。返回这次是否发起了续期。"""
        if self._lost:
            return False
        if now is None:
            now = self._manager.clock()
        if now < self._next_renew_at:
            return False
        self._next_renew_at = now + self._interval
        if self._manager.renew(self._lease_id, self._holder, self._ttl):
            return True
        self._lost = True
        lease = self._manager.get(self._lease_id)
        reason = "wrong_holder" if lease is not None else "gone"
        self._on_lost(self._lease_id, self._holder, reason)
        return False
