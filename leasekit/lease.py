"""进程内租约管理器。

一条租约就是「某个持有者在一段时间内独占某个东西」的凭证：
发放时按 TTL 算好到期时刻，读取时用注入的 clock 判断还活着没有。
过期的条目在读取路径上视同不存在（get 返回 None），但不会被顺手
删掉——清理由谁负责、什么时候做，是另一码事。

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

    def stats(self):
        """计数快照，返回独立 dict，调用方随便改。"""
        with self._lock:
            now = self._clock()
            live = sum(1 for r in self._leases.values() if now < r.expires_at)
            return {
                "granted": self._granted,
                "released": self._released,
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
