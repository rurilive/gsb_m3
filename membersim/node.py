"""节点：持有成员表，通过注入的网络收发消息。"""

from membersim.member import MembershipTable


class Node:
    """模拟集群里的一个节点。

    查询接口是 view 和 alive_members，手工上下线走 mark_up、mark_down。
    每个周期 Cluster 会调一次 on_period，收到消息时调 on_message；
    目前的 on_period 没有周期任务，on_message 只认整表快照 "table"。
    """

    def __init__(self, node_id, clock, network, node_ids):
        self.node_id = node_id
        self.clock = clock
        self.network = network
        self.periods = 0
        self.table = MembershipTable(node_ids)

    # ---- 查询 ----

    def view(self):
        """本地看到的整张成员表，{节点: 状态} 的副本。"""
        return self.table.snapshot()

    def alive_members(self):
        """本地认为在线的成员。"""
        return self.table.alive_members()

    def status_of(self, node_id):
        """本地认为的某个成员状态。"""
        return self.table.status_of(node_id)

    # ---- 手工标记 ----

    def mark_up(self, node_id):
        """手工把成员标回在线。"""
        self.table.mark_up(node_id)

    def mark_down(self, node_id):
        """手工把成员标成下线。"""
        self.table.mark_down(node_id)

    # ---- 收发 ----

    def send_to(self, peer_id, payload):
        """给某个邻居发一条消息，返回是否真的进了网络。"""
        return self.network.send(self.node_id, peer_id, payload)

    def announce(self, peer_id):
        """把整张表塞给一个邻居，整表同步的临时做法。"""
        return self.send_to(peer_id, ("table", self.table.snapshot()))

    def on_period(self, period):
        """每个周期开始时被调一次，目前的周期任务为空。"""
        self.periods += 1

    def on_message(self, src, payload):
        """收到一条消息，目前只处理整表快照。"""
        kind, data = payload
        if kind == "table":
            self.table.merge_snapshot(data)
