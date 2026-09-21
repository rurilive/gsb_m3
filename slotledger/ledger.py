"""中心名额账本：两个机房共用的名额总池、流水与专线状态。

放号系统每天只有一个总配额，两个机房各挂一个站点从总池领名额。账本记三件
事：还剩多少、各站点手里划走了多少、每笔动账的流水。站点与账本之间隔一条
专线，专线状态由 set_link 控制，断开时动账一律抛 LinkDown。纯标准库，
clock 注入是为了给流水打时刻，测试可换成假时钟。
"""

import threading
import time
from dataclasses import dataclass


class LinkDown(RuntimeError):
    """站点与账本之间的专线断开，动账请求被拒。"""


@dataclass(frozen=True)
class Entry:
    """账本流水的一笔动账。seq 全局递增，不重复不回退。"""

    seq: int
    kind: str
    site: str
    amount: int
    at: float


class Ledger:
    """名额总池。grant 划出、retire 归还，任何时刻账目守恒：

    remaining() + outstanding() == total，一个名额不多不少。
    """

    def __init__(self, total, clock=time.monotonic):
        if total < 0:
            raise ValueError("total must be >= 0")
        self._total = total
        self._remaining = total
        self._clock = clock
        self._lock = threading.Lock()
        self._outstanding = {}
        self._links = {}
        self._seq = 0
        self._history = []

    def set_link(self, site, up):
        """设置站点与账本之间的专线状态，断开后该站动账即抛 LinkDown。"""
        with self._lock:
            self._links[site] = bool(up)

    def link_up(self, site):
        """查站点专线当前是否连通，没设置过的站点视为连通。"""
        with self._lock:
            return self._links.get(site, True)

    def grant(self, site, amount):
        """给 site 划 amount 个名额，受剩余量约束，返回实际划到的数量。

        池子不够就少给，池子干了返回 0；amount 必须是正整数。专线断开抛
        LinkDown，此时账目分文不动。
        """
        if not isinstance(amount, int):
            raise TypeError("amount must be an int")
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            if not self._links.get(site, True):
                raise LinkDown("link down: %s" % (site,))
            got = min(amount, self._remaining)
            if got > 0:
                self._remaining -= got
                self._outstanding[site] = self._outstanding.get(site, 0) + got
                self._record("grant", site, got)
            return got

    def retire(self, site, amount):
        """site 把没用完的 amount 个名额退回池子，返回实际退回的数量。

        超过该站手里份额的部分自动截住，账目不会被退穿。amount 必须是正
        整数，专线断开抛 LinkDown。
        """
        if not isinstance(amount, int):
            raise TypeError("amount must be an int")
        if amount <= 0:
            raise ValueError("amount must be positive")
        with self._lock:
            if not self._links.get(site, True):
                raise LinkDown("link down: %s" % (site,))
            have = self._outstanding.get(site, 0)
            got = min(amount, have)
            if got > 0:
                self._outstanding[site] = have - got
                self._remaining += got
                self._record("retire", site, got)
            return got

    def total(self):
        """总配额，账本开张起不变。"""
        return self._total

    def remaining(self):
        """池子里还没划出去的名额。"""
        with self._lock:
            return self._remaining

    def outstanding(self, site=None):
        """划出去还没退回的名额。site 给 None 时是所有站点之和。"""
        with self._lock:
            if site is None:
                return sum(self._outstanding.values())
            return self._outstanding.get(site, 0)

    def history(self):
        """全部动账流水，按 seq 递增排列。"""
        with self._lock:
            return tuple(self._history)

    def _record(self, kind, site, amount):
        self._seq += 1
        self._history.append(Entry(self._seq, kind, site, amount, self._clock()))
