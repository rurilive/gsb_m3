"""基于多数派的选主与租约。

集群用一个可变的成员表来模拟：字典 node -> 是否在线，调用方直接改
这张表就等价于成员上下线或成员增减。时钟可注入，便于测试。
"""

import time


class QuorumLease:
    """一个集群视图上的多数派选主与租约。

    voters: 成员表 dict，node -> bool（在线为 True）。注入后归调用方持有，
            成员增减或上下线直接改它，等价于集群配置变化。
    clock: 零参可调用对象，返回当前时刻，默认 time.monotonic。
    lease_seconds: 续租一次给到的租约时长。
    """

    def __init__(self, voters, clock=time.monotonic, lease_seconds=10.0):
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        self._voters = voters
        self._clock = clock
        self._lease_seconds = lease_seconds
        self._leader = None
        self._term = 0
        self._expires_at = None

    # ---- 成员表视图 ----

    def members(self):
        """全部成员，按名字排序。"""
        return sorted(self._voters)

    def alive_members(self):
        """当前在线的成员，按名字排序。"""
        return sorted(n for n, up in self._voters.items() if up)

    def quorum_size(self):
        """多数派规模：全体成员数的一半向下取整再加一。"""
        return len(self._voters) // 2 + 1

    def has_quorum(self):
        """在线成员是否够当前配置的多数派。"""
        return len(self.alive_members()) >= self.quorum_size()

    # ---- 选主 ----

    def elect(self):
        """在在线成员里选主，取名字最小的那个。

        在线成员凑不齐多数派时返回 None，不动现有 leader。
        选出新 leader 时任期加一。
        """
        alive = self.alive_members()
        if len(alive) < self.quorum_size():
            return None
        self._leader = alive[0]
        self._term += 1
        return self._leader

    def leader(self):
        """当前 leader，没有时为 None。"""
        return self._leader

    def term(self):
        """任期计数，每次成功选主加一。"""
        return self._term

    # ---- 租约 ----

    def renew(self, node):
        """leader 续租：把到期时刻刷成 now + lease_seconds。

        不是当前 leader 就返回 False，不改到期时刻。
        """
        if node != self._leader:
            return False
        self._expires_at = self._clock() + self._lease_seconds
        return True

    def lease_expires_at(self):
        """当前租约的到期时刻，没有租约时为 None。"""
        return self._expires_at
