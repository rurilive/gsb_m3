"""预领批量站点：名额先划到站点手里再放，花完一批才再划。

朴素 Site 每放一个名额跑一趟账本，高峰把账本打垮、断链全误杀。BufferSite
一次 grant 划一批进本地，几十个线程并发扣本地库存，不丢不重；批里花完才
再跑账本。批大小按消耗快慢自调：盯着上一批花掉用了多久，往目标补给周期
window 上靠，夹在 min_batch 与 max_batch 之间，平稳期平均每 8 个名额最多
一趟账本往返。

红线不变：名额一律先划后放，任何时刻累计放行不越总配额。专线断了就花手
里这批，花完如实拒并报 link_down；线一恢复，下一次动账前先把账对上（用
了多少、剩多少一并 report 报回，序号幂等，专线重发不双算），对完再领新
批。收工 close 把囤的一次退干净，账本两边对得上。纯标准库，clock 注入是
为了测消耗快慢，测试可换假时钟。
"""

import math
import threading
import time

from slotledger.ledger import LinkDown

MIN_BATCH = 8
MAX_BATCH = 4096
WINDOW = 0.05


class BufferSite:
    """一个机房里的放名额端，围着一份 Ledger 批量预领。

    name 是站点名，与账本里的站点一一对应；多个线程可以共用同一个
    BufferSite 并发放名额。min_batch、max_batch、window 控制批大小自调
    的下限、上限与目标补给周期（秒）。
    """

    def __init__(self, ledger, name, min_batch=MIN_BATCH, max_batch=MAX_BATCH,
                 window=WINDOW, clock=time.monotonic):
        if min_batch < 1:
            raise ValueError("min_batch must be >= 1")
        if max_batch < min_batch:
            raise ValueError("max_batch must be >= min_batch")
        if window <= 0:
            raise ValueError("window must be > 0")
        self._ledger = ledger
        self.name = name
        self._min_batch = min_batch
        self._max_batch = max_batch
        self._window = window
        self._clock = clock
        self._lock = threading.Lock()
        self._in_hand = 0
        self._released = 0
        self._unreported = 0
        self._blocked = None
        self._dirty = False
        self._closed = False
        self._report_seq = 0
        self._batch = min_batch
        self._last_batch = 0
        self._batch_started = None

    def admit(self, n=1):
        """尽力放 n 个名额，返回实际放行的数量。

        手里有批就本地扣，扣完才跑账本领新批。专线断着就花手里这批，花
        完记 link_down 停住；池子干了记 exhausted。断链期间欠下的账，
        在线路恢复后、领新批之前先对清。一次全部放成时清掉上一次的停住
        原因。n 非正数时不动账也不放行，直接返回 0。
        """
        if n <= 0:
            return 0
        with self._lock:
            if self._closed:
                self._blocked = "closed"
                return 0
            if self._ledger.link_up(self.name):
                if self._dirty:
                    self._reconcile()
            else:
                self._dirty = True
            granted = 0
            while granted < n:
                if self._in_hand == 0:
                    if not self._refill():
                        break
                take = min(n - granted, self._in_hand)
                self._in_hand -= take
                self._unreported += take
                granted += take
            if granted == n:
                self._blocked = None
            self._released += granted
            return granted

    def close(self):
        """收工：用了多少、手里囤多少一并对账报回，返回退回的名额数。

        对完账该站在账本里的在外名额归零，两边对得上。专线断着时账报不
        出去，抛 LinkDown，恢复后可再调。已关的站点再 close 是空操作。
        """
        with self._lock:
            if self._closed:
                return 0
            returned = self._in_hand
            if not self._reconcile():
                raise LinkDown("link down: %s" % (self.name,))
            self._closed = True
            return returned

    def blocked_last(self):
        """上一次没放够的原因："exhausted"、"link_down"、"closed" 或 None。"""
        with self._lock:
            return self._blocked

    def released(self):
        """开张以来累计放行的名额。"""
        with self._lock:
            return self._released

    def in_hand(self):
        """手里囤着没放出去的名额。"""
        with self._lock:
            return self._in_hand

    def batch_size(self):
        """当前目标批大小，按消耗快慢自调，夹在上下限之间。"""
        with self._lock:
            return self._batch

    def _refill(self):
        if self._dirty and not self._reconcile():
            return False
        try:
            got = self._ledger.grant(self.name, self._batch)
        except LinkDown:
            self._dirty = True
            self._blocked = "link_down"
            return False
        if got <= 0:
            self._blocked = "exhausted"
            return False
        self._tune(got)
        self._in_hand = got
        return True

    def _reconcile(self):
        used = self._unreported
        returned = self._in_hand
        if used == 0 and returned == 0:
            self._dirty = False
            return True
        seq = self._report_seq + 1
        try:
            applied = self._ledger.report(self.name, seq, used, returned)
        except LinkDown:
            self._blocked = "link_down"
            return False
        if applied:
            self._report_seq = seq
        self._unreported = 0
        self._in_hand = 0
        self._dirty = False
        return True

    def _tune(self, got):
        now = self._clock()
        if self._batch_started is not None and self._last_batch > 0:
            elapsed = now - self._batch_started
            if elapsed <= 0:
                target = self._batch * 2
            else:
                target = math.ceil(self._last_batch * self._window / elapsed)
            self._batch = max(self._min_batch, min(self._max_batch, target))
        self._last_batch = got
        self._batch_started = now
