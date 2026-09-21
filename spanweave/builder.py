"""把同一 trace 的 span 挂成调用树。

树由 Node 组成，每个 Node 包一条 span 和它的直接子 span。一个 trace 可以
有多个根（一条链路被拆到多个进程上报、丢了 parent_id 时就会出现），
Tree.roots 是这些根；父 span 始终没有出现、或处在父子环里的 span 挂在
Tree.unresolved 上（作为入口节点，带着各自能挂上的子树），一条都不丢，
也绝不让环进入树里。

重建结果只取决于 span 内容本身：兄弟和根统一按 (start_ms, span_id)
排序，因此同一份数据无论以什么到达顺序喂进来，结果逐字节一致。
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

    def __init__(self, trace_id, roots, unresolved=None):
        self.trace_id = trace_id
        self.roots = roots
        self.unresolved = unresolved if unresolved is not None else []


_ORDER_KEY = lambda node: (node.span.start_ms, node.span.span_id)


def _classify(node_by_id):
    """把每个节点分到 'root'、'linked' 或 'unresolved'。

    没有 parent_id 的是 'root'；parent_id 在本 trace 里找不到（父始终
    没到，或指向别的 trace）以及处在父子环上的节点归 'unresolved'，
    切断父链；其余节点都是 'linked'，正常挂到直接父节点上——即使父是
    unresolved 入口（比如指向环入口的引子、缺父节点的子节点），也作为
    该入口子树的一员保留。环上每个节点都切链，保证挂出来的结构是树的
    森林，绝不成环。

    沿 parent 链走路并记忆结果找出所有环节点，再按上面的规则定类。
    全程迭代式，几千层深链也不会撑爆递归栈。
    """
    kinds = {}
    on_cycle = {}          # node -> True 在环上 / False 不在，记忆化每条链
    for first_node in node_by_id.values():
        if first_node in on_cycle:
            continue
        path = []
        seen_at = {}
        cursor = first_node
        hit_cycle = False
        while (cursor is not None
               and cursor.span.span_id in node_by_id
               and cursor not in on_cycle):
            if cursor in seen_at:
                # 撞到本次足迹：从落点到链尾是环，落点之前是引子
                cut = seen_at[cursor]
                for cyclic_node in path[cut:]:
                    on_cycle[cyclic_node] = True
                for feeder_node in path[:cut]:
                    on_cycle[feeder_node] = False
                hit_cycle = True
                break
            seen_at[cursor] = len(path)
            path.append(cursor)
            parent_id = cursor.span.parent_id
            cursor = node_by_id.get(parent_id) if parent_id is not None else None
        if not hit_cycle:
            # 走到根、缺失父或已定论节点：链上引子都不在环上
            for feeder_node in path:
                on_cycle[feeder_node] = False

    for target in node_by_id.values():
        target_parent_id = target.span.parent_id
        if target_parent_id is None:
            kinds[target] = "root"
        elif on_cycle[target] or target_parent_id not in node_by_id:
            kinds[target] = "unresolved"
        else:
            kinds[target] = "linked"
    return kinds


def build_tree(trace_id, spans):
    """把一条 trace 的 span 挂成 Tree。"""
    nodes = [Node(span) for span in spans]
    node_by_id = {node.span.span_id: node for node in nodes}
    kinds = _classify(node_by_id)

    roots = []
    unresolved = []
    for node in nodes:
        kind = kinds[node]
        if kind == "root":
            roots.append(node)
        elif kind == "unresolved":
            unresolved.append(node)
        else:
            node_by_id[node.span.parent_id].children.append(node)

    roots.sort(key=_ORDER_KEY)
    unresolved.sort(key=_ORDER_KEY)
    for node in nodes:
        node.children.sort(key=_ORDER_KEY)

    return Tree(trace_id, roots, unresolved)


def build_trees(by_trace):
    """trace_id -> [Span] 的映射建成 Tree 列表，trace 按 trace_id 排序。"""
    return [build_tree(trace_id, by_trace[trace_id])
            for trace_id in sorted(by_trace)]
