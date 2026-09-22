"""连接顺序规划。

Planner.plan 拿到新鲜的统计快照时，用行数和列基数估中间结果大小，
按等值条件把表分成若干连接组，组内用子集动态规划挑出估计探测行数
最小的顺序，组之间按声明顺序叉积。统计缺失、过期或对不上表时，
整体退回声明顺序。同样的查询加同样的统计，每次给出同一个计划。
"""

from .engine import Plan

# 子集动态规划最多处理的组大小，再大的组换贪心，保证规划耗时可控。
_DP_LIMIT = 13


class Planner:
    """给出查询的执行计划。"""

    def plan(self, query, stats=None):
        """按统计重排连接顺序；没有统计或统计对不上时退回声明顺序。"""
        declared = query.table_names()
        if stats is None or stats.stale(query.tables()):
            return Plan(declared)
        for t1, c1, t2, c2 in query.joins():
            if stats.distinct(t1, c1) is None or stats.distinct(t2, c2) is None:
                return Plan(declared)
        order = []
        for group in self.components(query):
            order.extend(self._order_component(query, stats, group))
        return Plan(tuple(order))

    def components(self, query):
        """按等值条件把表分成连不上的若干组，组内、组间都按声明顺序。"""
        names = query.table_names()
        parent = {name: name for name in names}

        def find(name):
            root = name
            while parent[root] != root:
                root = parent[root]
            while parent[name] != root:
                parent[name], name = root, parent[name]
            return root

        for t1, _, t2, _ in query.joins():
            r1, r2 = find(t1), find(t2)
            if r1 != r2:
                parent[r2] = r1
        groups = {}
        for name in names:
            groups.setdefault(find(name), []).append(name)
        return tuple(tuple(group) for group in groups.values())

    def _order_component(self, query, stats, group):
        """给一个连接组内部排序，按声明顺序的表名列表进，排好的列表出。"""
        if len(group) <= 1:
            return list(group)
        rows = [stats.row_count(name) for name in group]
        index = {name: i for i, name in enumerate(group)}
        # 每对表之间的所有等值条件合并成一个选择率因子。
        selectivity = [[1.0] * len(group) for _ in group]
        for t1, c1, t2, c2 in query.joins():
            if t1 not in index or t2 not in index:
                continue
            i, j = index[t1], index[t2]
            denom = max(stats.distinct(t1, c1), stats.distinct(t2, c2))
            factor = 1.0 / denom if denom > 0 else 1.0
            selectivity[i][j] *= factor
            selectivity[j][i] *= factor
        if len(group) > _DP_LIMIT:
            return self._greedy_order(group, rows, selectivity)
        return self._dp_order(group, rows, selectivity)

    @staticmethod
    def _dp_order(group, rows, selectivity):
        """子集动态规划：估每个前缀的中间结果大小，挑总探测行数最小的顺序。"""
        k = len(group)
        size = 1 << k
        card = [0.0] * size
        cost = [0.0] * size
        choice = [-1] * size
        card[0] = 1.0
        for mask in range(1, size):
            bit = mask & -mask
            i = bit.bit_length() - 1
            prev = mask ^ bit
            value = card[prev] * rows[i]
            for j in range(k):
                if prev >> j & 1:
                    value *= selectivity[i][j]
            card[mask] = value
        for mask in range(1, size):
            best_cost = None
            best_i = -1
            for i in range(k):
                bit = 1 << i
                if not mask & bit:
                    continue
                prev = mask ^ bit
                cand = cost[prev] + card[prev] * rows[i]
                if best_cost is None or cand < best_cost:
                    best_cost = cand
                    best_i = i
            cost[mask] = best_cost
            choice[mask] = best_i
        order = []
        mask = size - 1
        while mask:
            i = choice[mask]
            order.append(group[i])
            mask ^= 1 << i
        order.reverse()
        return order

    @staticmethod
    def _greedy_order(group, rows, selectivity):
        """大组兜底：每一步挑让当前前缀估计探测行数最小的表。"""
        remaining = set(range(len(group)))
        placed = []
        prefix_card = 1.0
        order = []
        while remaining:
            best = None
            for i in sorted(remaining):
                cand = prefix_card * rows[i]
                if best is None or cand < best[0]:
                    best = (cand, i)
            i = best[1]
            order.append(group[i])
            remaining.remove(i)
            factor = rows[i]
            for j in placed:
                factor *= selectivity[i][j]
            prefix_card *= factor
            placed.append(i)
        return order

    def __repr__(self):
        return "Planner()"
