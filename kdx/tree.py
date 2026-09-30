"""高维点集上的最近邻查询基线实现。

当前只提供朴素但正确的路径：最近邻与 k 近邻都逐点算距离后排序取最小，
范围查询逐点判断是否落在矩形或球内，最近点对与半径计数也一律枚举全部点。
点数一多，每次查询都要扫一遍整个集合。
"""

import math


class KdxError(Exception):
    """本包所有异常的基类。"""


class InvalidPointsError(KdxError):
    """点集本身不合法：坐标非数值、点为空、各点维度不一致等。"""


class DimensionMismatchError(KdxError):
    """查询点或区域的维度与点集维度不一致。"""


class EmptyPointSetError(KdxError):
    """点集为空，无法完成该查询。"""


class InvalidKError(KdxError):
    """k 近邻的 k 不是正整数。"""


class InvalidRadiusError(KdxError):
    """半径不是非负的数值。"""


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_point(point):
    if not isinstance(point, (tuple, list)):
        raise InvalidPointsError("点必须是坐标序列")
    coords = tuple(point)
    if not coords:
        raise InvalidPointsError("点至少需要一个坐标")
    for c in coords:
        if not _is_number(c):
            raise InvalidPointsError("坐标必须是数值且不能是布尔值")
    return coords


def _squared_distance(a, b):
    total = 0.0
    for i in range(len(a)):
        d = a[i] - b[i]
        total += d * d
    return total


def _distance(a, b):
    return math.sqrt(_squared_distance(a, b))


class PointSet(object):
    """维护一批等维度的点，按插入顺序保留，下标即插入位置。"""

    def __init__(self, points=()):
        coords = []
        for p in points:
            coords.append(_validate_point(p))
        dim = len(coords[0]) if coords else 0
        for c in coords:
            if len(c) != dim:
                raise InvalidPointsError("所有点的维度必须一致")
        self._points = coords
        self._dim = dim

    @property
    def dimension(self):
        return self._dim

    @property
    def points(self):
        return list(self._points)

    @property
    def pruning_count(self):
        """朴素路径不做任何子树剪枝，计数恒为零。"""
        return 0

    def reset_stats(self):
        pass

    def size(self):
        return len(self._points)

    def __len__(self):
        return len(self._points)

    def _normalize_query(self, point):
        coords = _validate_point(point)
        if len(coords) != self._dim:
            raise DimensionMismatchError("查询点维度与点集不一致")
        return coords

    def _require_non_empty(self):
        if not self._points:
            raise EmptyPointSetError("点集为空，无法查询")

    def nearest(self, point):
        """返回 (下标, 距离)，距离相同取下标较小者。"""
        self._require_non_empty()
        q = self._normalize_query(point)
        best_index = 0
        best_sq = _squared_distance(q, self._points[0])
        for i in range(1, len(self._points)):
            sq = _squared_distance(q, self._points[i])
            if sq < best_sq:
                best_sq = sq
                best_index = i
        return best_index, math.sqrt(best_sq)

    def knearest(self, point, k):
        """返回按 (距离, 下标) 升序排列的前 k 项。"""
        self._require_non_empty()
        if not isinstance(k, int) or isinstance(k, bool) or k < 1:
            raise InvalidKError("k 必须是正整数")
        q = self._normalize_query(point)
        scored = []
        for i in range(len(self._points)):
            scored.append((_squared_distance(q, self._points[i]), i))
        scored.sort(key=lambda item: (item[0], item[1]))
        result = []
        for sq, i in scored[:k]:
            result.append((i, math.sqrt(sq)))
        return result

    def range_query_rect(self, lower, upper):
        """返回落在闭超矩形内的点下标，按下标升序。"""
        lo = self._normalize_query(lower)
        hi = self._normalize_query(upper)
        for i in range(len(lo)):
            if lo[i] > hi[i]:
                raise InvalidPointsError("矩形下界不能大于上界")
        hits = []
        for i in range(len(self._points)):
            p = self._points[i]
            inside = True
            for d in range(len(p)):
                if p[d] < lo[d] or p[d] > hi[d]:
                    inside = False
                    break
            if inside:
                hits.append(i)
        return hits

    def range_query_ball(self, center, radius):
        """返回落在闭球（距离小于等于半径）内的点下标，按下标升序。"""
        c = self._normalize_query(center)
        if not _is_number(radius) or radius < 0:
            raise InvalidRadiusError("半径必须是非负数值")
        r_sq = radius * radius
        hits = []
        for i in range(len(self._points)):
            if _squared_distance(c, self._points[i]) <= r_sq:
                hits.append(i)
        return hits

    def nearest_pair(self):
        """返回 (i, j, 距离)，i 小于 j，距离相同取字典序最小的下标对。"""
        if len(self._points) < 2:
            raise EmptyPointSetError("最近点对至少需要两个点")
        best = None
        for i in range(len(self._points)):
            for j in range(i + 1, len(self._points)):
                sq = _squared_distance(self._points[i], self._points[j])
                if best is None or sq < best[0]:
                    best = (sq, i, j)
        return best[1], best[2], math.sqrt(best[0])

    def radius_count(self, center, radius):
        """返回落在闭球内的点数。"""
        return len(self.range_query_ball(center, radius))


def nearest_pair(points):
    """便捷入口：对一批点求最近点对。"""
    return PointSet(points).nearest_pair()


def radius_count(points, center, radius):
    """便捷入口：对一批点统计落在闭球内的点数。"""
    return PointSet(points).radius_count(center, radius)
