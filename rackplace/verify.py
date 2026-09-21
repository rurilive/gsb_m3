"""布局体检：把 Placement 和拓扑对一遍，把毛病列出来。"""


def check(placement, topology, replicas=None):
    """逐分区核对，返回问题描述列表；空列表代表干净。

    眼下只认三件事：副本数对不对、节点还在不在、同一分区有没有
    两个副本落在同一个节点上。
    """
    problems = []
    for partition in placement.partitions():
        owners = placement.owners(partition)
        if replicas is not None and len(owners) != replicas:
            problems.append("分区 %s 有 %d 个副本，该有 %d 个" % (
                partition, len(owners), replicas))
        if len(set(owners)) != len(owners):
            problems.append("分区 %s 有两个副本挤在同一节点" % (partition,))
        for node_id in owners:
            if not topology.has_node(node_id):
                problems.append("分区 %s 的副本落在不存在的节点 %s 上" % (
                    partition, node_id))
    return problems


def summary(placement, topology):
    """布局概览：每节点负载，加上最重和最轻的节点。"""
    loads = placement.node_loads()
    for node_id in topology.node_ids():
        loads.setdefault(node_id, 0)
    if placement.replica_total():
        heaviest = max(sorted(loads), key=lambda node_id: loads[node_id])
        lightest = min(sorted(loads), key=lambda node_id: loads[node_id])
    else:
        heaviest = lightest = None
    return {
        "loads": loads,
        "heaviest": heaviest,
        "lightest": lightest,
        "max_load": loads[heaviest] if heaviest is not None else 0,
        "min_load": loads[lightest] if lightest is not None else 0,
    }
