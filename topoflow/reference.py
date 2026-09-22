"""全量重算的参考实现，引擎的结果以它为准。

同一时刻有多个节点可以出队时，先出加入序号小的那个，
这条规则让每张图只对应一份拓扑序。测试和核对脚本拿它对拍。
"""

import heapq


class CycleError(Exception):
    """图里有环，排不出拓扑序。"""


def seq_map(graph):
    """节点加入序号，越小越先出队。"""
    return {node: index for index, node in enumerate(graph.nodes())}


def reference_order(graph):
    """从头算一份拓扑序；有环抛 CycleError。"""
    seq = seq_map(graph)
    indeg = {node: graph.in_degree(node) for node in seq}
    ready = [(seq[node], node) for node in seq if indeg[node] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, node = heapq.heappop(ready)
        order.append(node)
        for succ in graph.successors(node):
            indeg[succ] -= 1
            if indeg[succ] == 0:
                heapq.heappush(ready, (seq[succ], succ))
    if len(order) != len(seq):
        raise CycleError("图中存在环，排不出拓扑序")
    return order


def reference_is_acyclic(graph):
    """从头判一遍有没有环。"""
    try:
        reference_order(graph)
    except CycleError:
        return False
    return True


def order_problems(graph, order):
    """核对一份拓扑序，返回问题描述列表，没问题就是空表。"""
    problems = []
    pos = {}
    for index, node in enumerate(order):
        if node in pos:
            problems.append("节点 %r 在序里出现了多次" % (node,))
        pos[node] = index
    for node in graph.nodes():
        if node not in pos:
            problems.append("节点 %r 不在序里" % (node,))
    for u, v in graph.edges():
        if u in pos and v in pos and pos[u] >= pos[v]:
            problems.append("边 %r -> %r 的次序反了" % (u, v))
    return problems
