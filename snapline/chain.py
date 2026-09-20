"""对象快照链。

每个对象维护一条按版本号记录的状态链：snapshot() 追加一版，
at() 回读某一版，latest() 取当前版本，history() 列出全部版本。
时间由注入的 clock 提供，默认 time.monotonic，测试可替换。
"""

import threading
import time


class _Node:
    """链上的一版快照。"""

    __slots__ = ("version", "seq", "ts", "state", "prev", "next")

    def __init__(self, version, seq, ts, state):
        self.version = version
        self.seq = seq
        self.ts = ts
        self.state = state
        self.prev = None
        self.next = None


class SnapLine:
    """按对象维护的历史快照链。

    clock: 返回当前时刻的可调用对象，默认 time.monotonic。
    """

    def __init__(self, clock=time.monotonic):
        self._clock = clock
        self._lock = threading.Lock()
        self._seq = 0
        self._nodes = {}      # obj_id -> {version: _Node}
        self._tail = {}       # obj_id -> 链上最早的一版
        self._head = {}       # obj_id -> 物理上最后写入的一版
        self._cursor = {}     # obj_id -> 当前版本，rollback 会挪动它
        self._issued = {}     # obj_id -> 已经发放过的最大版本号

    # -- 写入 ------------------------------------------------------------

    def _next_seq(self):
        """取下一个提交序号。"""
        self._seq = self._seq + 1
        return self._seq

    def _allocate(self, obj_id):
        """给新快照分配版本号。"""
        current = self._cursor.get(obj_id)
        if current is None:
            return 1
        return current.version + 1

    def snapshot(self, obj_id, state):
        """记一版快照，返回分配到的版本号。"""
        seq = self._next_seq()
        version = self._allocate(obj_id)
        ts = self._clock()
        node = _Node(version, seq, ts, state)
        with self._lock:
            nodes = self._nodes.setdefault(obj_id, {})
            nodes[version] = node
            head = self._head.get(obj_id)
            node.prev = head
            if head is None:
                self._tail[obj_id] = node
            else:
                head.next = node
            self._head[obj_id] = node
            self._cursor[obj_id] = node
            self._issued[obj_id] = version
        return version

    def rollback(self, obj_id, version):
        """把对象的当前版本指回链上已有的某一版。"""
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            node = nodes.get(version)
            if node is None:
                raise KeyError(version)
            # 重新登记一次，表示它成了当前版本
            nodes.pop(version)
            nodes[version] = node
            self._cursor[obj_id] = node

    def delete(self, obj_id, version):
        """从链上删掉某一版，返回是否真的删掉了。"""
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            node = nodes.get(version)
            if node is None:
                return False
            prev_node, next_node = node.prev, node.next
            if prev_node is None:
                self._tail[obj_id] = next_node
            else:
                prev_node.next = next_node
            if next_node is None:
                self._head[obj_id] = prev_node
            # 摘掉自身，避免残留引用
            node.prev = None
            node.next = None
            del nodes[version]
            if self._cursor.get(obj_id) is node:
                self._cursor[obj_id] = prev_node
            return True

    # -- 读取 ------------------------------------------------------------

    def at(self, obj_id, version):
        """回读该对象指定版本的状态，版本不存在返回 None。"""
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            if version not in nodes:
                return None
            node = self._head.get(obj_id)
            while node is not None:
                if node.version == version:
                    return node.state
                node = node.prev
            return None

    def latest(self, obj_id):
        """取当前版本，返回 (version, state)；对象不存在返回 None。"""
        with self._lock:
            node = self._cursor.get(obj_id)
            if node is None:
                return None
            return (node.version, node.state)

    def history(self, obj_id):
        """按创建时刻列出该对象的全部版本号，旧的在前。"""
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            ordered = sorted(nodes.values(), key=lambda n: n.ts)
            return [n.version for n in ordered]
