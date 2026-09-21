"""对拍用的朴素参考实现：先按 trace_id 分组，再照 parent_id 挂树。

故意写成和 spanweave 正式实现完全不同的路子（递归、线性扫描、
每次重新判链），只在小规模乱序输入上当正确性标尺：怎么喂都该和
它的结果一致。
"""

from spanweave.model import Span


class RNode:
    __slots__ = ("span", "children")

    def __init__(self, span):
        self.span = span
        self.children = []


class RTree:
    __slots__ = ("trace_id", "roots", "unresolved")

    def __init__(self, trace_id, roots, unresolved):
        self.trace_id = trace_id
        self.roots = roots
        self.unresolved = unresolved


def _duration(span):
    return max(0, span.end_ms - span.start_ms)


def _order_key(node):
    return (node.span.start_ms, node.span.span_id)


def _reaches_root(by_id, node, seen):
    """沿 parent 链递归走：能走到 parent_id 为空的 span 才算挂得上。"""
    span = node.span
    if span.span_id in seen:
        return False
    if span.parent_id is None:
        return True
    parent = by_id.get(span.parent_id)
    if parent is None or parent.span.trace_id != span.trace_id:
        return False
    return _reaches_root(by_id, parent, seen | {span.span_id})


def _build_tree(trace_id, spans):
    by_id = {span.span_id: RNode(span) for span in spans}
    unresolved = [node for node in by_id.values()
                  if not _reaches_root(by_id, node, frozenset())]
    unresolved_ids = {node.span.span_id for node in unresolved}
    roots = []
    for node in by_id.values():
        if node.span.span_id in unresolved_ids:
            continue
        if node.span.parent_id is None:
            roots.append(node)
        else:
            by_id[node.span.parent_id].children.append(node)
    roots.sort(key=_order_key)
    unresolved.sort(key=_order_key)
    for node in by_id.values():
        node.children.sort(key=_order_key)
    return RTree(trace_id, roots, unresolved)


def reference_build(records):
    """吃 dict 记录（可含重传），返回按 trace_id 排序的 RTree 列表。"""
    first = {}
    for record in records:
        span = Span.from_record(record)
        if span.span_id not in first:
            first[span.span_id] = span
    grouped = {}
    for span in first.values():
        grouped.setdefault(span.trace_id, []).append(span)
    return [_build_tree(trace_id, grouped[trace_id])
            for trace_id in sorted(grouped)]


def _shape(node):
    return (node.span.span_id, [_shape(child) for child in node.children])


def canonical(trees):
    """任意一边的 Tree 列表都能摊成可直接判等的朴素结构。"""
    out = []
    for tree in trees:
        out.append({
            "trace_id": tree.trace_id,
            "roots": [_shape(root) for root in tree.roots],
            "unresolved": [node.span.span_id for node in tree.unresolved],
        })
    return out


def _render(node, depth, lines):
    lines.append("%s%s (%dms)" % ("  " * depth, node.span.name,
                                  _duration(node.span)))
    for child in node.children:
        _render(child, depth + 1, lines)


def reference_render(tree):
    lines = []
    for root in tree.roots:
        _render(root, 0, lines)
    return "\n".join(lines)


def _snapshot(node, depth, lines):
    span = node.span
    lines.append("%s%s %s %dms" % ("  " * depth, span.span_id,
                                   span.service or "-", _duration(span)))
    for child in node.children:
        _snapshot(child, depth + 1, lines)


def reference_snapshot(tree):
    lines = ["trace %s" % tree.trace_id]
    for root in tree.roots:
        _snapshot(root, 0, lines)
    return "\n".join(lines)


def _count(node, depth, stats):
    stats["spans"] += 1
    stats["total_ms"] += _duration(node.span)
    stats["max_depth"] = max(stats["max_depth"], depth)
    if node.span.end_ms < node.span.start_ms:
        stats["clock_skew"] += 1
    for child in node.children:
        _count(child, depth + 1, stats)


def reference_summary(tree):
    stats = {"spans": 0, "total_ms": 0, "max_depth": 0,
             "clock_skew": 0}
    for root in tree.roots:
        _count(root, 0, stats)
    for node in tree.unresolved:
        if node.span.end_ms < node.span.start_ms:
            stats["clock_skew"] += 1
    return {
        "spans": stats["spans"],
        "roots": len(tree.roots),
        "unresolved": len(tree.unresolved),
        "clock_skew": stats["clock_skew"],
        "total_ms": stats["total_ms"],
        "max_depth": stats["max_depth"],
    }


def _best(node):
    """返回 (最大耗时和, 对应 span_id 链)，并列取字典序最小的链。"""
    duration = _duration(node.span)
    best_total = duration
    best_ids = [node.span.span_id]
    for child in node.children:
        child_total, child_ids = _best(child)
        if child_total <= 0:
            continue
        total = duration + child_total
        ids = [node.span.span_id] + child_ids
        if total > best_total or (total == best_total and ids < best_ids):
            best_total = total
            best_ids = ids
    return best_total, best_ids


def reference_critical_path(tree):
    candidates = [_best(root) for root in tree.roots]
    if not candidates:
        return []
    best_total, best_ids = candidates[0]
    for total, ids in candidates[1:]:
        if total > best_total or (total == best_total and ids < best_ids):
            best_total = total
            best_ids = ids
    return best_ids
