"""rackplace 现状演示：机房改造前，先看看平铺轮询排出来的样子。

第一段：两架六节点上放 12 个分区，副本都落到哪了。
第二段：扩一架、摘一个节点，看迁移量和负载变化。
"""

from collections import Counter

from rackplace import (
    ClusterTopology,
    PlacementManager,
    check,
    migration_count,
    summary,
)

PARTITIONS = list(range(12))
REPLICAS = 3


def build_topology():
    topo = ClusterTopology()
    for rack in ("az1-r1", "az1-r2"):
        for slot in (1, 2, 3):
            topo.add_node("%s-n%d" % (rack, slot), rack)
    return topo


def same_rack_profile(placement, topology):
    """每个分区里单架最多压了几个副本。"""
    profile = {}
    for partition in placement.partitions():
        per_rack = {}
        for node_id in placement.owners(partition):
            rack = topology.rack_of(node_id)
            per_rack[rack] = per_rack.get(rack, 0) + 1
        profile[partition] = max(per_rack.values())
    return profile


def report(plan, topology, tag):
    profile = same_rack_profile(plan, topology)
    stats = summary(plan, topology)
    print("%s %d 个分区：每节点负载从 %d 到 %d" % (
        tag, plan.size(), stats["min_load"], stats["max_load"]))
    print("  单架副本数的分布：%s" % dict(sorted(Counter(profile.values()).items())))
    print("  check 报出 %d 条问题" % len(check(plan, topology, replicas=REPLICAS)))


def main():
    topo = build_topology()
    manager = PlacementManager(topo, PARTITIONS, replicas=REPLICAS, seed=42)

    print("=== 初始布局：%d 节点，%d 个机架 ===" % (len(topo), len(topo.racks())))
    plan = manager.rebalance()
    print("  分区 0 的副本：%s" % (plan.owners(0),))
    report(plan, topo, "初始")

    print("=== 扩容：az2-r3 新架子上两台，追加到节点列表尾部 ===")
    manager.add_node("az2-r3-n1", "az2-r3")
    plan2 = manager.add_node("az2-r3-n2", "az2-r3")
    print("  迁移分区 %d / %d" % (migration_count(plan, plan2), plan2.size()))
    report(plan2, topo, "扩容后")

    print("=== 摘掉失联节点 az1-r1-n1 ===")
    plan3 = manager.remove_node("az1-r1-n1")
    print("  迁移分区 %d / %d" % (migration_count(plan2, plan3), plan3.size()))
    report(plan3, topo, "摘除后")

    print("=== 分区 0 的副本轨迹 ===")
    for tag, snapshot in (("初始", plan), ("扩容", plan2), ("摘除", plan3)):
        print("  %s：%s" % (tag, snapshot.owners(0)))


if __name__ == "__main__":
    main()
