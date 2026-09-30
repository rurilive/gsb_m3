"""centroid.core：树的重心、子树规模与树上路径问题的朴素基线实现。

树用邻接表给出：edges 是若干条无向边，每条边是两个端点编号与一个正权。编号
从零开始，全树恰好 n 减 1 条边且连通，根固定为编号零。

当前实现全部走最直白的枚举：
  - 子树规模：对每个结点各自跑一遍遍历，数出以它为根的子树大小；
  - 重心：对每个结点把它删掉，分别求各个连通块的大小取最大，再用同样方式把
    全部结点试一遍，取最大块最小的结点，并列时取编号最小者；
  - 两点距离与路径最大值：枚举全部点对，再各自沿树求距离与路径上的最大权；
  - 路径计数：枚举全部点对，对每个点对各自求距离，再统计不超过上界的条数。

规模一大就退化到平方甚至立方量级，但结果正确、口径固定。
"""


class CentroidError(Exception):
    """centroid 全部异常的基类。"""


class CentroidInputError(CentroidError):
    """输入数据不合法：结点数为空、边数与结点数不匹配、端点越界、权不为正整数、
    图不连通、结点编号缺失或成环等。"""


class UnknownNode(CentroidError):
    """查询了一个没有登记的结点编号。"""


def _check_node(n, node):
    """结点编号必须是非负整数，且已完成载入。"""
    if n is None:
        raise CentroidInputError("尚未载入树，请先调用 load")
    if isinstance(node, bool) or not isinstance(node, int):
        raise CentroidInputError("结点编号必须是整数")
    if node < 0 or node >= n:
        raise UnknownNode("未登记的结点编号 %r" % (node,))


