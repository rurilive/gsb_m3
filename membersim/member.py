"""成员表：每个节点本地维护的一份成员视图。"""

ALIVE = "alive"
DEAD = "dead"


class MembershipTable:
    """节点本地的成员表，每个成员一条记录，初始都在线。

    状态现在只有 alive 和 dead 两种，整表同步用 merge_snapshot，
    按到达顺序覆盖，后到的赢。
    """

    def __init__(self, node_ids):
        entries = {}
        for node_id in node_ids:
            if node_id in entries:
                raise ValueError(f"duplicate member: {node_id!r}")
            entries[node_id] = ALIVE
        self._entries = entries

    def status_of(self, node_id):
        """成员的当前状态，不认识的成员抛 KeyError。"""
        if node_id not in self._entries:
            raise KeyError(f"unknown member: {node_id!r}")
        return self._entries[node_id]

    def members(self, status=None):
        """状态匹配的成员，按名字排序；status 为 None 时返回全部。"""
        if status is None:
            return tuple(sorted(self._entries))
        return tuple(sorted(nid for nid, st in self._entries.items() if st == status))

    def alive_members(self):
        """当前在线的成员。"""
        return self.members(ALIVE)

    def mark_up(self, node_id):
        """把成员标回在线。"""
        self.status_of(node_id)
        self._entries[node_id] = ALIVE

    def mark_down(self, node_id):
        """把成员标成下线。"""
        self.status_of(node_id)
        self._entries[node_id] = DEAD

    def snapshot(self):
        """整表快照的副本，改它不影响表本身。"""
        return dict(self._entries)

    def merge_snapshot(self, snapshot):
        """并入一份快照，表里没有的成员忽略。"""
        for node_id, status in snapshot.items():
            if node_id in self._entries:
                self._entries[node_id] = status

    def __repr__(self):
        return f"MembershipTable({self._entries!r})"
