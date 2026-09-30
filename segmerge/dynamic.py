"""segmerge.dynamic：动态集合合并工具包（改造前的朴素实现）。

现状做法：一棵树，每个节点各自挂一个小权值集合。要把子节点的集合并入
父节点，基线只会把一方集合里的元素逐个取出来，逐个追加到另一方的桶里，
自底向上合并整棵树。合并完的那只桶整体排一次序，之后所有统计都在这只
排序桶上从头扫过：数某个权值出现几次就逐个比一遍，求前几大之和就整桶
排序再切前几项，数不同权值个数就把桶里元素塞进一个集合再看大小，求某个
权值排第几就从头数有多少个比它小，取第几小就排好序后直接按下标取。

这套做法结果是对的，规模小时一眼能看穿，但合并的代价与元素个数成正比：
子树越大，往父节点里搬的元素越多，自底向上走完整棵树就是元素总数与节
点数相乘的量级，树退化成链时更是平方量级。非法节点号、非法权值、越界
的 k、无法定义的排名与取小，统一抛异常快速失败，绝不悄悄兜底。
"""


class MergeSegError(Exception):
    """segmerge 全部异常的共同基类。"""


class NodeIndexError(MergeSegError):
    """节点号不存在，属于调用方非法输入。"""


class BadWeightError(MergeSegError):
    """权值不是整数，属于调用方非法输入。"""


class TreeShapeError(MergeSegError):
    """给的父子关系构不成一棵树：多根、成环或自指。"""


class EmptySetError(MergeSegError):
    """对空集合下达了无法定义结果的操作。"""


class KOutOfRangeError(MergeSegError):
    """k 越出合法区间，属于调用方非法输入。"""


