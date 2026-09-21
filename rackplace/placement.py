"""放置结果的不可变快照，以及基线用的平铺轮询分配。

Placement 就是"分区 -> 副本节点列表"的一张表。每个副本背后是实打实
的一份数据，挪副本要拷盘，所以两份布局之间能比出"迁移了多少"。
"""

from collections import Counter


class PlacementError(ValueError):
    """放置结果不合法：分区重复、副本数不对、节点不够放。"""


class Placement:
    """分区到副本节点的映射，构造完就不许改了。"""

    def __init__(self, assignments):
        self._owners = {}
        for partition, node_ids in assignments.items():
            owners = tuple(node_ids)
            if not owners:
                raise PlacementError("分区 %s 一个副本都没有" % (partition,))
            self._owners[partition] = owners

    def owners(self, partition):
        """一个分区的副本节点，顺序跟放置时一致。"""
        try:
            return self._owners[partition]
        except KeyError:
            raise PlacementError("分区不在布局里：%s" % (partition,))

    def get(self, partition, default=None):
        return self._owners.get(partition, default)

    def partitions(self):
        """全部分区 ID，从小到大。"""
        return tuple(sorted(self._owners))

    def size(self):
        return len(self._owners)

    def replica_total(self):
        return sum(len(owners) for owners in self._owners.values())

    def node_loads(self):
        """节点 -> 扛的副本数。"""
        loads = Counter()
        for owners in self._owners.values():
            loads.update(owners)
        return dict(loads)

    def as_dict(self):
        return {partition: list(owners) for partition, owners in self._owners.items()}

    def __eq__(self, other):
        if not isinstance(other, Placement):
            return NotImplemented
        return self._owners == other._owners

    def __repr__(self):
        return "Placement(%d 个分区)" % len(self._owners)


def round_robin(topology, partitions, replicas):
    """基线分配：节点列表平铺成一条长带子，按顺序切给每个分区。

    每个分区拿连续的一段；节点列表里机架怎么排、副本就跟着怎么排。
    """
    node_ids = topology.node_ids()
    if not node_ids:
        raise PlacementError("集群里一个节点都没有")
    replicas = int(replicas)
    if replicas < 1:
        raise PlacementError("副本数至少为 1")
    if replicas > len(node_ids):
        raise PlacementError(
            "副本数 %d 超过节点数 %d，放不下" % (replicas, len(node_ids)))
    count = len(node_ids)
    assignments = {}
    for index, partition in enumerate(partitions):
        if partition in assignments:
            raise PlacementError("分区重复：%s" % (partition,))
        base = (index * replicas) % count
        assignments[partition] = [
            node_ids[(base + step) % count] for step in range(replicas)
        ]
    return Placement(assignments)


def migration_count(before, after):
    """两份布局之间，副本集合变了的那些分区数。

    只换副本顺序不算迁移，数据没挪窝；after 里新冒出来的分区也记一笔。
    """
    moved = 0
    for partition in after.partitions():
        old = before.get(partition)
        new_owners = sorted(after.owners(partition))
        if old is None or sorted(old) != new_owners:
            moved += 1
    return moved
