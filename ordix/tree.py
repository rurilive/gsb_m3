"""单线程 B+ 树。

按最小度数 t 组织：非根节点最多 2t-1 个键、最少 t-1 个。键唯一，
put 同名键覆盖旧值，数据全在叶子里，叶子用 next 串成升序链。

内部节点有 c 个孩子、c-1 个键，第 i 个键等于第 i+1 个孩子子树的
最小键，所以查找时 bisect_right(keys, key) 的结果可以直接当孩子
下标。子树的最小键要顺着 children[0] 下到叶子才知道。
"""

from bisect import bisect_left, bisect_right

from .errors import InvariantError
from .nodes import reset
from .pool import NodePool


class BPlusTree:
    def __init__(self, min_degree=3, pool=None):
        if min_degree < 2:
            raise ValueError("min_degree 不能小于 2")
        self.min_degree = min_degree
        self.pool = pool if pool is not None else NodePool()
        self._root = self._new_leaf()
        self._size = 0
        self._stats = {
            "puts": 0, "gets": 0, "hits": 0, "misses": 0,
            "deletes": 0, "removed": 0, "scans": 0,
            "splits": 0, "merges": 0, "borrows": 0,
        }

    # ---- 容量口径 -------------------------------------------------

    @property
    def max_keys(self):
        return 2 * self.min_degree - 1

    @property
    def min_keys(self):
        return self.min_degree - 1

    @property
    def root(self):
        return self._root

    # ---- 节点构造 -------------------------------------------------

    def _new_leaf(self):
        return reset(self.pool.acquire(True))

    def _new_internal(self):
        return reset(self.pool.acquire(False))

    # ---- 读取 -----------------------------------------------------

    def _leaf_for(self, key):
        node = self._root
        while not node.is_leaf:
            node = node.children[bisect_right(node.keys, key)]
        return node

    def _min_key(self, node):
        """node 子树里的最小键。

        顺着最左孩子下到叶子；删除过程中最左叶子可能短暂为空，
        这时沿链往右找下一个非空叶子。整棵树都空时返回 None。
        """
        while not node.is_leaf:
            node = node.children[0]
        while node is not None and not node.keys:
            node = node.next
        return node.keys[0] if node is not None else None

    def _leftmost_leaf(self):
        node = self._root
        while not node.is_leaf:
            node = node.children[0]
        return node

    def get(self, key):
        self._stats["gets"] += 1
        leaf = self._leaf_for(key)
        i = bisect_left(leaf.keys, key)
        if i < len(leaf.keys) and leaf.keys[i] == key:
            self._stats["hits"] += 1
            return leaf.values[i]
        self._stats["misses"] += 1
        return None

    def contains(self, key):
        return self.get(key) is not None

    def scan(self, start=None, stop=None):
        """升序遍历 [start, stop) 区间，返回惰性迭代器。"""
        self._stats["scans"] += 1
        return self._scan(start, stop)

    def _scan(self, start, stop):
        if start is None:
            leaf = self._leftmost_leaf()
            i = 0
        else:
            leaf = self._leaf_for(start)
            i = bisect_left(leaf.keys, start)
        while leaf is not None:
            while i < len(leaf.keys):
                key = leaf.keys[i]
                if stop is not None and key >= stop:
                    return
                yield key, leaf.values[i]
                i += 1
            leaf = leaf.next
            i = 0

    def __len__(self):
        return self._size

    def height(self):
        node = self._root
        levels = 1
        while not node.is_leaf:
            node = node.children[0]
            levels += 1
        return levels

    def stats(self):
        snap = dict(self._stats)
        snap["size"] = self._size
        snap["height"] = self.height()
        return snap

    def pool_stats(self):
        return self.pool.stats()

    # ---- 写入 -----------------------------------------------------

    def put(self, key, value):
        """插入或覆盖，返回 True 表示新插入。"""
        self._stats["puts"] += 1
        leaf = self._leaf_for(key)
        i = bisect_left(leaf.keys, key)
        if i < len(leaf.keys) and leaf.keys[i] == key:
            leaf.values[i] = value
            return False
        leaf.keys.insert(i, key)
        leaf.values.insert(i, value)
        self._size += 1
        if i == 0:
            self._refresh_separator(leaf)
        if len(leaf.keys) > self.max_keys:
            self._split_leaf(leaf)
        return True

    def delete(self, key):
        """删除键，返回 True 表示确实删掉了。"""
        self._stats["deletes"] += 1
        leaf = self._leaf_for(key)
        i = bisect_left(leaf.keys, key)
        if i >= len(leaf.keys) or leaf.keys[i] != key:
            return False
        del leaf.keys[i]
        del leaf.values[i]
        self._size -= 1
        self._stats["removed"] += 1
        if i == 0 and leaf.keys:
            self._refresh_separator(leaf)
        if leaf is self._root or len(leaf.keys) >= self.min_keys:
            return True
        self._rebalance_leaf(leaf)
        return True

    # ---- 分隔键维护 -----------------------------------------------

    def _refresh_separator(self, node):
        """把 node 子树的最小键同步到父节点的分隔键上。

        node 是最左孩子时它自己就是父节点的最小键，继续往上冒。
        """
        parent = node.parent
        if parent is None:
            return
        idx = parent.children.index(node)
        if idx > 0:
            key = self._min_key(node)
            if key is not None:
                parent.keys[idx - 1] = key
            return
        self._refresh_separator(parent)

    # ---- 分裂 -----------------------------------------------------

    def _split_leaf(self, leaf):
        mid = len(leaf.keys) // 2
        right = self._new_leaf()
        right.keys = leaf.keys[mid:]
        right.values = leaf.values[mid:]
        leaf.keys = leaf.keys[:mid]
        leaf.values = leaf.values[:mid]
        right.next = leaf.next
        right.prev = leaf
        if leaf.next is not None:
            leaf.next.prev = right
        leaf.next = right
        self._stats["splits"] += 1
        self._insert_in_parent(leaf, right.keys[0], right)

    def _split_internal(self, node):
        cut = len(node.keys) // 2 + 1
        sep = node.keys[cut - 1]
        right = self._new_internal()
        right.keys = node.keys[cut:]
        right.children = node.children[cut:]
        node.keys = node.keys[:cut - 1]
        node.children = node.children[:cut]
        for child in right.children:
            child.parent = right
        self._stats["splits"] += 1
        self._insert_in_parent(node, sep, right)

    def _insert_in_parent(self, left, sep, right):
        parent = left.parent
        if parent is None:
            root = self._new_internal()
            root.keys = [sep]
            root.children = [left, right]
            left.parent = root
            right.parent = root
            self._root = root
            return
        i = parent.children.index(left)
        parent.keys.insert(i, sep)
        parent.children.insert(i + 1, right)
        right.parent = parent
        if len(parent.keys) > self.max_keys:
            self._split_internal(parent)

    # ---- 合并与借用 -----------------------------------------------

    def _unlink_child(self, parent, child, key_index):
        """摘掉一个孩子，连同该摘的分隔键。"""
        del parent.children[parent.children.index(child)]
        del parent.keys[key_index]

    def _rebalance_leaf(self, leaf):
        parent = leaf.parent
        idx = parent.children.index(leaf)
        left = parent.children[idx - 1] if idx > 0 else None
        right = parent.children[idx + 1] if idx + 1 < len(parent.children) else None
        if left is not None and len(left.keys) > self.min_keys:
            leaf.keys.insert(0, left.keys.pop())
            leaf.values.insert(0, left.values.pop())
            self._refresh_separator(leaf)
            self._stats["borrows"] += 1
            return
        if right is not None and len(right.keys) > self.min_keys:
            leaf.keys.append(right.keys.pop(0))
            leaf.values.append(right.values.pop(0))
            self._refresh_separator(right)
            self._refresh_separator(leaf)
            self._stats["borrows"] += 1
            return
        if left is not None:
            left.keys.extend(leaf.keys)
            left.values.extend(leaf.values)
            left.next = leaf.next
            if leaf.next is not None:
                leaf.next.prev = left
            self._unlink_child(parent, leaf, idx - 1)
            self.pool.release(leaf)
            keep = left
        else:
            right.keys[:0] = leaf.keys
            right.values[:0] = leaf.values
            right.prev = leaf.prev
            if leaf.prev is not None:
                leaf.prev.next = right
            self._unlink_child(parent, leaf, idx)
            self.pool.release(leaf)
            keep = right
        self._stats["merges"] += 1
        self._refresh_separator(keep)
        if len(parent.children) < self.min_degree:
            self._rebalance_internal(parent)

    def _rebalance_internal(self, node):
        parent = node.parent
        if parent is None:
            if len(node.children) == 1:
                child = node.children[0]
                self._root = child
                child.parent = None
                self.pool.release(node)
            return
        idx = parent.children.index(node)
        left = parent.children[idx - 1] if idx > 0 else None
        right = parent.children[idx + 1] if idx + 1 < len(parent.children) else None
        if left is not None and len(left.children) > self.min_degree:
            child = left.children.pop()
            left.keys.pop()
            node.children.insert(0, child)
            node.keys.insert(0, parent.keys[idx - 1])
            child.parent = node
            self._refresh_separator(node)
            self._stats["borrows"] += 1
            return
        if right is not None and len(right.children) > self.min_degree:
            child = right.children.pop(0)
            node.children.append(child)
            child.parent = node
            node.keys.append(parent.keys[idx])
            parent.keys[idx] = right.keys.pop(0)
            self._stats["borrows"] += 1
            return
        if left is not None:
            left.keys.append(parent.keys[idx - 1])
            left.keys.extend(node.keys)
            left.children.extend(node.children)
            for child in node.children:
                child.parent = left
            self._unlink_child(parent, node, idx - 1)
            self.pool.release(node)
            keep = left
        else:
            right.keys[:0] = node.keys + [parent.keys[idx]]
            right.children[:0] = node.children
            for child in node.children:
                child.parent = right
            self._unlink_child(parent, node, idx)
            self.pool.release(node)
            keep = right
        self._stats["merges"] += 1
        self._refresh_separator(keep)
        if len(parent.children) < self.min_degree:
            self._rebalance_internal(parent)

    # ---- 自检 -----------------------------------------------------

    def validate(self):
        """结构自检，违反任一不变量就抛 InvariantError。"""
        root = self._root
        if root.parent is not None:
            raise InvariantError("根节点不应该有父指针")
        if not root.is_leaf and len(root.children) < 2:
            raise InvariantError("根内部节点至少要有两个孩子")
        depths = set()
        self._validate_node(root, 0, depths)
        if len(depths) != 1:
            raise InvariantError("所有叶子必须在同一层，实际深度 %r" % sorted(depths))
        total = 0
        leaf = self._leftmost_leaf()
        prev = None
        while leaf is not None:
            if leaf.prev is not prev:
                raise InvariantError("叶子链的 prev 指针断了：%r" % (leaf,))
            if prev is not None and prev.keys and leaf.keys and prev.keys[-1] >= leaf.keys[0]:
                raise InvariantError("相邻叶子键序颠倒：%r / %r" % (prev, leaf))
            total += len(leaf.keys)
            prev = leaf
            leaf = leaf.next
        if total != self._size:
            raise InvariantError("链上键数 %d 与 size %d 不符" % (total, self._size))
        return True

    def _validate_node(self, node, depth, depths):
        keys = node.keys
        for i in range(1, len(keys)):
            if keys[i - 1] >= keys[i]:
                raise InvariantError("节点内键序不对：%r" % (node,))
        if len(keys) > self.max_keys:
            raise InvariantError("键数超上限：%r" % (node,))
        if node is not self._root and len(keys) < self.min_keys:
            raise InvariantError("键数低于下限：%r" % (node,))
        if node.is_leaf:
            depths.add(depth)
            return
        if len(node.children) != len(keys) + 1:
            raise InvariantError("内部节点孩子数应是键数加一：%r" % (node,))
        for i, child in enumerate(node.children):
            if child.parent is not node:
                raise InvariantError("孩子 %r 的父指针不对" % (child,))
            if not child.keys:
                raise InvariantError("内部节点的孩子不能是空的：%r" % (child,))
            if i > 0 and keys[i - 1] != self._min_key(child):
                raise InvariantError(
                    "分隔键 %r 与子树 %r 的最小键不符" % (keys[i - 1], child)
                )
            self._validate_node(child, depth + 1, depths)
