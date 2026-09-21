"""多分支合并：把从同一版本分叉的若干分支合回一条线。

每个分支是一个 ChangeLog，与基线共享 version <= base_version 的历史。
merge 把各分支在基线之后的变更按字段归拢：独占字段原样并入；
多分支撞车的字段交给消解函数挑一个赢家，输家记入 conflicts 账本。
"""

import time
from collections import namedtuple

from .changelog import DELETED, ChangeLog

# 一个分支对某字段的最终态度：分支名 + 该分支在这条字段上的最后一条变更。
Candidate = namedtuple("Candidate", ["origin", "change"])

# 合并进主线的一条变更：变更本体 + 来源分支名。
MergedChange = namedtuple("MergedChange", ["change", "origin"])

# 一次冲突的账本：哪个字段，谁赢了，谁被消解掉了。
Conflict = namedtuple("Conflict", ["field", "winner", "losers"])

# merge 的返回：合出的日志、逐条来源、冲突账本。
MergeResult = namedtuple("MergeResult", ["log", "changes", "conflicts"])


def last_write_wins(field, candidates):
    """默认策略：删除优先，否则版本号大者胜，平手取分支顺序靠后者。"""
    pool = [c for c in candidates if c.change.value is DELETED] or candidates
    return max(pool, key=lambda c: (c.change.version, candidates.index(c)))


def first_write_wins(field, candidates):
    """备选策略：版本号小者胜，平手取分支顺序靠前者（不特殊对待删除）。"""
    return min(candidates, key=lambda c: (c.change.version, candidates.index(c)))


def merge(obj, branches, base_version, into=None, resolver=None, clock=time.time):
    """把 branches 里各分支在 base_version 之后对 obj 的变更合回一条线。

    branches: {分支名: ChangeLog}（或 (名, 日志) 对的可迭代），
        其顺序即消解时平手的分支顺序。
    resolver: (field, candidates) -> Candidate，candidates 是各分支对该
        字段的最终 Candidate，须返回其中之一；缺省用 last_write_wins。
    into: 合并结果写入的 ChangeLog；缺省时用 clock 新建一个，并先把
        第一个分支里 version <= base_version 的基线变更抄进去。
    返回 MergeResult(log, changes, conflicts)。
    """
    items = list(branches.items() if hasattr(branches, "items") else branches)
    resolve = resolver or last_write_wins

    if into is None:
        into = ChangeLog(clock=clock)
        if items:
            for change in items[0][1].history(obj):
                if change.version <= base_version:
                    into.append(obj, change.field, change.value, change.version)

    # 按字段归拢各分支在基线之后的变更，保持分支顺序与各自 append 顺序。
    fields = {}  # field -> {origin: [Change, ...]}
    for origin, log in items:
        for change in log.history(obj):
            if change.version > base_version:
                fields.setdefault(change.field, {}).setdefault(origin, []).append(change)

    merged = []
    conflicts = []
    for field, per_origin in fields.items():
        entries = list(per_origin.items())
        if len(entries) == 1:
            origin, changes = entries[0]
            ordered = [(origin, change) for change in changes]
        else:
            candidates = [Candidate(origin, changes[-1]) for origin, changes in entries]
            first_value = candidates[0].change.value
            if all(c.change.value == first_value for c in candidates[1:]):
                # 各分支殊途同归，不算冲突
                ordered = [(o, c) for o, cs in entries for c in cs]
            else:
                winner = resolve(field, candidates)
                if winner not in candidates:
                    raise ValueError(
                        f"resolver 必须返回 candidates 之一，字段 {field!r} 拿到 {winner!r}"
                    )
                winner = candidates[candidates.index(winner)]
                losers = [c for c in candidates if c != winner]
                conflicts.append(Conflict(field, winner, losers))
                # 输家先进历史，赢家压在该字段最后，保证 at 重建出赢家的值
                ordered = [
                    (o, c) for o, cs in entries for c in cs if c is not winner.change
                ]
                ordered.append((winner.origin, winner.change))
        for origin, change in ordered:
            appended = into.append(obj, field, change.value, change.version)
            merged.append(MergedChange(appended, origin))
    return MergeResult(into, merged, conflicts)
