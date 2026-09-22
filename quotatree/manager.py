"""扁平配额管理器。

一个团队一份固定额度，注册时定死，申请从额度里扣，归还把没用掉的退回来，
扣不动的申请当场拒掉，不欠账。所有写操作可以带 req_id：同一个 req_id 重复
提交只记一次账，重试拿首次的结果，额度不重复动，被拒过的也是这个规矩。
"""

from .errors import UnknownTeam
from .ledger import Ledger


def check_amount(amount, what):
    """额度、申请量与归还量都限定为正整数。"""
    if isinstance(amount, bool) or not isinstance(amount, int) or amount <= 0:
        raise ValueError("%s必须是正整数，收到 %r" % (what, amount))
    return amount


class QuotaManager:
    """平铺的团队额度管理器。"""

    def __init__(self, ledger=None):
        self.ledger = ledger if ledger is not None else Ledger()
        self._limits = {}
        self._used = {}
        self._requests = {}

    # ---- 注册 ----
    def register(self, team, limit):
        """注册团队并定死额度，重复注册报 ValueError。"""
        if not isinstance(team, str) or not team:
            raise ValueError("团队名必须是非空字符串，收到 %r" % (team,))
        check_amount(limit, "额度")
        if team in self._limits:
            raise ValueError("团队 %r 已经注册过了" % (team,))
        self._limits[team] = limit
        self._used[team] = 0

    # ---- 写 ----
    def acquire(self, team, amount, req_id=None):
        """申请额度。可用额够就扣下来返回 True，不够返回 False。"""
        self._require(team)
        check_amount(amount, "申请量")
        done = self._replay(req_id, "acquire", team, amount)
        if done is not None:
            return done
        ok = self._used[team] + amount <= self._limits[team]
        if ok:
            self._used[team] += amount
        self.ledger.record(team, "acquire", amount, ok, req_id)
        self._remember(req_id, "acquire", team, amount, ok)
        return ok

    def release(self, team, amount, req_id=None):
        """归还额度。归还量超过当前占用报 ValueError。"""
        self._require(team)
        check_amount(amount, "归还量")
        done = self._replay(req_id, "release", team, amount)
        if done is not None:
            return done
        if amount > self._used[team]:
            raise ValueError(
                "团队 %r 只占着 %d，退不了 %d" % (team, self._used[team], amount))
        self._used[team] -= amount
        self.ledger.record(team, "release", amount, True, req_id)
        self._remember(req_id, "release", team, amount, True)
        return True

    # ---- 读 ----
    def available(self, team):
        """还能申请的额度。"""
        self._require(team)
        return self._limits[team] - self._used[team]

    def used(self, team):
        """当前占用。"""
        self._require(team)
        return self._used[team]

    def limit(self, team):
        """注册时定下的额度。"""
        self._require(team)
        return self._limits[team]

    def teams(self):
        """全部团队名，升序。"""
        return sorted(self._limits)

    # ---- 内部 ----
    def _require(self, team):
        if team not in self._limits:
            raise UnknownTeam("团队 %r 没注册过" % (team,))

    def _replay(self, req_id, kind, team, amount):
        if req_id is None:
            return None
        seen = self._requests.get(req_id)
        if seen is None:
            return None
        if seen[:3] != (kind, team, amount):
            raise ValueError(
                "请求 ID %r 已经用在 %r 上，不能改口" % (req_id, seen[:3]))
        self.ledger.record(team, "replay", amount, seen[3], req_id)
        return seen[3]

    def _remember(self, req_id, kind, team, amount, result):
        if req_id is not None:
            self._requests[req_id] = (kind, team, amount, result)
