"""多分支合并的行为测试。"""

import unittest

from changelogd.changelog import DELETED, ChangeLog
from changelogd.merge import Conflict, MergeResult, last_write_wins, merge


class Tick:
    """注入时钟：每次调用前进 1 秒。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        self.now += 1.0
        return self.now


def branch_log(start, writes):
    """造一条分支日志：writes 为 (field, value, version) 序列。"""
    log = ChangeLog(clock=Tick(start))
    for field, value, version in writes:
        log.append("doc", field, value, version)
    return log


def zhang_and_li():
    """老张改标题和状态，小李动状态还补了标签，从同一版本分叉。"""
    zhang = branch_log(100.0, [
        ("title", "老张的标题", 2),
        ("status", "review", 2),
    ])
    li = branch_log(200.0, [
        ("status", "published", 3),
        ("tag", "release", 3),
    ])
    return [("zhang", zhang.history("doc")), ("li", li.history("doc"))]


class TestDefaultMerge(unittest.TestCase):
    def test_disjoint_fields_merge_and_conflict_resolved(self):
        log = ChangeLog(clock=Tick())
        result = merge(log, "doc", zhang_and_li(), start_version=10)

        self.assertEqual(
            [e.change.field for e in result.entries],
            ["title", "status", "tag"],
        )
        # 版本从 start_version 起递增，ts 取自注入时钟
        self.assertEqual([e.change.version for e in result.entries], [10, 11, 12])
        self.assertEqual([e.change.ts for e in result.entries], [1.0, 2.0, 3.0])
        # 每条都能说清来自哪条分支；status 撞车，默认版本高的小李胜
        self.assertEqual(
            [e.source for e in result.entries], ["zhang", "li", "li"])
        self.assertEqual(
            result.snapshot(),
            {"title": "老张的标题", "status": "published", "tag": "release"},
        )
        # 合并结果落进了目标日志，at 与 result.snapshot() 一致
        self.assertEqual(log.at("doc", 12), result.snapshot())
        self.assertEqual(len(log.history("doc")), 3)

    def test_conflict_books_winner_and_losers(self):
        log = ChangeLog(clock=Tick())
        result = merge(log, "doc", zhang_and_li(), start_version=10)

        self.assertEqual(len(result.conflicts), 1)
        conflict = result.conflicts[0]
        self.assertIsInstance(conflict, Conflict)
        self.assertEqual(conflict.field, "status")
        self.assertEqual(conflict.winner.source, "li")
        self.assertEqual(conflict.winner.change.value, "published")
        # 输家也记录在案，能复盘
        self.assertEqual(len(conflict.losers), 1)
        self.assertEqual(conflict.losers[0].source, "zhang")
        self.assertEqual(conflict.losers[0].change.value, "review")
        self.assertEqual(result.losers, list(conflict.losers))

    def test_same_value_on_both_sides_is_not_a_conflict(self):
        branches = [
            ("a", branch_log(0.0, [("status", "done", 2)]).history("doc")),
            ("b", branch_log(0.0, [("status", "done", 3)]).history("doc")),
        ]
        result = merge(ChangeLog(clock=Tick()), "doc", branches)
        self.assertEqual(result.conflicts, [])
        self.assertEqual([e.source for e in result.entries], ["a"])
        self.assertEqual(result.snapshot(), {"status": "done"})

    def test_version_tie_broken_by_branch_order(self):
        branches = [
            ("a", branch_log(0.0, [("status", "x", 2)]).history("doc")),
            ("b", branch_log(0.0, [("status", "y", 2)]).history("doc")),
        ]
        result = merge(ChangeLog(clock=Tick()), "doc", branches)
        self.assertEqual(result.conflicts[0].winner.source, "b")
        self.assertEqual(result.snapshot(), {"status": "y"})

    def test_later_change_within_branch_wins_before_merge(self):
        branches = [
            ("a", branch_log(0.0, [("t", "old", 2), ("t", "new", 3)]).history("doc")),
            ("b", branch_log(0.0, [("t", "other", 2)]).history("doc")),
        ]
        result = merge(ChangeLog(clock=Tick()), "doc", branches)
        self.assertEqual(result.conflicts[0].winner.change.value, "new")


class TestCustomResolver(unittest.TestCase):
    def test_custom_resolver_picks_winner(self):
        calls = []

        def prefer_zhang(field, options):
            calls.append((field, list(options)))
            for option in options:
                if option.source == "zhang":
                    return option
            return options[0]

        log = ChangeLog(clock=Tick())
        result = merge(log, "doc", zhang_and_li(), resolve=prefer_zhang)

        # 消解函数收到字段名与各分支候选
        self.assertEqual([c[0] for c in calls], ["status"])
        self.assertEqual([o.source for o in calls[0][1]], ["zhang", "li"])
        # 业务口径换成老张优先，输家变成小李
        self.assertEqual(result.snapshot()["status"], "review")
        self.assertEqual(result.conflicts[0].winner.source, "zhang")
        self.assertEqual(result.conflicts[0].losers[0].source, "li")
        self.assertEqual(
            [e.source for e in result.entries], ["zhang", "zhang", "li"])

    def test_default_resolver_is_last_write_wins(self):
        log = ChangeLog(clock=Tick())
        result = merge(log, "doc", zhang_and_li(), resolve=last_write_wins)
        self.assertEqual(result.snapshot()["status"], "published")


class TestDeleteSemantics(unittest.TestCase):
    def test_delete_beats_concurrent_modify(self):
        # 老张删掉字段，小李同时改它：最终快照不该再冒出这个字段
        branches = [
            ("zhang", branch_log(0.0, [("tag", DELETED, 2)]).history("doc")),
            ("li", branch_log(0.0, [("tag", "release", 3)]).history("doc")),
        ]
        log = ChangeLog(clock=Tick())
        result = merge(log, "doc", branches, start_version=5)

        self.assertEqual(result.snapshot(), {})
        self.assertEqual(log.at("doc", 5), {})
        # 冲突记在案：删除方赢，修改方是输家
        conflict = result.conflicts[0]
        self.assertEqual(conflict.winner.source, "zhang")
        self.assertIs(conflict.winner.change.value, DELETED)
        self.assertEqual(conflict.losers[0].change.value, "release")
        # 历史里看得见中间发生过什么
        history = log.history("doc")
        self.assertEqual(len(history), 1)
        self.assertIs(history[0].value, DELETED)
        self.assertEqual(result.entries[0].source, "zhang")

    def test_at_treats_deleted_as_absent(self):
        log = ChangeLog(clock=Tick())
        log.append("doc", "a", 1, 1)
        log.append("doc", "a", DELETED, 2)
        log.append("doc", "a", 3, 3)
        self.assertEqual(log.at("doc", 1), {"a": 1})
        self.assertEqual(log.at("doc", 2), {})
        self.assertEqual(log.at("doc", 3), {"a": 3})
        # 历史不受墓碑影响，全程可见
        self.assertEqual(len(log.history("doc")), 3)

    def test_readd_within_branch_survives_merge(self):
        # 同一分支里先删后补，以分支内最后一条为准
        branches = [
            ("a", branch_log(0.0, [("t", DELETED, 2), ("t", "back", 3)]).history("doc")),
            ("b", branch_log(0.0, [("t", "other", 2)]).history("doc")),
        ]
        result = merge(ChangeLog(clock=Tick()), "doc", branches)
        self.assertEqual(result.snapshot(), {"t": "back"})


class TestMergeResult(unittest.TestCase):
    def test_result_types_and_fresh_snapshot(self):
        log = ChangeLog(clock=Tick())
        result = merge(log, "doc", zhang_and_li())
        self.assertIsInstance(result, MergeResult)
        snap = result.snapshot()
        snap["title"] = "篡改"
        self.assertNotEqual(result.snapshot()["title"], "篡改")

    def test_unknown_object_untouched_by_merge(self):
        log = ChangeLog(clock=Tick())
        merge(log, "doc", zhang_and_li())
        self.assertEqual(log.at("other", 99), {})
        self.assertEqual(log.objects(), ["doc"])


if __name__ == "__main__":
    unittest.main()
