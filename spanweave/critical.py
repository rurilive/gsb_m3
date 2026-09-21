"""关键路径：根到叶耗时之和最大的那条链。

用显式栈做后序遍历，几千层的深链也不会撑爆递归深度。
"""


def _pick(candidates):
    """总耗时最大、并列时 span_id 序列字典序最小的候选。"""
    total, ids = candidates[0]
    for candidate_total, candidate_ids in candidates[1:]:
        if candidate_total > total or (candidate_total == total
                                       and candidate_ids < ids):
            total, ids = candidate_total, candidate_ids
    return total, ids


def _best_paths(roots):
    """返回 {node: (总耗时, (span_id, ...))}，值是以该节点打头的最优根到叶链。

    关键路径是根到叶的链：叶子的候选只有自身；有子节点时候选是
    自身接上各子节点的最优链（不允许在 0 耗时的内节点处提前结束）。
    节点按后序处理，保证取用时子节点已经算好。
    """
    order = []
    seen = set()
    for root in roots:
        stack = [root]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            order.append(node)
            stack.extend(reversed(node.children))
    best = {}
    for node in reversed(order):
        span_id = node.span.span_id
        duration = node.span.duration_ms
        if node.children:
            candidates = []
            for child in node.children:
                child_total, child_ids = best[child]
                candidates.append((duration + child_total, (span_id,) + child_ids))
        else:
            candidates = [(duration, (span_id,))]
        best[node] = _pick(candidates)
    return best


def critical_path(tree):
    """整棵树的关键路径，返回从根到叶的 span_id 列表。

    并列时取 span_id 序列字典序最小的那条；空树返回空列表。
    """
    if not tree.roots:
        return []
    best = _best_paths(tree.roots)
    _, ids = _pick([best[root] for root in tree.roots])
    return list(ids)