class MergeTree:
    """一棵节点各挂一个权值集合的树（基线：逐元素搬移合并）。

    构造参数 parents 与 weights 等长：parents[i] 是节点 i 的父节点号，根
    节点的父记为负一；weights[i] 是节点 i 自己的那一个小集合，允许为空。
    合并的口径是「子树并集的多重集」，同一个权值出现几次就算几次。自底向
    上合并时，基线把每个子节点合好的整只桶逐个元素追加进父节点的桶里，最
    后整体排序，之后每次统计都在这只排序桶上从头扫过。
    """

    def __init__(self, parents, weights):
        parents = list(parents)
        weights = [list(w) for w in weights]
        if len(parents) != len(weights):
            raise TreeShapeError("parents and weights differ in length")
        n = len(parents)
        for i, w in enumerate(weights):
            for v in w:
                self._check_weight(v)
        self._parents = parents
        self._weights = weights
        self._children = [[] for _ in range(n)]
        roots = []
        for i, p in enumerate(parents):
            if p == -1:
                roots.append(i)
            else:
                if not isinstance(p, int) or isinstance(p, bool):
                    raise TreeShapeError("parent must be an int")
                if p < 0 or p >= n:
                    raise TreeShapeError("parent %r out of range" % (p,))
                if p == i:
                    raise TreeShapeError("node %r is its own parent" % (i,))
                self._children[p].append(i)
        if n == 0:
            pass
        elif len(roots) != 1:
            raise TreeShapeError("expected exactly one root, got %r"
                                 % (len(roots),))
        self._check_acyclic(roots)
        self._cache = {}
        self._moves = 0

    @staticmethod
    def _check_weight(value):
        if not isinstance(value, int) or isinstance(value, bool):
            raise BadWeightError("weight must be an int, got %r"
                                 % (type(value).__name__,))

    def _check_acyclic(self, roots):
        """连通性检查：除根外每个点都要能沿父指针走到根。"""
        n = len(self._parents)
        for start in range(n):
            seen = set()
            cur = start
            while cur != -1:
                if cur in seen:
                    raise TreeShapeError("parent chain forms a cycle")
                seen.add(cur)
                cur = self._parents[cur]

    def node_count(self):
        """节点个数。"""
        return len(self._parents)

    def root(self):
        """根节点号；空树返回 None。"""
        for i, p in enumerate(self._parents):
            if p == -1:
                return i
        return None

    def children(self, node_id):
        """某节点的直接子节点号，按升序给出。"""
        self._check_node(node_id)
        return list(self._children[node_id])

    def local_weights(self, node_id):
        """某节点自己那一个小集合的拷贝。"""
        self._check_node(node_id)
        return list(self._weights[node_id])

    def _check_node(self, node_id):
        if not isinstance(node_id, int) or isinstance(node_id, bool):
            raise NodeIndexError("node id must be an int")
        if node_id < 0 or node_id >= len(self._parents):
            raise NodeIndexError("no such node: %r" % (node_id,))

    def clear_cache(self):
        """清掉已合好的桶，让下一次合并重新逐元素搬一遍。"""
        self._cache = {}

    def _merged(self, node_id):
        """自底向上合出子树的多重集，返回一只升序桶。

        基线做法：先放本节点自己的元素，再逐个取子节点合好的桶，把里面
        每一个元素逐个追加进来，全部追加完再整体排序一次。每搬一个元素，
        计数加一，暴露的就是「逐个搬移」这一现状。
        """
        cached = self._cache.get(node_id)
        if cached is not None:
            return cached
        bucket = list(self._weights[node_id])
        for child in self._children[node_id]:
            for value in self._merged(child):
                bucket.append(value)
                self._moves += 1
        bucket.sort()
        self._cache[node_id] = bucket
        return bucket

    def merged_values(self, node_id):
        """合并后子树多重集的升序拷贝，改它不影响实例。"""
        self._check_node(node_id)
        return list(self._merged(node_id))

    def size(self, node_id):
        """合并后集合的元素总个数，重复权值各算一次。"""
        self._check_node(node_id)
        return len(self._merged(node_id))

    def count_of(self, node_id, value):
        """合并后某权值出现的次数，没有就算零。"""
        self._check_node(node_id)
        self._check_weight(value)
        total = 0
        for v in self._merged(node_id):
            if v == value:
                total += 1
        return total

    def topk_sum(self, node_id, k):
        """合并后权值的前 k 大之和。k 为零返回零，越界抛异常。"""
        self._check_node(node_id)
        bucket = self._merged(node_id)
        if not isinstance(k, int) or isinstance(k, bool):
            raise KOutOfRangeError("k must be an int")
        if k < 0 or k > len(bucket):
            raise KOutOfRangeError("k %r out of [0, %r]" % (k, len(bucket)))
        ordered = sorted(bucket, reverse=True)
        return sum(ordered[:k])

    def distinct_count(self, node_id):
        """合并后不同权值的个数。"""
        self._check_node(node_id)
        return len(set(self._merged(node_id)))

    def rank_of(self, node_id, value):
        """某权值在合并集合中的排名，从一算起。

        口径：比该权值小的元素个数加一，也就是它若排进升序序列里最靠前
        那一次出现所在的位置；该权值一个也没有时同样给出这个口径下的值。
        """
        self._check_node(node_id)
        self._check_weight(value)
        smaller = 0
        for v in self._merged(node_id):
            if v < value:
                smaller += 1
        return smaller + 1

    def kth_smallest(self, node_id, k):
        """合并后第 k 小的权值，k 从一算起。

        基线做法：桶已经排好序，直接按下标取第 k 减一项；空集合或 k 越界
        抛异常。
        """
        self._check_node(node_id)
        bucket = self._merged(node_id)
        if not bucket:
            raise EmptySetError("no kth element over an empty set")
        if not isinstance(k, int) or isinstance(k, bool) or k < 1 \
                or k > len(bucket):
            raise KOutOfRangeError("k %r out of [1, %r]" % (k, len(bucket)))
        return bucket[k - 1]

    def merge_report(self):
        """整棵树每个节点的合并结果，节点号为键。

        每个节点给出元素总个数、不同权值个数、最大值与最小值；空集合的
        最大值与最小值记为 None。
        """
        report = {}
        for node_id in range(len(self._parents)):
            bucket = self._merged(node_id)
            report[node_id] = {
                "total": len(bucket),
                "distinct": len(set(bucket)),
                "min": bucket[0] if bucket else None,
                "max": bucket[-1] if bucket else None,
            }
        return report

    def naive_moves(self):
        """朴素逐个搬移计数：建实例以来累计追加过的元素个数。"""
        return self._moves
