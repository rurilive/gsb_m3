"""机房拓扑：集群按机架分组，节点带权重。

放置器只认节点 ID，机架信息统一由这里提供。机架是故障域：一个机架
的电源或交换机挂了，架上的节点会一起下线。
"""


class TopologyError(ValueError):
    """拓扑操作不合法：节点重名、删不存在的节点、机架对不上号。"""


class Node:
    """一个存储节点：ID、所属机架、权重（越大越能装）。"""

    __slots__ = ("node_id", "rack_id", "weight")

    def __init__(self, node_id, rack_id, weight=1.0):
        if not isinstance(node_id, str) or not node_id:
            raise TopologyError("节点 ID 必须是非空字符串")
        if not isinstance(rack_id, str) or not rack_id:
            raise TopologyError("机架 ID 必须是非空字符串")
        weight = float(weight)
        if weight <= 0:
            raise TopologyError("权重必须为正：%r" % (weight,))
        self.node_id = node_id
        self.rack_id = rack_id
        self.weight = weight

    def __repr__(self):
        return "Node(%r, rack=%r, weight=%r)" % (
            self.node_id, self.rack_id, self.weight)


class ClusterTopology:
    """机架分组的节点集合。

    节点顺序按上架先后保留；架上的节点走光了，机架也跟着消失，
    不会留下空壳。
    """

    def __init__(self):
        self._nodes = {}
        self._racks = {}

    def add_node(self, node_id, rack_id, weight=1.0):
        """挂一个节点上架；重名直接报错。"""
        if node_id in self._nodes:
            raise TopologyError("节点已存在：%s" % node_id)
        node = Node(node_id, rack_id, weight)
        self._nodes[node_id] = node
        self._racks.setdefault(rack_id, []).append(node_id)
        return node

    def remove_node(self, node_id):
        """摘掉一个节点。"""
        node = self._nodes.pop(node_id, None)
        if node is None:
            raise TopologyError("节点不存在：%s" % node_id)
        peers = self._racks[node.rack_id]
        peers.remove(node_id)
        if not peers:
            del self._racks[node.rack_id]
        return node

    def has_node(self, node_id):
        return node_id in self._nodes

    def node(self, node_id):
        try:
            return self._nodes[node_id]
        except KeyError:
            raise TopologyError("节点不存在：%s" % node_id)

    def node_ids(self):
        """全部节点 ID，按上架先后排。"""
        return tuple(self._nodes)

    def racks(self):
        """全部机架 ID，字典序。"""
        return tuple(sorted(self._racks))

    def nodes_in_rack(self, rack_id):
        """一个机架上的节点，按上架先后排。"""
        try:
            return tuple(self._racks[rack_id])
        except KeyError:
            raise TopologyError("机架不存在：%s" % rack_id)

    def rack_of(self, node_id):
        return self.node(node_id).rack_id

    def weight(self, node_id):
        return self.node(node_id).weight

    def total_weight(self):
        return sum(node.weight for node in self._nodes.values())

    def __len__(self):
        return len(self._nodes)

    def __repr__(self):
        return "ClusterTopology(%d 架, %d 节点)" % (
            len(self._racks), len(self._nodes))