class TreeCentroid:
    """树的重心与树上路径问题的朴素求解器。

    load(n, edges) 载入一棵树：
      n 是结点个数，编号取 0 到 n 减 1；
      edges 是若干条边，每条边形如 (u, v, w)，u 与 v 是端点，w 是正权。
    多次 load 会整体替换上一棵树。
    """

    def __init__(self):
        self._n = None
        self._adj = None

    # ------------------------------------------------------------------ 载入
    def load(self, n, edges):
        """校验并登记一棵树。任何不合法都抛 CentroidInputError。"""
        if isinstance(n, bool) or not isinstance(n, int):
            raise CentroidInputError("结点个数必须是整数")
        if n <= 0:
            raise CentroidInputError("树至少要有结点")
        if not isinstance(edges, (list, tuple)):
            raise CentroidInputError("边表必须是列表或元组")

        adj = {}
        for i in range(n):
            adj[i] = []

        for item in edges:
            if not isinstance(item, (list, tuple)) or len(item) != 3:
                raise CentroidInputError("每条边必须是三元组")
            u, v, w = item
            if (isinstance(u, bool) or not isinstance(u, int)
                    or isinstance(v, bool) or not isinstance(v, int)):
                raise CentroidInputError("边端点必须是整数")
            if u < 0 or u >= n or v < 0 or v >= n:
                raise UnknownNode("边端点越界")
            if isinstance(w, bool) or not isinstance(w, int) or w <= 0:
                raise CentroidInputError("边权必须是正整数")
            adj[u].append((v, w))
            adj[v].append((u, w))

        if len(edges) != n - 1:
            raise CentroidInputError("树恰好有结点数减一条边")
        self._check_connected(adj, n)

        for i in range(n):
            adj[i].sort()
        self._n = n
        self._adj = adj

    def _check_connected(self, adj, n):
        """全树必须连通，否则抛 CentroidInputError。"""
        seen = set()
        stack = [0]
        while stack:
            node = stack.pop()
            if node in seen:
                continue
            seen.add(node)
            for nxt, _ in adj[node]:
                if nxt not in seen:
                    stack.append(nxt)
        if len(seen) != n:
            raise CentroidInputError("树必须连通")

    def _loaded(self):
        if self._n is None:
            raise CentroidInputError("尚未载入树，请先调用 load")
        return self._n, self._adj

    # ------------------------------------------------------------------ 查询
    def nodes(self):
        """返回全部结点编号，按升序，结果确定。"""
        n, _ = self._loaded()
        return list(range(n))

    def brute_scale(self):
        """朴素口径的规模：结点数乘以结点数，量级随结点数平方增长。"""
        n, _ = self._loaded()
        return n * n

    # ------------------------------------------------------- 子树规模（朴素）
    def subtree_size(self, root):
        """以 root 为根，返回 结点编号 到 以它为根的子树规模 的映射。

        朴素口径：对每个结点各自从 root 跑一遍遍历，数出以该结点为根的子树里
        有多少个结点。每个结点都要重新展开一遍。
        """
        n, adj = self._loaded()
        _check_node(n, root)
        order = self._bfs_order(root)
        size = {}
        for node in range(n):
            if not self._reachable(root, node):
                continue
            size[node] = self._count_subtree(root, node)
        return size

    def _bfs_order(self, root):
        """从 root 出发的遍历次序，父指针一并求出。"""
        n, adj = self._loaded()
        parent = {root: None}
        order = [root]
        head = 0
        while head < len(order):
            node = order[head]
            head += 1
            for nxt, _ in adj[node]:
                if nxt not in parent:
                    parent[nxt] = node
                    order.append(nxt)
        return order

    def _reachable(self, root, node):
        """node 是否在以 root 为根的树里（树连通，恒真，仍逐一走一遍）。"""
        for item in self._bfs_order(root):
            if item == node:
                return True
        return False

    def _count_subtree(self, root, node):
        """朴素地数出以 root 为根时，node 子树里的结点个数。"""
        n, adj = self._loaded()
        parent = {root: None}
        order = [root]
        head = 0
        while head < len(order):
            cur = order[head]
            head += 1
            for nxt, _ in adj[cur]:
                if nxt not in parent:
                    parent[nxt] = cur
                    order.append(nxt)
        children = {}
        for name, up in parent.items():
            children.setdefault(up, []).append(name)
        count = 0
        stack = [node]
        while stack:
            cur = stack.pop()
            count += 1
            for child in children.get(cur, []):
                stack.append(child)
        return count

    # --------------------------------------------------- 重心（朴素）
    def component_sizes(self, node):
        """删掉 node 后，各连通块的大小，按升序。"""
        n, adj = self._loaded()
        _check_node(n, node)
        seen = {node}
        sizes = []
        for start in range(n):
            if start in seen:
                continue
            comp = []
            stack = [start]
            seen.add(start)
            while stack:
                cur = stack.pop()
                comp.append(cur)
                for nxt, _ in adj[cur]:
                    if nxt not in seen:
                        seen.add(nxt)
                        stack.append(nxt)
            sizes.append(len(comp))
        sizes.sort()
        return sizes

    def largest_component(self, node):
        """删掉 node 后，最大连通块的大小；孤立点返回零。"""
        sizes = self.component_sizes(node)
        if not sizes:
            return 0
        return sizes[-1]

    def centroid(self):
        """按编号升序试完全部结点，取最大连通块最小者，并列取编号最小者。"""
        n, _ = self._loaded()
        best_node = None
        best_key = None
        for node in range(n):
            key = ((self.largest_component(node)), node)
            if best_key is None or key < best_key:
                best_key = key
                best_node = node
        return best_node

    def centroids(self):
        """全部满足重心条件的结点编号，按升序。"""
        n, _ = self._loaded()
        best = self.largest_component(self.centroid())
        out = []
        for node in range(n):
            if self.largest_component(node) == best:
                out.append(node)
        return out

    def centroid_property(self, node):
        """重心性质：不以 node 为重心的结点，都存在一棵子树结点数超过一半，
        且那棵子树正是最大连通块，返回 (块大小, 是否超过半数的布尔值)。

        朴素口径：直接枚举全部连通块后取最大，再与结点数的一半比较。
        """
        n, _ = self._loaded()
        _check_node(n, node)
        biggest = self.largest_component(node)
        return (biggest, biggest * 2 > n)

    # ------------------------------------------ 两点距离与路径最大值（朴素）
    def path_stats(self, u, v):
        """返回 u 到 v 的距离与路径上的最大边权，形如 (距离, 最大值)。

        朴素口径：先从 u 走到根，记下路径；再从 v 走到根，拼出 u 到 v 的路径，
        再在路径上逐条边累加并取最大。
        """
        n, adj = self._loaded()
        _check_node(n, u)
        _check_node(n, v)
        path = self._path_between(u, v)
        dist = 0
        peak = 0
        for i in range(len(path) - 1):
            a = path[i]
            b = path[i + 1]
            w = self._edge_weight(a, b)
            dist += w
            if w > peak:
                peak = w
        return (dist, peak)

    def _edge_weight(self, a, b):
        n, adj = self._loaded()
        for nxt, w in adj[a]:
            if nxt == b:
                return w
        raise UnknownNode("结点 %r 与 %r 之间没有边" % (a, b))

    def _path_between(self, u, v):
        """朴素地求 u 到 v 的结点路径：各自上溯到根，去掉公共的 祖先到根 段再拼。"""
        up = self._path_to_root(u)
        vp = self._path_to_root(v)
        # 两条 结点到根 的序列共享同一段 祖先到根 的后缀，从尾部对齐找最长公共后缀。
        same = 0
        while (same < len(up) and same < len(vp)
               and up[-1 - same] == vp[-1 - same]):
            same += 1
        head = up[:len(up) - same + 1]
        tail = list(reversed(vp[:len(vp) - same]))
        return head + tail

    def _path_to_root(self, node):
        """从结点出发沿父指针走到编号零这条链上的结点序列。"""
        n, adj = self._loaded()
        parent = {0: None}
        order = [0]
        head = 0
        while head < len(order):
            cur = order[head]
            head += 1
            for nxt, _ in adj[cur]:
                if nxt not in parent:
                    parent[nxt] = cur
                    order.append(nxt)
        seq = []
        cur = node
        while cur is not None:
            seq.append(cur)
            cur = parent[cur]
        return seq

    def distance(self, u, v):
        """朴素口径下的树上两点距离。"""
        return self.path_stats(u, v)[0]

    def max_edge_on_path(self, u, v):
        """朴素口径下两点路径上的最大边权。"""
        return self.path_stats(u, v)[1]

    def brute_pair_scale(self):
        """暴力枚举点对的规模，即 结点数 乘以 结点数减一 再除二。"""
        n, _ = self._loaded()
        return n * (n - 1) // 2

    # ------------------------------------------------- 路径计数（朴素）
    def count_paths_within(self, limit):
        """统计距离不超过 limit 的无序点对条数。

        朴素口径：枚举全部点对，对每个点对各自求一次距离再比上界。
        """
        n, _ = self._loaded()
        if isinstance(limit, bool) or not isinstance(limit, int):
            raise CentroidInputError("上界必须是整数")
        if limit < 0:
            raise CentroidInputError("上界不能为负数")
        count = 0
        for u in range(n):
            for v in range(u + 1, n):
                if self.distance(u, v) <= limit:
                    count += 1
        return count
