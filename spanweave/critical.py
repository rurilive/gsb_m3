"""关键路径：根到叶耗时之和最大的那条链。

耗时已经在 Span.duration_ms 里钳到非负（时钟回拨按 0 计），负数不会
再把关键路径带歪。实现用自底向上的迭代 DP，几千层的深链也不会撞
递归深度限制。
"""


def critical_path(tree):
    """整棵树的关键路径，返回从根到叶的 span_id 列表。

    并列时取 span_id 序列字典序最小的那条；空树返回空列表。
    """
    if not tree.roots:
        return []

    # 先序收集全部节点，反向遍历即自底向上。每个节点只记两件事：
    # best_total —— 以它打头的链的最大总耗时；
    # best_child —— 该链选中的直接子节点（没选就是 None）。
    ordered = []
    stack = list(reversed(tree.roots))
    while stack:
        node = stack.pop()
        ordered.append(node)
        stack.extend(reversed(node.children))

    best_total = {}
    best_child = {}
    for node in reversed(ordered):
        duration = node.span.duration_ms
        chosen = None
        chosen_total = 0
        for child in node.children:
            subtotal = best_total[child]
            if subtotal <= 0:
                continue
            # 并列时取 span_id 序列字典序最小的链：同代兄弟 span_id
            # 互不相同，比候选链的下一个元素（子节点 span_id）即可。
            if (chosen is None or subtotal > chosen_total or
                    (subtotal == chosen_total and
                     child.span.span_id < chosen.span.span_id)):
                chosen = child
                chosen_total = subtotal
        best_child[node] = chosen
        best_total[node] = duration + chosen_total

    root = None
    for candidate in tree.roots:
        if (root is None or best_total[candidate] > best_total[root] or
                (best_total[candidate] == best_total[root] and
                 candidate.span.span_id < root.span.span_id)):
            root = candidate

    ids = []
    node = root
    while node is not None:
        ids.append(node.span.span_id)
        node = best_child[node]
    return ids
