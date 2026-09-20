"""对象快照链。

每个对象维护一条按版本号记录的状态链：snapshot() 追加一版，
at() 回读某一版，latest() 取当前版本，history() 列出全部版本，
ancestors() 从任意版本沿链一路回走到最早一版。
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
        self._tail = {}       # obj_id -> 链上现存最早的一版
        self._head = {}       # obj_id -> 链上现存最晚的一版
        self._cursor = {}     # obj_id -> 当前版本，rollback 会挪动它
        self._issued = {}     # obj_id -> 已发放过的最大版本号，只增不减

    # -- 写入 ------------------------------------------------------------

    def snapshot(self, obj_id, state):
        """记一版快照，返回分配到的版本号。"""
        with self._lock:
            # 序号、版本号、时刻在锁内一次性确定：并发提交不重号，
            # 同一时刻的版本也能按提交先后稳定排序。
            self._seq += 1
            seq = self._seq
            ts = self._clock()
            # 版本号只从“历史上发过的最大值”往后发；rollback/delete
            # 挪动的只是当前游标，不会让号段回退去占用旧号。
            version = self._issued.get(obj_id, 0) + 1
            self._issued[obj_id] = version
            nodes = self._nodes.setdefault(obj_id, {})
            node = _Node(version, seq, ts, state)
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
        """把对象的当前版本指回链上已有的某一版。"""
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            node = nodes.get(version)
            if node is None:
                raise KeyError(version)
            # 只挪动当前游标：链结构、版本号、已发号段都不动。
            self._cursor[obj_id] = node

    def delete(self, obj_id, version):
        """从链上删掉某一版，返回是否真的删掉了。"""
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            node = nodes.get(version)
            if node is None:
                return False
            prev_node, next_node = node.prev, node.next
            # 双向摘链：两边的指针都要补，链才不会断在缺口处。
            if prev_node is None:
                self._tail[obj_id] = next_node
            else:
                prev_node.next = next_node
            if next_node is None:
                self._head[obj_id] = prev_node
            else:
                next_node.prev = prev_node
            node.prev = None
            node.next = None
            del nodes[version]
            if self._cursor.get(obj_id) is node:
                self._cursor[obj_id] = (
                    prev_node if prev_node is not None else next_node
                )
            return True

    # -- 读取 ------------------------------------------------------------

    def at(self, obj_id, version):
        """回读该对象指定版本的状态，版本不存在返回 None。"""
        with self._lock:
            node = self._nodes.get(obj_id, {}).get(version)
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

        先比时刻，时刻相同再比全局提交序号，因此同一毫秒内的版本
        严格按提交先后排列，不随 dict 插入顺序或 rollback 漂移。
        """
        with self._lock:
            nodes = self._nodes.get(obj_id, {})
            ordered = sorted(nodes.values(), key=lambda n: (n.ts, n.seq))
            return [n.version for n in ordered]

    def ancestors(self, obj_id, version):
        """从指定版本沿 prev 一路回走到最早一版，返回版本号列表。

        起点版本排在最前，最早版本排在最后；版本不存在抛 KeyError。
        中间版本被删除后，剩余节点的 prev 会直接跨过缺口，所以从
        任意现存版本往回走都能走到底、不重不漏。
        """
        with self._lock:
            node = self._nodes.get(obj_id, {}).get(version)
            if node is None:
                raise KeyError(version)
            versions = []
            while node is not None:
                versions.append(node.version)
                node = node.prev
            return versions
