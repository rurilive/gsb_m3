"""把同一 trace 的 span 挂成调用树。

树由 Node 组成，每个 Node 包一条 span 和它的直接子 span。一个 trace 可以
有多个根（一条链路被拆到多个进程上报时会出现），Tree.roots 是这一层的入口；
父 span 始终没有出现的那些 span 挂在 Tree.unresolved 上。
"""


class Node:
    """树上的一段：一条 span 加上它的直接子 span。"""

    __slots__ = ("span", "children")

    def __init__(self, span):
        self.span = span
        self.children = []

    def __repr__(self):
        return "Node(%s)" % self.span.span_id


class Tree:
    """一条 trace 重建出来的调用树。"""

    def __init__(self, trace_id, roots, unresolved):
        self.trace_id = trace_id
        self.roots = roots
        self.unresolved = unresolved


def _order_key(node):
    """兄弟/根/未决 span 的统一排序键：先按开始时间，再按 span_id。"""
    return (node.span.start_ms, node.span.span_id)


def _reaches_root(nodes, state, start):
    """沿 parent_id 向上走，判断 start 能不能挂到一个根上。

    走到 parent_id 为空的 span 才算成功；父缺失（跨 trace 同样查不到）、
    指向自身或成环都算失败。结果记忆在 state 里，每个 Node 至多走一遍。
    """
    path = []
    on_path = set()
    current = start
    verdict = None
    while current is not None:
        if current in state:
            verdict = state[current]
            break
        if current in on_path:
            verdict = False
            break
        path.append(current)
        on_path.add(current)
        parent_id = current.span.parent_id
        if parent_id is None:
            current = None
            verdict = True
        else:
            current = nodes.get(parent_id)
            if current is None:
                verdict = False
    for node in path:
        state[node] = verdict
    return verdict


def build_tree(trace_id, spans):
    """把一条 trace 的 span 挂成 Tree。"""
    nodes = {span.span_id: Node(span) for span in spans}

    state = {}  # Node -> True（能挂到根）/ False（父缺失或成环）
    roots = []
    unresolved = []
    for node in nodes.values():
        if _reaches_root(nodes, state, node):
            if node.span.parent_id is None:
                roots.append(node)
            else:
                nodes[node.span.parent_id].children.append(node)
        else:
            unresolved.append(node)

    roots.sort(key=_order_key)
    unresolved.sort(key=_order_key)
    for node in nodes.values():
        node.children.sort(key=_order_key)

    return Tree(trace_id, roots, unresolved)


def build_trees(by_trace):
    """trace_id -> [Span] 的映射建成 Tree 列表，trace 按 trace_id 排序。"""
    return [build_tree(trace_id, by_trace[trace_id])
            for trace_id in sorted(by_trace)]
