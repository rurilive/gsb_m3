"""集中式的真实存活时间线，对拍时的上帝视角基准。"""


class TrueSchedule:
    """每个节点真实的上下线时刻。

    不看心跳、不看网络，节点在 crash 之后、restart 之前就是死的。
    集群里的节点只能靠消息猜，猜出来的视图最终要和这份时间线对上。
    """

    def __init__(self, node_ids, alive_from=0.0):
        ids = sorted(set(node_ids))
        if not ids:
            raise ValueError("schedule needs at least one node")
        self.node_ids = tuple(ids)
        self._intervals = {nid: [(float(alive_from), True)] for nid in self.node_ids}

    def is_alive(self, node_id, at):
        """节点在某个时刻是否活着。"""
        if node_id not in self._intervals:
            raise KeyError(f"unknown node: {node_id!r}")
        alive = False
        for when, up in self._intervals[node_id]:
            if when <= at:
                alive = up
            else:
                break
        return alive

    def alive_at(self, at):
        """某个时刻真实活着的节点集合。"""
        return frozenset(nid for nid in self.node_ids if self.is_alive(nid, at))

    def crash(self, node_id, at):
        """记一次崩溃，节点此刻必须还活着。"""
        if not self.is_alive(node_id, at):
            raise ValueError(f"{node_id} is already down at {at}")
        self._intervals[node_id].append((float(at), False))

    def restart(self, node_id, at):
        """记一次重启，节点此刻必须已经崩了。"""
        if self.is_alive(node_id, at):
            raise ValueError(f"{node_id} is still alive at {at}")
        self._intervals[node_id].append((float(at), True))

    def last_event_at(self):
        """最后一次上下线变化的时刻。"""
        return max(interval[-1][0] for interval in self._intervals.values())

    def __repr__(self):
        return f"TrueSchedule({list(self.node_ids)!r})"
