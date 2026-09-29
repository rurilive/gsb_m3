"""ledgerbook 的现状实现：一张按发生次序排好的收支流水。

Ledger 只记两件事，一笔收入记正，一笔支出记负，余额是全部流水之和。金额一律
是整数分，全程没有浮点参与；还没有科目、分录、借贷平衡与期间的概念，也没有
结账、对账与冲销。这些留待在这个基础上补齐。
"""

from .errors import InvalidAmount


class Flow:
    """一条流水：方向、金额（整数分）与备注。

    kind 取 in 或 out，amount 是正整数分，note 是可选的文字说明。
    """

    __slots__ = ("kind", "amount", "note")

    def __init__(self, kind, amount, note=""):
        self.kind = kind
        self.amount = amount
        self.note = note

    def signed_amount(self):
        """带符号的金额，收入为正、支出为负。"""
        return self.amount if self.kind == "in" else -self.amount

    def __repr__(self):
        return "Flow(kind=%r, amount=%r, note=%r)" % (
            self.kind,
            self.amount,
            self.note,
        )


def _check_amount(amount):
    """金额校验：只收正整数分，浮点与其它类型一律拒绝。"""
    if isinstance(amount, bool) or not isinstance(amount, int):
        raise InvalidAmount("金额必须是整数分，收到 %r" % (amount,))
    if amount <= 0:
        raise InvalidAmount("金额必须为正，收到 %r" % (amount,))
    return amount


class Ledger:
    """一张收支流水账。

    流水按提交次序保存，余额是全部流水带符号金额之和。本类不感知科目与期间。
    """

    def __init__(self):
        self._flows = []

    def record_in(self, amount, note=""):
        """记一笔收入，追加一条流向为 in 的流水，返回该条流水。"""
        _check_amount(amount)
        flow = Flow("in", amount, note)
        self._flows.append(flow)
        return flow

    def record_out(self, amount, note=""):
        """记一笔支出，追加一条流向为 out 的流水，返回该条流水。"""
        _check_amount(amount)
        flow = Flow("out", amount, note)
        self._flows.append(flow)
        return flow

    def flows(self):
        """按发生次序返回全部流水的浅拷贝。"""
        return list(self._flows)

    def total_in(self):
        """全部收入之和。"""
        return sum(f.amount for f in self._flows if f.kind == "in")

    def total_out(self):
        """全部支出之和。"""
        return sum(f.amount for f in self._flows if f.kind == "out")

    def balance(self):
        """余额，收入合计减支出合计。"""
        return self.total_in() - self.total_out()

    def reset(self):
        """清空全部流水。"""
        self._flows = []
