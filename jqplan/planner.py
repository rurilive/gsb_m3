"""连接顺序规划。

Planner 拿着统计快照，用行数和列基数估计每个执行前缀的中间结果大小，
按嵌套循环探测行数的口径给候选顺序估代价，挑出代价低的连接顺序。
条件图里连不上的表分成若干连接组（components），组内各自排好，
组与组之间按叉乘代价排序后拼接。统计没给、缺表、缺列基数或者快照
过期，都整体退回查询的声明顺序。同样的查询加同样的统计，出的计划
永远一样。
"""

from functools import cmp_to_key

from .engine import Plan


class _StatsIncomplete(Exception):
    """统计跟查询对不上，调用方整体退回声明顺序。"""


class _CostModel:
    """用统计快照给连接顺序估代价，口径跟 Engine 的 rows_scanned 一致。"""

    def __init__(self, query, stats):
        self._rows = {}
        for name in query.table_names():
            count = stats.row_count(name)
            if count is None:
                raise _StatsIncomplete(name)
            self._rows[name] = count
        self._selectivity = {}
        for t1, c1, t2, c2 in query.joins():
            d1 = stats.distinct(t1, c1)
            d2 = stats.distinct(t2, c2)
            if d1 is None or d2 is None:
                raise _StatsIncomplete((t1, c1, t2, c2))
            top = max(d1, d2)
            selectivity = 0.0 if top == 0 else 1.0 / top
            key = frozenset((t1, t2))
            self._selectivity[key] = self._selectivity.get(key, 1.0) * selectivity

    def rows(self, name):
        """表的估计行数。"""
        return self._rows[name]

    def selectivity(self, first, second):
        """两表之间所有等值条件的联合选择率，没有条件时为 1。"""
        if first == second:
            return 1.0
        return self._selectivity.get(frozenset((first, second)), 1.0)


def _cross_compare(left, right):
    """叉乘拼接时两组谁先谁后：先放"自己代价 + 自己结果放大对方代价"小的。"""
    _, cost_left, size_left = left
    _, cost_right, size_right = right
    left_first = cost_left + size_left * cost_right
    right_first = cost_right + size_right * cost_left
    return (left_first > right_first) - (left_first < right_first)


class Planner:
    """给出查询的执行计划。"""

    _EXACT_LIMIT = 12

    def plan(self, query, stats=None):
        """按统计挑连接顺序；统计没给、缺漏或过期时退回声明顺序。"""
        if stats is None or stats.stale(query.tables()):
            return Plan(query.table_names())
        try:
            model = _CostModel(query, stats)
        except _StatsIncomplete:
            return Plan(query.table_names())
        groups = []
        for members in self.components(query):
            order, cost, size = self._order_component(model, members)
            groups.append((order, cost, size))
        groups.sort(key=cmp_to_key(_cross_compare))
        return Plan(tuple(name for order, _, _ in groups for name in order))

    def components(self, query):
        """条件图里的连接组，组内和组间都按声明顺序排。"""
        parent = {name: name for name in query.table_names()}

        def find(name):
            while parent[name] != name:
                parent[name] = parent[parent[name]]
                name = parent[name]
            return name

        for t1, _, t2, _ in query.joins():
            root1, root2 = find(t1), find(t2)
            if root1 != root2:
                parent[root2] = root1
        groups = {}
        for name in query.table_names():
            groups.setdefault(find(name), []).append(name)
        return tuple(tuple(members) for members in groups.values())

    def _order_component(self, model, members):
        """组内排序，返回 (顺序, 估计代价, 估计结果大小)。"""
        members = tuple(sorted(members))
        if len(members) > self._EXACT_LIMIT:
            return self._greedy_order(model, members)
        count = len(members)
        rows = [model.rows(name) for name in members]
        sel = [[1.0] * count for _ in range(count)]
        for i in range(count):
            for j in range(i + 1, count):
                sel[i][j] = sel[j][i] = model.selectivity(members[i], members[j])
        size = [0.0] * (1 << count)
        cost = [0.0] * (1 << count)
        choice = [0] * (1 << count)
        size[0] = 1.0
        for subset in range(1, 1 << count):
            low = subset & (-subset)
            low_index = low.bit_length() - 1
            rest = subset ^ low
            selectivity = 1.0
            others = rest
            while others:
                bit = others & (-others)
                selectivity *= sel[low_index][bit.bit_length() - 1]
                others ^= bit
            size[subset] = size[rest] * rows[low_index] * selectivity
            best_cost = None
            best_last = 0
            for last in range(count):
                if not subset & (1 << last):
                    continue
                prev = subset ^ (1 << last)
                candidate = rows[last] if prev == 0 else cost[prev] + size[prev] * rows[last]
                if best_cost is None or candidate < best_cost:
                    best_cost = candidate
                    best_last = last
            cost[subset] = best_cost
            choice[subset] = best_last
        order = []
        subset = (1 << count) - 1
        while subset:
            last = choice[subset]
            order.append(members[last])
            subset ^= 1 << last
        order.reverse()
        full = (1 << count) - 1
        return tuple(order), cost[full], size[full]

    def _greedy_order(self, model, members):
        """大连接组的兜底：从最小的表出发，每次接估计结果最小的表。"""
        remaining = list(members)
        first = min(remaining, key=lambda name: (model.rows(name), name))
        remaining.remove(first)
        order = [first]
        cost = float(model.rows(first))
        size = float(model.rows(first))
        while remaining:

            def grown(name):
                selectivity = 1.0
                for placed in order:
                    selectivity *= model.selectivity(name, placed)
                return (size * model.rows(name) * selectivity, model.rows(name), name)

            picked = min(remaining, key=grown)
            remaining.remove(picked)
            cost += size * model.rows(picked)
            size = grown(picked)[0]
            order.append(picked)
        return tuple(order), cost, size

    def __repr__(self):
        return "Planner()"
