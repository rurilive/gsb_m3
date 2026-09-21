"""多分支合并的行为测试。

场景：老张（zhang）和小李（li）从 v2 分叉各自动手——
老张改标题和状态，小李也改状态还补了标签。时钟全部注入。
"""

import unittest

from changelogd.changelog import DELETED, Change, ChangeLog
from changelogd.merge import Candidate, Conflict, MergeResult, merge


class Tick:
    """注入时钟：每次调用 +1。"""

    def __init__(self, start=0.0):
        self.t = start

    def __call__(self):
        self.t += 1.0
        return self.t


def make_branches():
    """老张：标题+状态；小李：状态（冲突）+标签。版本从 v3 起。"""
    zhang = ChangeLog(clock=Tick(10.0))
    zhang.append("doc", "title", "老张的标题", 3)
    zhang.append("doc", "status", "published", 3)

    li = ChangeLog(clock=Tick(20.0))
    li.append("doc", "status", "archived", 4)
    li.append("doc", "tag", "urgent", 4)
    return {"zhang": zhang, "li": li}


class TestMergeBasics(unittest.TestCase):
    def test_result_shape_and_sources(self):
        result = merge("doc", make_branches(), clock=Tick(100.0))
        self.assertIsInstance(result, MergeResult)
        # 双方全部变更都进合并日志，每条都能说清来源
        self.assertEqual(len(result.history()), 4)
        for cand in result.entries:
            self.assertIsInstance(cand, Candidate)
            self.assertIn(cand.source, ("zhang", "li"))
            self.assertIsInstance(cand.change, Change)
            self.assertEqual(result.source_of(cand.change), cand.source)

    def test_versions_kept_and_ts_from_injected_clock(self):
        result = merge("doc", make_branches(), clock=Tick(100.0))
        # 合并日志按 (version, 分支名, 分支内顺序) 排列
        self.assertEqual(
            [(c.change.field, c.change.version, c.source) for c in result.entries],
            [
                ("title", 3, "zhang"),
                ("status", 3, "zhang"),
                ("status", 4, "li"),
                ("tag", 4, "li"),
            ],
        )
        self.assertEqual(
            [cand.change.ts for cand in result.entries],
            [101.0, 102.0, 103.0, 104.0],
        )

    def test_non_conflicting_fields_merge_independently(self):
        result = merge("doc", make_branches(), clock=Tick())
        snap = result.at(99)
        self.assertEqual(snap["title"], "老张的标题")  # 只有老张动过
        self.assertEqual(snap["tag"], "urgent")  # 只有小李动过

    def test_default_strategy_picks_higher_version(self):
        result = merge("doc", make_branches(), clock=Tick())
        self.assertEqual(result.at(99)["status"], "archived")  # li v4 胜 zhang v3

    def test_default_strategy_tie_breaks_by_source_name(self):
        zhang = ChangeLog(clock=Tick())
        zhang.append("doc", "status", "published", 3)
        li = ChangeLog(clock=Tick())
        li.append("doc", "status", "archived", 3)
        result = merge("doc", {"zhang": zhang, "li": li}, clock=Tick())
        self.assertEqual(result.at(99)["status"], "published")  # 并列取分支名大者

    def test_named_strategy_first_is_swappable(self):
        result = merge("doc", make_branches(), strategy="first", clock=Tick())
        self.assertEqual(result.at(99)["status"], "published")  # 先写优先：v3 胜

    def test_custom_resolver_function(self):
        seen = []

        def prefer_li(field, candidates):
            seen.append((field, sorted(c.source for c in candidates)))
            for cand in candidates:
                if cand.source == "li":
                    return cand
            return candidates[0]

        result = merge("doc", make_branches(), strategy=prefer_li, clock=Tick())
        self.assertEqual(result.at(99)["status"], "archived")
        self.assertEqual(seen, [("status", ["li", "zhang"])])

    def test_unknown_strategy_raises(self):
        with self.assertRaises(ValueError):
            merge("doc", make_branches(), strategy="nope", clock=Tick())

    def test_merge_does_not_touch_branch_logs(self):
        branches = make_branches()
        merge("doc", branches, clock=Tick())
        self.assertEqual(len(branches["zhang"].history("doc")), 2)
        self.assertEqual(len(branches["li"].history("doc")), 2)


class TestConflicts(unittest.TestCase):
    def test_conflict_records_winner_and_losers(self):
        result = merge("doc", make_branches(), clock=Tick())
        self.assertEqual(len(result.conflicts), 1)
        conf = result.conflicts[0]
        self.assertIsInstance(conf, Conflict)
        self.assertEqual(conf.field, "status")
        self.assertEqual(
            (conf.winner.change.value, conf.winner.source), ("archived", "li")
        )
        self.assertEqual(
            [(c.change.value, c.source) for c in conf.losers],
            [("published", "zhang")],
        )

    def test_same_value_on_both_sides_is_not_a_conflict(self):
        zhang = ChangeLog(clock=Tick())
        zhang.append("doc", "status", "done", 3)
        li = ChangeLog(clock=Tick())
        li.append("doc", "status", "done", 4)
        result = merge("doc", {"zhang": zhang, "li": li}, clock=Tick())
        self.assertEqual(result.conflicts, [])
        self.assertEqual(result.at(99), {"status": "done"})

    def test_loser_stays_in_merged_history(self):
        result = merge("doc", make_branches(), clock=Tick())
        loser = result.conflicts[0].losers[0]
        self.assertIn(loser.change, result.history())
        self.assertEqual(result.source_of(loser.change), "zhang")


class TestDeleteSemantics(unittest.TestCase):
    def make_delete_branches(self):
        zhang = ChangeLog(clock=Tick())
        zhang.append("doc", "legacy", DELETED, 3)  # 老张删掉 legacy
        li = ChangeLog(clock=Tick())
        li.append("doc", "legacy", "小李又改了它", 4)  # 小李删除后又改
        return {"zhang": zhang, "li": li}

    def test_delete_wins_over_later_modify(self):
        result = merge("doc", self.make_delete_branches(), clock=Tick())
        self.assertEqual(result.at(99), {})  # 最终快照不再冒出 legacy

    def test_history_shows_what_happened_in_between(self):
        result = merge("doc", self.make_delete_branches(), clock=Tick())
        trail = [(c.field, c.value, c.version) for c in result.history()]
        self.assertEqual(
            trail,
            [("legacy", "小李又改了它", 4), ("legacy", DELETED, 3)],
        )

    def test_delete_conflict_is_recorded(self):
        result = merge("doc", self.make_delete_branches(), clock=Tick())
        (conf,) = result.conflicts
        self.assertEqual(conf.field, "legacy")
        self.assertIs(conf.winner.change.value, DELETED)
        self.assertEqual([c.change.value for c in conf.losers], ["小李又改了它"])

    def test_modify_after_delete_on_same_line_reappears(self):
        log = ChangeLog(clock=Tick())
        log.append("doc", "a", 1, 1)
        log.append("doc", "a", DELETED, 2)
        log.append("doc", "a", 3, 3)
        self.assertEqual(log.at("doc", 2), {})
        self.assertEqual(log.at("doc", 3), {"a": 3})


if __name__ == "__main__":
    unittest.main()
