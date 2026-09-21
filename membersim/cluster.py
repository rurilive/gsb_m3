"""把节点、网络、时钟和一条真实存活时间线拼成一个能推进的簇。"""

from membersim.clock import SimClock
from membersim.network import InMemoryNetwork
from membersim.node import Node
from membersim.reference import TrueSchedule


class Cluster:
    """一圈本地节点加一张进程内网络。

    step 推进一个周期：先让活着的节点各跑一次周期任务，再投递到期的
    消息。崩掉的节点不跑任务，发给它的消息也直接扔掉，两件事都记在
    计数里。顺序固定，同一种子跑出来必然一模一样。
    """

    def __init__(self, node_ids, clock=None, network=None, schedule=None, period=1.0, rng=None):
        ids = sorted(set(node_ids))
        if not ids:
            raise ValueError("cluster needs at least one node")
        self.period = float(period)
        if self.period <= 0:
            raise ValueError("period must be positive")
        self.clock = clock if clock is not None else SimClock()
        self.network = network if network is not None else InMemoryNetwork(self.clock, rng=rng)
        self.schedule = schedule if schedule is not None else TrueSchedule(ids)
        self.nodes = {nid: Node(nid, self.clock, self.network, ids) for nid in ids}
        self.steps = 0
        self.dropped_to_down = 0

    def node(self, node_id):
        """按名字取节点。"""
        return self.nodes[node_id]

    def alive_nodes(self):
        """按真实时间线此刻还活着的节点，按名字排序。"""
        now = self.clock.now
        return tuple(nid for nid in sorted(self.nodes) if self.schedule.is_alive(nid, now))

    def step(self):
        """推进一个周期，返回推进后的时刻。"""
        now = self.clock.advance(self.period)
        for node_id in sorted(self.nodes):
            if self.schedule.is_alive(node_id, now):
                self.nodes[node_id].on_period(self.period)
        for msg in self.network.deliver_due():
            if self.schedule.is_alive(msg.dst, now):
                self.nodes[msg.dst].on_message(msg.src, msg.payload)
            else:
                self.dropped_to_down += 1
        self.steps += 1
        return now

    def run(self, periods):
        """连续推进若干个周期。"""
        for _ in range(periods):
            self.step()

    def views(self):
        """所有活着节点的视图，{节点: {成员: 状态}}。"""
        return {nid: self.nodes[nid].view() for nid in self.alive_nodes()}

    def views_agree(self):
        """活着的节点是不是拿着同一份视图。"""
        views = list(self.views().values())
        return all(view == views[0] for view in views[1:])
