"""treedpx.core：树上背包的朴素基线实现（暴力枚举口径）。

节点用字符串命名，整棵树由若干节点组成，每个节点带重量与价值。规则：选某个
节点之前必须先选它的父节点，根节点没有父节点因此可以直接选，任何节点都可以
不选。目标是求出容量上限下能取得的最大总价值，并给出对应的选择、统计可行
方案数。

当前实现把全部节点的组合枚举出来（共 2 的节点数次方个），对每个组合逐一校验
父子约束、累加重量与价值，最后在重量不超容量的组合里取价值最大者。节点一多
枚举量就爆炸，但口径直白、结果确定。
"""


class TreeError(Exception):
    """treedpx 全部异常的基类。"""


class TreeInputError(TreeError):
    """输入数据不合法：节点为空、重量或价值不是非负整数、树结构成环等。"""


class UnknownNode(TreeError):
    """查询了一个没有登记的节点名。"""


def _check_capacity(capacity):
    """容量必须是非负整数。"""
    if isinstance(capacity, bool) or not isinstance(capacity, int):
        raise TreeInputError("容量必须是非负整数")
    if capacity < 0:
        raise TreeInputError("容量不能为负数")
    return capacity


class TreeKnapsack:
    """树上背包的暴力求解器。

    load(nodes, parent) 载入一棵树：
      nodes 是 节点名 -> (重量, 价值) 的字典；
      parent 是 节点名 -> 父节点名或 None 的字典，值为 None 表示该节点是根。
    多次 load 会整体替换上一棵树。
    """

    def __init__(self):
        self._nodes = None
        self._weights = None
        self._values = None
        self._parents = None

    # ------------------------------------------------------------------ 载入
    def load(self, nodes, parent):
        """校验并登记一棵树。任何不合法都抛 TreeInputError。"""
        if not isinstance(nodes, dict):
            raise TreeInputError("nodes 必须是字典")
        if not nodes:
            raise TreeInputError("树至少要有节点")
        if not isinstance(parent, dict):
            raise TreeInputError("parent 必须是字典")

        weights = {}
        values = {}
        for name, pair in nodes.items():
            if not isinstance(name, str) or not name:
                raise TreeInputError("节点名必须是非空字符串")
            if not isinstance(pair, (tuple, list)) or len(pair) != 2:
                raise TreeInputError("节点 %s 的重量价值必须是二元组" % name)
            weight, value = pair
            if isinstance(weight, bool) or not isinstance(weight, int) or weight < 0:
                raise TreeInputError("节点 %s 的重量必须是非负整数" % name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise TreeInputError("节点 %s 的价值必须是非负整数" % name)
            weights[name] = weight
            values[name] = value

        for name in parent:
            if name not in nodes:
                raise UnknownNode("parent 里有未登记的节点 %s" % name)
        for name in nodes:
            if name not in parent:
                raise TreeInputError("节点 %s 缺少父节点登记" % name)

        parents = {}
        for name in nodes:
            up = parent[name]
            if up is not None and (not isinstance(up, str) or up not in nodes):
                raise UnknownNode("节点 %s 的父节点 %r 未登记" % (name, up))
            if up == name:
                raise TreeInputError("节点 %s 不能以自己为父节点" % name)
            parents[name] = up

        # 沿父指针上溯必须能走到根，中途重复即说明成环。
        for name in nodes:
            seen = set()
            cur = name
            while cur is not None:
                if cur in seen:
                    raise TreeInputError("父子关系里存在环，起点 %s" % name)
                seen.add(cur)
                cur = parents[cur]

        self._nodes = sorted(nodes)
        self._weights = weights
        self._values = values
        self._parents = parents

    def _loaded(self):
        if self._nodes is None:
            raise TreeInputError("尚未载入树，请先调用 load")
        return self._nodes, self._weights, self._values, self._parents

    # ------------------------------------------------------------------ 查询
    def nodes(self):
        """返回全部节点名，按字典序升序，结果确定。"""
        names, _, _, _ = self._loaded()
        return list(names)

    def parent_of(self, name):
        """返回某节点的父节点名，根节点返回 None。"""
        names, _, _, parents = self._loaded()
        if name not in parents:
            raise UnknownNode("未登记的节点 %s" % name)
        return parents[name]

    # -------------------------------------------------------------- 暴力求解
    def brute_force_scale(self):
        """暴力枚举要看的组合个数：2 的节点数次方。"""
        names, _, _, _ = self._loaded()
        return 1 << len(names)

    def state_scale(self, capacity):
        """状态表规模，尚未实现。"""
        self._loaded()
        _check_capacity(capacity)
        raise NotImplementedError("状态表规模统计尚未实现")

    def _is_legal(self, mask, index_of, parents):
        """组合里每个被选中的节点，其父节点也必须被选中。"""
        for name, bit in index_of.items():
            if mask & (1 << bit) and parents[name] is not None:
                if not (mask & (1 << index_of[parents[name]])):
                    return False
        return True

    def _value_of(self, mask, index_of, weights, values):
        value = 0
        weight = 0
        for name, bit in index_of.items():
            if mask & (1 << bit):
                value += values[name]
                weight += weights[name]
        return weight, value

    def brute_force_best(self, capacity):
        """逐组合枚举，返回容量上限下的最大总价值；没有可选项时返回 0。"""
        _check_capacity(capacity)
        names, weights, values, parents = self._loaded()
        index_of = {name: i for i, name in enumerate(names)}
        best_value = 0
        best_key = None
        for mask in range(1 << len(names)):
            if not self._is_legal(mask, index_of, parents):
                continue
            weight, value = self._value_of(mask, index_of, weights, values)
            if weight > capacity:
                continue
            chosen = tuple(names[i] for i in range(len(names)) if mask & (1 << i))
            key = (value, -weight, tuple(chosen))
            if best_key is None or key > best_key:
                best_key = key
                best_value = value
        return best_value

    def brute_force_selection(self, capacity):
        """逐组合枚举，返回一组最优选择，按节点名字典序升序；无解返回空列表。"""
        _check_capacity(capacity)
        names, weights, values, parents = self._loaded()
        index_of = {name: i for i, name in enumerate(names)}
        best_key = None
        best_chosen = ()
        for mask in range(1 << len(names)):
            if not self._is_legal(mask, index_of, parents):
                continue
            weight, value = self._value_of(mask, index_of, weights, values)
            if weight > capacity:
                continue
            chosen = tuple(names[i] for i in range(len(names)) if mask & (1 << i))
            key = (value, -weight, tuple(chosen))
            if best_key is None or key > best_key:
                best_key = key
                best_chosen = chosen
        return list(best_chosen)

    def feasible_count(self, capacity):
        """统计重量不超容量的合法组合数，空组合总是一个可行解。"""
        _check_capacity(capacity)
        names, weights, values, parents = self._loaded()
        index_of = {name: i for i, name in enumerate(names)}
        count = 0
        for mask in range(1 << len(names)):
            if not self._is_legal(mask, index_of, parents):
                continue
            weight, _ = self._value_of(mask, index_of, weights, values)
            if weight <= capacity:
                count += 1
        return count
