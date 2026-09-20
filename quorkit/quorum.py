"""按多数派选主的法定人数小工具。

集群成员由外部注入的 MemberTable 描述（测试里借它模拟节点的加入、
离开与失联），所有时刻都来自构造时传入的 clock；纯标准库，不碰
真实时间，也不用真等。

一个 Quorum 实例代表一个节点：它记下自己收到的心跳、维护自己的
任期号，并按当前在册成员里的活跃多数派判断自己能不能当 leader。
"""

import threading
import time


class MemberTable:
    """在册成员表。

    由外部持有，可以同时注入给多个节点，用来模拟真实集群里各节点
    看到的成员视图。节点的加入和离开都记在这里。
    """

    def __init__(self, nodes=()):
        self._lock = threading.Lock()
        self._members = set(nodes)

    def add(self, node):
        """把节点加进在册成员。"""
        with self._lock:
            self._members.add(node)

    def remove(self, node):
        """把节点从在册成员里摘掉；不在册时静默忽略。"""
        with self._lock:
            self._members.discard(node)

    def nodes(self):
        """当前在册成员的快照。"""
        with self._lock:
            return set(self._members)

    def __len__(self):
        with self._lock:
            return len(self._members)

    def __contains__(self, node):
        with self._lock:
            return node in self._members


class Quorum:
    """单个节点的法定人数判定器。

    cluster: 注入的 MemberTable，多个节点可以共享同一份。
    clock:   返回当前时刻的可调用对象，默认 time.monotonic，测试可注入。
    timeout: 本节点配置的失联超时，单位秒。
    config:  集群商量好的公共配置，例如 {"heartbeat_timeout": 5.0}；
             只要协商过，各节点就该以它为准。

    内部一把锁保护，单个方法调用对多线程安全。
    """

    def __init__(self, cluster, clock=time.monotonic, timeout=1.0, config=None):
        if timeout <= 0:
            raise ValueError("timeout must be > 0")
        self._cluster = cluster
        self._clock = clock
        self._timeout = timeout
        self._config = config or {}
        self._term = 0
        self._seen = {}                                # node -> 最近一次有效心跳时刻
        self._lock = threading.Lock()

    def majority(self):
        """按当前在册成员动态算出的多数派门槛。

        成员表由外部持有、随时可能扩容或缩容，所以这里不能缓存构造时的
        成员数，每次都按此刻的在册规模重算（偶数集群向上取整）。
        """
        with self._lock:
            return len(self._cluster) // 2 + 1

    def negotiated_timeout(self):
        """集群协商出来的失联超时；没协商过就退回本地配置。"""
        return self._config.get("heartbeat_timeout", self._timeout)

    def heartbeat(self, node, ts, term=0):
        """记下 node 在 ts 时刻的心跳，它在这条心跳里声称自己处于 term 任期。

        任期只能严格往前走：落后于本节点已知任期的心跳一律不认，既不更新
        活跃时间戳也不参与计票；更高级别的心跳则把本节点带到同一任期
        （Raft 风格的任期对齐）。返回这条心跳是否被采纳。
        """
        with self._lock:
            if term < self._term:
                return False
            if term > self._term:
                self._term = term
            self._seen[node] = ts
            return True

    def term(self):
        """本节点目前的任期号，初始为 0。"""
        with self._lock:
            return self._term

    def active(self):
        """此刻还活着的节点集合，返回独立快照。"""
        with self._lock:
            return self._active(self._clock())

    def elect(self):
        """按多数派把自己选成 leader。

        票够就任期加一、当上 leader 并返回新任期；票不够返回 None。
        """
        with self._lock:
            votes = len(self._active(self._clock()))
            if votes < self._majority_locked():
                return None
            self._term += 1
            return self._term

    def _active(self, now):
        """挑出此刻还活着的在册节点。调用方必须持锁。

        活跃判定以集群协商好的失联超时为准（没协商过才退回本地配置），
        各节点因此对“谁还活着”看法一致；同时只统计当前在册成员，被
        摘除的节点即便留有旧心跳时间戳也立刻退出计票。
        """
        timeout = self.negotiated_timeout()
        members = self._cluster.nodes()
        return {
            node
            for node, ts in self._seen.items()
            if node in members and now - ts < timeout
        }

    def _majority_locked(self):
        """多数派门槛的持锁版本，避免在锁内重入公开方法。"""
        return len(self._cluster) // 2 + 1
