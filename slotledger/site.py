"""朴素站点：每放一个名额就往账本跑一趟。

这是最老实的实现，账本说给一个才放一个，行为正确但开销大：每放一个名额
一次账本往返，高峰时账本自己先被打垮；专线一断，一个都放不出，全在误杀。
它是后续预领批量改造的正确性参照和行为基线。纯标准库。
"""

import threading

from slotledger.ledger import LinkDown


class Site:
    """一个机房里的放名额端，围着一份 Ledger 转圈。

    name 是站点名，与账本里的站点一一对应；多个线程可以共用同一个 Site
    并发放名额。
    """

    def __init__(self, ledger, name):
        self._ledger = ledger
        self.name = name
        self._lock = threading.Lock()
        self._released = 0
        self._blocked = None

    def admit(self, n=1):
        """尽力放 n 个名额，返回实际放行的数量。

        逐个向账本要，要不到就地停住：池子干了记 exhausted，专线断了记
        link_down。一次全部放成时清掉上一次的停住原因。n 非正数时不动账
        也不放行，直接返回 0。
        """
        if n <= 0:
            return 0
        granted = 0
        with self._lock:
            for _ in range(n):
                try:
                    got = self._ledger.grant(self.name, 1)
                except LinkDown:
                    self._blocked = "link_down"
                    break
                if got < 1:
                    self._blocked = "exhausted"
                    break
                granted += 1
            else:
                self._blocked = None
            self._released += granted
            return granted

    def blocked_last(self):
        """上一次没放够的原因："exhausted"、"link_down" 或没停住时的 None。"""
        with self._lock:
            return self._blocked

    def released(self):
        """开张以来累计放行的名额。"""
        with self._lock:
            return self._released

    def in_hand(self):
        """手里囤着没放出去的名额。朴素版每放一个都是现要的，永远是 0。"""
        with self._lock:
            return 0
