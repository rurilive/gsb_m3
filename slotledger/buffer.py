"""预领批量站点：一次划一批到本地，断链也能花手里这批。

朴素站点每放一个名额跑一趟账本，高峰账本先垮，断链全在挨拒；先放后同步
的老路子又超放过。本模块的红线是任何时刻累计放行不越总配额：名额先从账
本划到站点手里（grant 原子记账，池子不会被双机房划穿），本地几十个线程
在缓冲上并发扣，一批花完才再跑一趟账本；批量大小按消耗速度自适应，平稳
期平均每放 8 个名额最多一趟账本往返。

专线断开时站点先花手里这批，花完如实拒并报 "link_down"；链路恢复后，下
一次放行前先对账（用了多少、手里剩多少一并报回），对账上报经 Reconciler
按请求号去重，专线重发两遍只记一次。收工 close() 把囤着的名额一次退干净。
纯标准库，clock 可注入，测试用假时钟，不真 sleep。
"""

import threading

from slotledger.ledger import LinkDown

DEFAULT_BATCH = 8
MIN_BATCH = 8
MAX_BATCH = 1024


class ReconcileMismatch(RuntimeError):
    """站点上报的用量与账本 outstanding 对不上。"""


class UsageReport:
    """一笔用量上报：站点累计放了多少、手里还剩多少。"""

    def __init__(self, site, req_id, used, remaining):
        self.site = site
        self.req_id = req_id
        self.used = used
        self.remaining = remaining

    def __eq__(self, other):
        if not isinstance(other, UsageReport):
            return NotImplemented
        return (self.site == other.site and self.req_id == other.req_id
                and self.used == other.used and self.remaining == other.remaining)

    def __repr__(self):
        return ("UsageReport(site=%r, req_id=%d, used=%d, remaining=%d)"
                % (self.site, self.req_id, self.used, self.remaining))


class ReconcileAck:
    """对账回执。duplicate=True 表示这是重发的请求号，没重复记账。"""

    def __init__(self, report, matched, duplicate):
        self.report = report
        self.matched = matched
        self.duplicate = duplicate


class Reconciler:
    """账本侧的用量对账入口，按 (站点, 请求号) 去重，扛专线重发。

    submit 与 grant/retire 走同一条专线：链路断开抛 LinkDown，账目不动。
    同一个 req_id 重发，返回首条回执且不再记录，报两遍不算两次。账本口径
    守恒：used + remaining 必须等于该站在账本里的 outstanding。
    """

    def __init__(self, ledger):
        self._ledger = ledger
        self._lock = threading.Lock()
        self._last_req = {}
        self._reports = {}

    def submit(self, report):
        if not isinstance(report, UsageReport):
            raise TypeError("report must be a UsageReport")
        if not isinstance(report.used, int) or report.used < 0:
            raise ValueError("used must be a non-negative int")
        if not isinstance(report.remaining, int) or report.remaining < 0:
            raise ValueError("remaining must be a non-negative int")
        if not self._ledger.link_up(report.site):
            raise LinkDown("link down: %s" % (report.site,))
        with self._lock:
            last = self._last_req.get(report.site)
            if last is not None and report.req_id < last:
                raise ValueError("req_id must not go backwards")
            if last == report.req_id:
                first = self._reports[(report.site, report.req_id)]
                return ReconcileAck(first, matched=True, duplicate=True)
            outstanding = self._ledger.outstanding(report.site)
            matched = report.used + report.remaining == outstanding
            self._last_req[report.site] = report.req_id
            self._reports[(report.site, report.req_id)] = report
            return ReconcileAck(report, matched, duplicate=False)

    def reports(self, site=None):
        """已确认的对账上报（不含重发），按提交顺序排列。"""
        with self._lock:
            items = [report for (name, _), report in self._reports.items()
                     if site is None or name == site]
            return tuple(items)

    def last_report(self, site):
        """该站最后一条被确认的上报，从没报过返回 None。"""
        with self._lock:
            req_id = self._last_req.get(site)
            if req_id is None:
                return None
            return self._reports[(site, req_id)]


