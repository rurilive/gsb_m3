"""操作流水账。

每次申请、归还都留一条，被拒的和重复提交的也照留，供对账与审计。
流水只追加不回改，entries 与 by_team 返回副本，拿在手里随便改不影响账。
"""

KINDS = ("acquire", "release", "replay")


class Ledger:
    """顺序追加的流水账。"""

    def __init__(self):
        self._entries = []
        self._counts = dict.fromkeys(KINDS, 0)
        self._rejected = 0

    def record(self, team, kind, amount, ok, req_id=None):
        """记一条流水，返回这条记录。

        kind 只认 KINDS 里的三类；ok 为 False 表示这次请求被拒。
        """
        if kind not in self._counts:
            raise ValueError("未知的流水类型 %r，只认 %s" % (kind, ", ".join(KINDS)))
        entry = {
            "seq": len(self._entries) + 1,
            "team": team,
            "kind": kind,
            "amount": amount,
            "ok": bool(ok),
            "req_id": req_id,
        }
        self._entries.append(entry)
        self._counts[kind] += 1
        if not ok:
            self._rejected += 1
        return dict(entry)

    def entries(self):
        """全部流水，按发生顺序，返回副本。"""
        return [dict(entry) for entry in self._entries]

    def by_team(self, team):
        """某个团队的流水，按发生顺序，返回副本。"""
        return [dict(e) for e in self._entries if e["team"] == team]

    def count(self):
        return len(self._entries)

    def stats(self):
        """按类型计数的汇总，另有 rejected 统计被拒条数。"""
        summary = dict(self._counts)
        summary["rejected"] = self._rejected
        return summary
