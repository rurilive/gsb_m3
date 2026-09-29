"""quadrex 的现有实现：顺序扫描的点集。

点存在一个列表里，按矩形查询时逐个点判断是否落在范围内。没有树、没有划分、
没有层次，数据量大时每次查询都要扫过全部点。当前只支持矩形查询。
"""

import math


class QuadError(Exception):
    """quadrex 抛出的一切异常的共同基类。

    非法坐标、非法矩形等入参问题都从这里派生，调用方可以只捕获本类。
    """


def _check_number(value, name):
    """校验一个坐标是有限的实数，否则 fail fast。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QuadError(f"{name} must be a real number, got {type(value).__name__}")
    if not math.isfinite(value):
        raise QuadError(f"{name} must be finite, got {value!r}")
    return value


def _check_point(x, y):
    return (_check_number(x, "x"), _check_number(y, "y"))


def _check_rect(xmin, ymin, xmax, ymax):
    _check_number(xmin, "xmin")
    _check_number(ymin, "ymin")
    _check_number(xmax, "xmax")
    _check_number(ymax, "ymax")
    if xmin > xmax or ymin > ymax:
        raise QuadError("rectangle is empty by bounds: min must not exceed max")


class LinearPoints:
    """顺序扫描的点集。

    点按插入顺序存列表，重复点只保留一份；矩形查询逐个点比较，命中的点按
    坐标 (x, y) 升序返回，边界一律算命中。空集与覆盖全平面的矩形都能处理。
    """

    def __init__(self, points=None):
        self._points = []
        if points is not None:
            for p in points:
                self.insert(p[0], p[1])

    def insert(self, x, y):
        """插入一个点；已存在则不动并返回 False，新加入返回 True。"""
        pt = _check_point(x, y)
        if pt in self._points:
            return False
        self._points.append(pt)
        return True

    def remove(self, x, y):
        """删掉一个点；存在并删除返回 True，不存在返回 False。"""
        pt = _check_point(x, y)
        if pt in self._points:
            self._points.remove(pt)
            return True
        return False

    def contains(self, x, y):
        """点是否在集合里。"""
        return _check_point(x, y) in self._points

    def query_rect(self, xmin, ymin, xmax, ymax):
        """返回落在闭矩形内的全部点，按 (x, y) 升序，边界算命中。"""
        _check_rect(xmin, ymin, xmax, ymax)
        hits = [
            (x, y)
            for (x, y) in self._points
            if xmin <= x <= xmax and ymin <= y <= ymax
        ]
        hits.sort()
        return hits

    def points(self):
        """当前全部点，按 (x, y) 升序。"""
        return sorted(self._points)

    def __len__(self):
        return len(self._points)

    def __contains__(self, pt):
        return tuple(pt) in self._points