class BufferedSite:
    """预领批量站点：一批名额本地放，花完再划，接口与朴素 Site 对齐。

    admit(n) 尽力放 n 个，返回实际放行数量；blocked_last() 报停住原因
    ("exhausted" / "link_down")；released()、in_hand() 查累计放行与囤货。
    grant_trips() 是开张以来跑账本划批的次数，量同步开销用。批量按上一批
    的消耗速度自适应（一批花完用时 t 个，则瞄准每批够用 t 个时间单位），
    下限 8 保证平稳期平均每放 8 个名额最多一趟账本往返。
    """

    def __init__(self, ledger, name, batch=DEFAULT_BATCH,
                 min_batch=MIN_BATCH, max_batch=MAX_BATCH,
                 reconciler=None, clock=None):
        if batch <= 0:
            raise ValueError("batch must be positive")
        if min_batch < 1 or max_batch < min_batch:
            raise ValueError("bad batch bounds")
        self._ledger = ledger
        self.name = name
        self._batch = max(min_batch, min(batch, max_batch))
        self._min_batch = min_batch
        self._max_batch = max_batch
        self._reconciler = reconciler
        self._clock = clock
        self._lock = threading.Lock()
        self._in_hand = 0
        self._released = 0
        self._blocked = None
        self._closed = False
        self._grant_trips = 0
        self._seq = 0
        self._pending = None
        self._last_match = None
        self._batch_start = None
        self._batch_got = 0

    def admit(self, n=1):
        """尽力放 n 个名额，本地缓冲先扣，扣完再跑账本划一批。

        池子干了记 exhausted；专线断且手里花完记 link_down，断链期间凭
        手里这批续放。链路恢复后先对账再放行。一次全放成时清掉停住原因。
        n 非正数不动账也不放行，直接返回 0。
        """
        if n <= 0:
            return 0
        with self._lock:
            if self._closed:
                raise RuntimeError("site is closed")
            if not self._ledger.link_up(self.name):
                self._arm_locked()
            elif self._pending is not None:
                try:
                    self._send_report_locked()
                except LinkDown:
                    self._blocked = "link_down"
                    return 0
            granted = 0
            while granted < n:
                if self._in_hand > 0:
                    take = min(n - granted, self._in_hand)
                    self._in_hand -= take
                    granted += take
                    self._released += take
                    if self._in_hand == 0:
                        self._adapt_locked()
                    continue
                if not self._ledger.link_up(self.name):
                    self._arm_locked()
                    self._blocked = "link_down"
                    break
                got = self._refill_locked()
                if got == 0:
                    if self._blocked != "link_down":
                        self._blocked = "exhausted"
                    break
            if granted == n:
                self._blocked = None
            return granted

    def blocked_last(self):
        """上一次没放够的原因："exhausted"、"link_down" 或 None。"""
        with self._lock:
            return self._blocked

    def released(self):
        """开张以来累计放行的名额。"""
        with self._lock:
            return self._released

    def in_hand(self):
        """手里囤着还没放出去的名额。"""
        with self._lock:
            return self._in_hand

    def grant_trips(self):
        """开张以来跑账本划批的次数，每批最多一趟。"""
        with self._lock:
            return self._grant_trips

    def last_reconcile_matched(self):
        """最近一次对账是否对平，没报过返回 None。"""
        with self._lock:
            return self._last_match

    def reconcile(self):
        """显式对账：把用量与囤货上报账本，返回 UsageReport。

        专线断开或没挂 Reconciler 时抛 LinkDown / RuntimeError；重发同一个
        请求号在账本侧只记一次。
        """
        with self._lock:
            return self._send_report_locked()

    def close(self):
        """收工：把手里囤的名额一次退干净并报最后一次账，返回退回数量。

        专线断开抛 LinkDown，囤货原样留在手里，链路恢复后可重试。
        """
        with self._lock:
            if self._closed:
                return 0
            if not self._ledger.link_up(self.name):
                raise LinkDown("link down: %s" % (self.name,))
            back = 0
            if self._in_hand > 0:
                back = self._ledger.retire(self.name, self._in_hand)
                self._in_hand -= back
            self._soft_report_locked()
            if self._in_hand == 0:
                self._closed = True
            return back

    def _refill_locked(self):
        try:
            got = self._ledger.grant(self.name, self._batch)
        except LinkDown:
            self._blocked = "link_down"
            return 0
        self._grant_trips += 1
        self._in_hand += got
        self._pending = None
        if got > 0:
            self._batch_got = got
            self._batch_start = self._now_locked()
        return got

    def _adapt_locked(self):
        """上一批花完，按消耗速度调下一批：瞄准每批够用一个时间单位。"""
        if self._clock is None:
            return
        end = self._clock()
        start = self._batch_start
        spent = self._batch_got or self._batch
        if start is not None:
            elapsed = end - start
            if elapsed > 0:
                spent = int(spent / elapsed)
        self._batch = max(self._min_batch, min(spent, self._max_batch))

    def _arm_locked(self):
        """观察到断链，挂起一笔账：链路恢复后先对这笔再放行。"""
        if self._reconciler is not None and self._pending is None:
            self._seq += 1
            self._pending = self._seq

    def _soft_report_locked(self):
        """收工用的对账：尽力报，专线再抖不影响已退账的事实。"""
        if self._reconciler is None:
            return
        if self._pending is None:
            self._seq += 1
            self._pending = self._seq
        try:
            self._send_report_locked()
        except LinkDown:
            pass

    def _send_report_locked(self):
        if self._reconciler is None:
            raise RuntimeError("no reconciler attached")
        if self._pending is None:
            self._seq += 1
        report = UsageReport(self.name, self._seq, self._released, self._in_hand)
        ack = self._reconciler.submit(report)
        self._pending = None
        self._last_match = ack.matched
        return report

    def _now_locked(self):
        if self._clock is None:
            return None
        return self._clock()
