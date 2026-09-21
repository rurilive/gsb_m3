"""只读的图遍历辅助，demo 与排查用。"""


def reachable(store, roots):
    """从 roots 出发沿强引用能走到的活对象集合，含 roots 自己。

    迭代实现，带 visited 去重，环和深链都不会打转。
    roots 里已经不活的对象直接跳过。
    """
    seen = set()
    stack = [oid for oid in roots if store.alive(oid)]
    while stack:
        oid = stack.pop()
        if oid in seen:
            continue
        seen.add(oid)
        for dst in store.out_links(oid):
            if dst not in seen:
                stack.append(dst)
    return seen


def layers(store, roots):
    """按到 roots 的最短跳数分层，第 0 层就是 roots 自己。

    返回 [[第 0 层], [第 1 层], ...]，层内按遍历到的先后排。
    """
    seen = set()
    level = []
    for oid in roots:
        if store.alive(oid) and oid not in seen:
            seen.add(oid)
            level.append(oid)
    out = []
    while level:
        out.append(level)
        nxt = []
        for oid in level:
            for dst in store.out_links(oid):
                if dst not in seen:
                    seen.add(dst)
                    nxt.append(dst)
        level = nxt
    return out
