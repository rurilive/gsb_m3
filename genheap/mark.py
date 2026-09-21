"""标记阶段的遍历原语。

只认一件事：从一组根出发、顺着槽位能走到的对象集合。
不关心回收策略，也不认识堆的其它状态，后续换回收策略时
这层可以照用。
"""


def trace(cells, roots):
    """从 roots 出发迭代标记。

    cells 是 oid 到 Cell 的映射，roots 是起始 oid 集合。
    返回 (marked, scanned)：marked 是可达 oid 集合，scanned 是
    本轮实际访问过的对象个数，同一个对象最多算一次。

    根里指向已不在 cells 里的条目直接跳过，不报错。
    """
    marked = set()
    stack = []
    for oid in roots:
        if oid in cells and oid not in marked:
            marked.add(oid)
            stack.append(oid)
    scanned = 0
    while stack:
        oid = stack.pop()
        scanned += 1
        for dst in cells[oid].refs.values():
            if dst in cells and dst not in marked:
                marked.add(dst)
                stack.append(dst)
    return marked, scanned


def unmarked(cells, marked):
    """没被标记到的对象，按 oid 升序给出。

    回收和回调都按这个顺序走，保证同一批垃圾的回收顺序稳定。
    """
    return [oid for oid in sorted(cells) if oid not in marked]
