"""多分支合并的行为测试。

所有用例都注入时钟：合并日志的 ts 取自注入序列，版本号保持分支原值，
借此断言每条合并变更的版本与来源。
"""

import unittest

from changelogd.changelog import DELETED, ChangeLog
from changelogd.merge import (
    Candidate,
    Conflict,
    MergeResult,
    MergedChange,
    first_write_wins,
    last_write_wins,
    merge,
)


def branch_from(base, obj):
    """从 base 分叉出一个共享基线历史的新分支。"""
    fork = ChangeLog(clock=lambda: 0.0)
    for c in base.history(obj):
        fork.append(c.obj, c.field, c.value, c.version)
    return fork


def ticking_clock(start=100.0, step=1.0):
    ticks = iter([start + i * step for i in range(1000)])
    return lambda: next(ticks)


class MergeFixture(unittest.TestCase):
    """老张和小李从 v2 分叉：老张改标题和状态，小李改状态、补标签。"""

    def setUp(self):
        self.base = ChangeLog(clock=lambda: 0.0)
        self.base.append("doc", "title", "草稿", 1)
        self.base.append("doc", "status", "draft", 2)

        zhang = branch_from(self.base, "doc")
        zhang.append("doc", "title", "定稿", 3)
        zhang.append("doc", "status", "review", 3)

        li = branch_from(self.base, "doc")
        li.append("doc", "status", "published", 4)
        li.append("doc", "tag", "release", 4)

        self.branches = {"zhang": zhang, "li": li}

    def merge(self, **kwargs):
        return merge("doc", self.branches, 2, clock=ticking_clock(), **kwargs)


class TestDefaultMerge(MergeFixture):
    def test_snapshot_combines_both_branches(self):
        result = self.merge()
        self.assertEqual(
            result.log.at("doc", 4),
            {"title": "定稿", "status": "published", "tag": "release"},
        )

    def test_every_merged_change_knows_its_origin(self):
        result = self.merge()
        pairs = {
            (c.change.field, c.origin)
            for c in result.changes
            if c.change.version > 2
        }
        self.assertEqual(
            pairs,
            {
                ("title", "zhang"),
                ("status", "zhang"),
                ("status", "li"),
                ("tag", "li"),
            },
        )

    def test_merged_changes_keep_original_versions(self):
        result = self.merge()
        versions = {
            (c.change.field, c.origin): c.change.version
            for c in result.changes
            if c.change.version > 2
        }
        self.assertEqual(
            versions,
            {
                ("title", "zhang"): 3,
                ("status", "zhang"): 3,
                ("status", "li"): 4,
                ("tag", "li"): 4,
            },
        )

    def test_merged_log_stamped_by_injected_clock(self):
        result = self.merge()
        history = result.log.history("doc")
        self.assertEqual(
            [c.ts for c in history], [100.0 + i for i in range(len(history))]
        )

    def test_base_changes_are_copied_into_new_log(self):
        result = self.merge()
        self.assertEqual(
            result.log.at("doc", 2), {"title": "草稿", "status": "draft"}
        )

    def test_conflict_records_winner_and_losers(self):
        result = self.merge()
        self.assertEqual(len(result.conflicts), 1)
        conflict = result.conflicts[0]
        self.assertIsInstance(conflict, Conflict)
        self.assertEqual(conflict.field, "status")
        self.assertEqual(conflict.winner.origin, "li")
        self.assertEqual(conflict.winner.change.value, "published")
        self.assertEqual(
            [(c.origin, c.change.value) for c in conflict.losers],
            [("zhang", "review")],
        )

    def test_result_shape(self):
        result = self.merge()
        self.assertIsInstance(result, MergeResult)
        self.assertTrue(all(isinstance(c, MergedChange) for c in result.changes))

    def test_default_tie_goes_to_later_branch(self):
        # 同字段同版本撞车：分支顺序靠后者胜
        zhang = branch_from(self.base, "doc")
        zhang.append("doc", "status", "review", 3)
        li = branch_from(self.base, "doc")
        li.append("doc", "status", "published", 3)
        result = merge("doc", {"zhang": zhang, "li": li}, 2, clock=ticking_clock())
        self.assertEqual(result.log.at("doc", 3)["status"], "published")
        self.assertEqual(result.conflicts[0].winner.origin, "li")

    def test_same_value_on_both_sides_is_not_a_conflict(self):
        zhang = branch_from(self.base, "doc")
        zhang.append("doc", "status", "done", 3)
        li = branch_from(self.base, "doc")
        li.append("doc", "status", "done", 4)
        result = merge("doc", {"zhang": zhang, "li": li}, 2, clock=ticking_clock())
        self.assertEqual(result.conflicts, [])
        self.assertEqual(result.log.at("doc", 4)["status"], "done")


