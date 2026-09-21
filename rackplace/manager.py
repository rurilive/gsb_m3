"""放置管理器：拓扑、分区、当前布局捏在一起，节点增删后统一重排。"""

from .placement import PlacementError, round_robin


class PlacementManager:
    """管着一份布局的生命周期。

    构造时给拓扑、分区序列、副本数、随机种子；rebalance() 产出新布局
    并记住它，current() 拿最近一次的结果。还没排过时 current() 是 None。
    """

    def __init__(self, topology, partitions, replicas=3, seed=None):
        self._topology = topology
        self._partitions = tuple(partitions)
        if len(set(self._partitions)) != len(self._partitions):
            raise PlacementError("分区序列里有重复")
        self._replicas = int(replicas)
        if self._replicas < 1:
            raise PlacementError("副本数至少为 1")
        self._seed = seed
        self._current = None

    def topology(self):
        return self._topology

    def partitions(self):
        return self._partitions

    def replicas(self):
        return self._replicas

    def seed(self):
        return self._seed

    def current(self):
        """最近一次重排的布局；一次都没排过就是 None。"""
        return self._current

    def add_node(self, node_id, rack_id, weight=1.0):
        """上架一个新节点，然后重排，返回新布局。"""
        self._topology.add_node(node_id, rack_id, weight)
        return self.rebalance()

    def remove_node(self, node_id):
        """摘掉一个节点，然后重排，返回新布局。"""
        self._topology.remove_node(node_id)
        return self.rebalance()

    def rebalance(self):
        """重排全部分区。

        眼下是照着当前节点列表从零轮询一遍，不看旧布局的账：
        节点列表一动，几乎每个分区的归属都跟着挪。
        """
        plan = round_robin(self._topology, self._partitions, self._replicas)
        self._current = plan
        return plan
