"""对象快照链。

每个对象维护一条按版本号记录的状态链：snapshot() 追加一版，
at() 回读某一版，latest() 取当前版本，history() 列出全部版本。
时间由注入的 clock 提供，默认 time.monotonic，测试可替换。

版本号在锁内按对象分别从高水位递增发放，任何情况下（并发、回滚）
都不会重复或回退。链本身严格按提交先后双向链接（新写的版本永远挂在
物理链尾），history() 直接沿链走，因此同一毫秒、甚至时钟回跳都不会
打乱顺序，也不依赖时间戳做排序。clock 刻意在锁外调用，避免注入的
时钟回调和本对象的锁互相等待（例如演示里用来对齐并发线程的屏障）。
delete() 双向摘链，删掉任意中间节点后，剩下的节点仍能从头走到尾、
从尾走到底，不重不漏。
"""

import threading
import time


class _Node:
    """链上的一版快照。"""

    __slots__ = ("version", "ts", "state", "prev", "next")

    def __init__(self, version, ts, state):
        self.version = version
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
        self._nodes = {}      # obj_id -> {version: _Node}
        self._tail = {}       # obj_id -> 链上最早的一版
        self._head = {}       # obj_id -> 物理上最后写入的一版
        self._cursor = {}     # obj_id -> 当前版本，rollback 会挪动它
        self._issued = {}     # obj_id -> 已经发放过的最大版本号

    # -- 写入 ------------------------------------------------------------

    def snapshot(self, obj_id, state):
        """记一版快照，返回分配到的版本号。

        版本号取自该对象历史发放过的最大号 + 1，与当前游标（可能因
        rollback 指向旧版本）无关，因此回滚后再写绝不会复用旧号。
        发号和挂链都在同一把锁内完成，两个线程并发写同一对象时必然
        拿到两个不同的、严格递增的版本号，且两版都会留在链上。
        """
        ts = self._clock()
        with self._lock:
            version = self._issued.get(obj_id, 0) + 1
            self._issued[obj_id] = version

            node = _Node(version, ts, state)
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
        return version

    def rollback(self, obj_id, version):
        """把对象的当前版本指回链上已有的某一版。

        只移动游标，不动版本号高水位：之后 snapshot() 仍从历史最大号
        往后发号，历史版本原封不动。
        """
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            node = nodes.get(version)
            if node is None:
                raise KeyError(version)
            self._cursor[obj_id] = node

    def delete(self, obj_id, version):
        """从链上删掉某一版，返回是否真的删掉了。

        双向摘除：同时缝好两侧节点的 prev/next，所以删掉中间版本后，
        比它旧和比它新的版本仍然在同一条完整链上，回读与遍历都不断。
        若删掉的正是当前游标，游标退到它的前一版（没有则为后一版）。
        """
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
            else:
                next_node.prev = prev_node
            # 摘掉自身，避免残留引用
            node.prev = None
            node.next = None
            del nodes[version]
            if self._cursor.get(obj_id) is node:
                self._cursor[obj_id] = prev_node or next_node
            return True

    # -- 读取 ------------------------------------------------------------

    def at(self, obj_id, version):
        """回读该对象指定版本的状态，版本不存在返回 None。"""
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            node = nodes.get(version)
            if node is None:
                return None
            return node.state

    def latest(self, obj_id):
        """取当前版本，返回 (version, state)；对象不存在返回 None。"""
        with self._lock:
            node = self._cursor.get(obj_id)
            if node is None:
                return None
            return (node.version, node.state)

    def history(self, obj_id):
        """按提交先后列出该对象的全部版本号，旧的在前。

        直接沿双向链从最早一版走到最新一版：物理链接顺序就是提交
        顺序，与时间戳无关，所以同一毫秒连续提交、甚至时钟抖动都不
        会让结果漂移；删除中间版本后走出来的也恰好是剩余版本，
        不重不漏。
        """
        with self._lock:
            versions = []
            node = self._tail.get(obj_id)
            while node is not None:
                versions.append(node.version)
                node = node.next
            return versions