class TestDeleteSemantics(unittest.TestCase):
    def setUp(self):
        self.base = ChangeLog(clock=lambda: 0.0)
        self.base.append("doc", "temp", "待清理", 1)

    def test_delete_beats_concurrent_edit(self):
        # 老张删掉字段，小李随后改它：快照里不该再冒出来
        zhang = branch_from(self.base, "doc")
        zhang.append("doc", "temp", DELETED, 2)
        li = branch_from(self.base, "doc")
        li.append("doc", "temp", "改回", 3)
        result = merge("doc", {"zhang": zhang, "li": li}, 1, clock=ticking_clock())
        self.assertEqual(result.log.at("doc", 3), {})
        conflict = result.conflicts[0]
        self.assertEqual(conflict.winner.origin, "zhang")
        self.assertIs(conflict.winner.change.value, DELETED)
        self.assertEqual([c.origin for c in conflict.losers], ["li"])

    def test_history_still_shows_delete_and_edit(self):
        zhang = branch_from(self.base, "doc")
        zhang.append("doc", "temp", DELETED, 2)
        li = branch_from(self.base, "doc")
        li.append("doc", "temp", "改回", 3)
        result = merge("doc", {"zhang": zhang, "li": li}, 1, clock=ticking_clock())
        values = [
            c.value for c in result.log.history("doc") if c.field == "temp"
        ]
        self.assertEqual(values, ["待清理", "改回", DELETED])

    def test_lone_delete_removes_field_from_snapshot(self):
        zhang = branch_from(self.base, "doc")
        zhang.append("doc", "temp", DELETED, 2)
        result = merge("doc", {"zhang": zhang}, 1, clock=ticking_clock())
        self.assertEqual(result.log.at("doc", 2), {})
        self.assertEqual(result.conflicts, [])


class TestResolvers(MergeFixture):
    def test_first_write_wins_strategy(self):
        result = self.merge(resolver=first_write_wins)
        self.assertEqual(result.log.at("doc", 4)["status"], "review")
        self.assertEqual(result.conflicts[0].winner.origin, "zhang")
        self.assertEqual([c.origin for c in result.conflicts[0].losers], ["li"])

    def test_custom_resolver(self):
        # 业务口径：状态一律以老张为准
        def zhang_decides(field, candidates):
            return next(c for c in candidates if c.origin == "zhang")

        result = self.merge(resolver=zhang_decides)
        self.assertEqual(result.log.at("doc", 4)["status"], "review")
        self.assertEqual(result.conflicts[0].winner.change.value, "review")

    def test_custom_resolver_receives_field_and_candidates(self):
        seen = {}

        def spy(field, candidates):
            seen["field"] = field
            seen["candidates"] = candidates
            return last_write_wins(field, candidates)

        self.merge(resolver=spy)
        self.assertEqual(seen["field"], "status")
        self.assertTrue(all(isinstance(c, Candidate) for c in seen["candidates"]))
        self.assertEqual({c.origin for c in seen["candidates"]}, {"zhang", "li"})

    def test_resolver_must_return_a_candidate(self):
        def outsider(field, candidates):
            return Candidate("ghost", candidates[0].change)

        with self.assertRaises(ValueError):
            self.merge(resolver=outsider)


class TestMergeTarget(MergeFixture):
    def test_merge_into_existing_log_uses_its_clock(self):
        into = ChangeLog(clock=lambda: 7.0)
        result = merge("doc", self.branches, 2, into=into)
        self.assertIs(result.log, into)
        self.assertTrue(all(c.change.ts == 7.0 for c in result.changes))
        # into 里没有基线，快照只含基线之后的变更
        self.assertEqual(
            into.at("doc", 4),
            {"title": "定稿", "status": "published", "tag": "release"},
        )

    def test_branches_accepted_as_pairs(self):
        result = merge(
            "doc", list(self.branches.items()), 2, clock=ticking_clock()
        )
        self.assertEqual(result.log.at("doc", 4)["status"], "published")

    def test_disjoint_fields_merge_without_conflicts(self):
        zhang = branch_from(self.base, "doc")
        zhang.append("doc", "title", "定稿", 3)
        li = branch_from(self.base, "doc")
        li.append("doc", "tag", "release", 3)
        result = merge("doc", {"zhang": zhang, "li": li}, 2, clock=ticking_clock())
        self.assertEqual(result.conflicts, [])
        self.assertEqual(
            result.log.at("doc", 3),
            {"title": "定稿", "status": "draft", "tag": "release"},
        )


if __name__ == "__main__":
    unittest.main()
