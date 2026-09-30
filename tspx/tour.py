"""tspx：完全图上最短闭合回路的朴素实现（改造前基线）。

只用最直白的做法：枚举全部排列挑最短回路，或对每个起点做朴素最近邻。
只有标准库，无外部依赖。
"""

import itertools


def distance(a, b):
    """两点之间的欧氏距离。"""
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5


def tour_length(points, order):
    """按给定次序把点依次相连再回到起点，返回闭合回路长度。

    次序为空时长度为 0.0，只有一个点时长度为 0.0。
    """
    total = 0.0
    n = len(order)
    if n == 0:
        return total
    for i in range(n):
        p = points[order[i]]
        q = points[order[(i + 1) % n]]
        total += distance(p, q)
    return total


def all_permutations(n):
    """前 n 个下标 0..n-1 的全部排列。"""
    return itertools.permutations(range(n))


class TspSolver:
    """旅行商问题的朴素求解器。

    坐标形如 [(x, y), ...]，可以重复，也可以为空。
    """

    def __init__(self, points):
        self.points = [tuple(float(c) for c in p) for p in points]

    def count(self):
        """点数。"""
        return len(self.points)

    def enumerate_best(self):
        """枚举全部排列，返回最短回路长度与达到该长度的最小次序。

        点数小于等于 1 直接返回零长度与平凡次序，不做枚举。
        """
        n = self.count()
        if n <= 1:
            return 0.0, list(range(n))
        best_len = None
        best_order = None
        for order in all_permutations(n):
            length = tour_length(self.points, order)
            if best_len is None or length < best_len:
                best_len = length
                best_order = list(order)
        return best_len, best_order

    def enumerate_count(self):
        """枚举口径下需要考察的排列数。"""
        n = self.count()
        if n <= 1:
            return 0
        total = 1
        for k in range(2, n + 1):
            total *= k
        return total

    def nearest_neighbor(self, start):
        """朴素最近邻：从 start 出发，每次挑最近的未访问点。

        返回回路次序与长度。点数小于等于 1 时返回平凡结果。
        """
        n = self.count()
        if n == 0:
            return [], 0.0
        if n == 1:
            return [0], 0.0
        visited = [start]
        used = set(visited)
        while len(visited) < n:
            cur = visited[-1]
            best = None
            best_d = None
            for j in range(n):
                if j in used:
                    continue
                d = distance(self.points[cur], self.points[j])
                if best_d is None or d < best_d or (d == best_d and j < best):
                    best_d = d
                    best = j
            visited.append(best)
            used.add(best)
        return visited, tour_length(self.points, visited)

    def nearest_neighbor_over_starts(self):
        """对每个起点各做一次朴素最近邻，返回其中最短的一个。

        返回回路长度、次序与起点。点数小于等于 1 时返回平凡结果。
        """
        n = self.count()
        if n <= 1:
            return 0.0, list(range(n)), 0
        best_len = None
        best_order = None
        best_start = None
        for start in range(n):
            order, length = self.nearest_neighbor(start)
            if best_len is None or length < best_len:
                best_len = length
                best_order = order
                best_start = start
        return best_len, best_order, best_start
