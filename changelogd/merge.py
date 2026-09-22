"""多分支合并：把从同一版本分叉的变更序列合回一条线。

merge 按字段汇总各分支的候选变更，同字段不同值交给消解策略
（默认 last_write_wins，可注入自定义函数），胜出的变更以递增
版本号 append 进目标 ChangeLog。返回的 MergeResult 记账：
每条合并结果来自哪条分支，每次冲突的赢家与输家。
"""

from collections import namedtuple

from .changelog import DELETED

# 一个分支对某字段的候选：分支名 + 该分支里这条字段的最后一条变更。
Option = namedtuple("Option", ["source", "change"])

# 一条合并结果：写进目标日志的变更 + 它来自哪条分支。
MergedEntry = namedtuple("MergedEntry", ["change", "source"])

# 一次冲突的账：哪个字段，谁赢（Option），谁输（Option 列表）。
Conflict = namedtuple("Conflict", ["field", "winner", "losers"])


def last_write_wins(field, options):
    """默认消解策略：删除标记优先；否则版本高者胜，并列取靠后的分支。

    field: 冲突的字段名。
    options: [Option, ...]，按 branches 给出的分支顺序排列。
    返回 options 中的一个。
    """
    tombstoned = [o for o in options if o.change.value is DELETED]
    if tombstoned:
        return tombstoned[-1]
    best = options[0]
    for option in options[1:]:
        if option.change.version >= best.change.version:
            best = option
    return best


class MergeResult:
    """一次合并的账本：合并结果（带来源）与冲突记录。"""

    def __init__(self, entries, conflicts):
        self.entries = entries  # [MergedEntry]，按写入目标日志的顺序
        self.conflicts = conflicts  # [Conflict]，按字段首次出现的顺序

    @property
    def losers(self):
        """所有冲突里被消解掉的输家（Option），按冲突顺序。"""
        return [loser for conflict in self.conflicts for loser in conflict.losers]

    def snapshot(self):
        """折叠合并结果：后写覆盖先写，DELETED 把字段移除。返回新 dict。"""
        snapshot = {}
        for entry in self.entries:
            if entry.change.value is DELETED:
                snapshot.pop(entry.change.field, None)
            else:
                snapshot[entry.change.field] = entry.change.value
        return snapshot


def merge(log, obj, branches, resolve=None, start_version=1):
    """把多条分支合进 log 里 obj 的时间线，返回 MergeResult。

    log: 目标 ChangeLog，胜出的变更按 start_version 起递增版本号 append 进去。
    branches: [(分支名, [Change, ...])]，每条分支通常取自另一条日志的 history。
    resolve: 消解函数 resolve(field, options) -> Option，默认 last_write_wins。
    同一字段各分支取值相同不算冲突，取首条分支的候选。
    """
    resolve = resolve or last_write_wins

    # 按字段汇总候选：分支内同字段取 append 顺序的最后一条。
    candidates = {}  # field -> [Option]
    fields = []  # 字段首次出现的顺序（先按分支序，再按分支内顺序）
    for source, changes in branches:
        per_field = {}
        for change in changes:
            per_field[change.field] = change
        for field, change in per_field.items():
            if field not in candidates:
                candidates[field] = []
                fields.append(field)
            candidates[field].append(Option(source, change))

    entries = []
    conflicts = []
    version = start_version
    for field in fields:
        options = candidates[field]
        first_value = options[0].change.value
        if len(options) > 1 and any(o.change.value != first_value for o in options[1:]):
            winner = resolve(field, options)
            losers = [o for o in options if o is not winner]
            conflicts.append(Conflict(field, winner, losers))
        else:
            winner = options[0]
        change = log.append(obj, field, winner.change.value, version)
        entries.append(MergedEntry(change, winner.source))
        version += 1
    return MergeResult(entries, conflicts)
