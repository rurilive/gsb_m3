"""多分支合并：把从同一版本分叉的几条变更线合回一条。

branches 给出各分支分叉后的变更（分支名 -> ChangeLog），merge 把双方
全部变更收进一条新日志：同字段同值直接并，同字段不同值按策略消解，
删除（DELETED）默认优先。结果里每条变更都带来源标注，冲突另记一笔账，
被消解掉的输家仍留在合并日志里，history 可见。
"""

import time
from collections import namedtuple

from .changelog import ChangeLog, DELETED

# 一条带来源标注的合并变更：change 是合并日志里的记录，source 是分支名。
Candidate = namedtuple("Candidate", ["change", "source"])

# 一次同字段冲突：胜出的变更与被消解掉的输家（都是 Candidate）。
Conflict = namedtuple("Conflict", ["field", "winner", "losers"])


def _latest(field, candidates):
    """默认策略：删除优先，否则版本高者胜，并列取分支名大者。"""
    for cand in candidates:
        if cand.change.value is DELETED:
            return cand
    return max(candidates, key=lambda c: (c.change.version, c.source))


def _first(field, candidates):
    """先写优先：删除优先，否则版本低者胜，并列取分支名小者。"""
    for cand in candidates:
        if cand.change.value is DELETED:
            return cand
    return min(candidates, key=lambda c: (c.change.version, c.source))


STRATEGIES = {"latest": _latest, "first": _first}


class MergeResult:
    """一次合并的产出：合并日志、带来源的条目、冲突账。"""

    def __init__(self, obj, log, entries, conflicts):
        self.obj = obj
        self.log = log  # ChangeLog，含双方全部变更（含输家）
        self.entries = entries  # [Candidate]，与 log 内记录一一对应、同序
        self.conflicts = conflicts  # [Conflict]

    def history(self):
        """合并后的全部变更，按合并日志顺序。"""
        return self.log.history(self.obj)

    def at(self, version):
        """合并后的快照：非冲突字段各归各，冲突字段取赢家。"""
        return self.log.at(self.obj, version)

    def source_of(self, change):
        """合并日志里某条记录来自哪条分支。"""
        for cand in self.entries:
            if cand.change is change:
                return cand.source
        raise ValueError("not a merged change: %r" % (change,))


def merge(obj, branches, strategy="latest", clock=time.time):
    """把 branches（分支名 -> ChangeLog）里 obj 的变更合成一条线。

    每条分支日志只含该分支分叉后的变更。strategy 为 "latest"（默认）/
    "first"，或自定义消解函数 resolver(field, candidates) -> candidate，
    candidates 是 Candidate 列表，须返回其中之一。返回 MergeResult。
    """
    if isinstance(strategy, str):
        if strategy not in STRATEGIES:
            raise ValueError("unknown strategy: %r" % strategy)
        resolver = STRATEGIES[strategy]
    else:
        resolver = strategy

    # 按分支名排序收变更，结果与 dict 迭代顺序无关。
    per_field = {}  # field -> [Candidate]，候选指向分支里的原始记录
    order = {}  # id(change) -> (version, source, 分支内序号)
    seq = 0
    for source in sorted(branches):
        for change in branches[source].history(obj):
            per_field.setdefault(change.field, []).append(Candidate(change, source))
            order[id(change)] = (change.version, source, seq)
            seq += 1

    # 逐字段消解：值有分歧才算冲突；赢家排到该字段最后，at 叠出来的才是它。
    resolved = {}  # field -> (winner, losers)，候选均指向原始记录
    for field, candidates in per_field.items():
        values = [cand.change.value for cand in candidates]
        if any(value != values[0] for value in values[1:]):
            winner = resolver(field, candidates)
            losers = [
                cand
                for cand in candidates
                if cand is not winner and cand.change.value != winner.change.value
            ]
            resolved[field] = (winner, losers)

    flat = [cand for candidates in per_field.values() for cand in candidates]
    flat.sort(key=lambda cand: order[id(cand.change)])
    for field, (winner, _losers) in resolved.items():
        flat.remove(winner)
        last = max(i for i, cand in enumerate(flat) if cand.change.field == field)
        flat.insert(last + 1, winner)

    # 写入合并日志：版本保留分支原值，ts 取自注入时钟。
    log = ChangeLog(clock=clock)
    entries = []
    for cand in flat:
        change = log.append(obj, cand.change.field, cand.change.value, cand.change.version)
        entries.append(Candidate(change, cand.source))

    merged_by_origin = {id(origin): cand for origin, cand in zip(flat, entries)}
    conflicts = [
        Conflict(
            field,
            merged_by_origin[id(winner)],
            [merged_by_origin[id(loser)] for loser in losers],
        )
        for field, (winner, losers) in resolved.items()
    ]
    return MergeResult(obj, log, entries, conflicts)
