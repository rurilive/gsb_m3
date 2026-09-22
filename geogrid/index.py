"""本地点位索引。

点先按固定边长格网分桶；桶里点太多时按象限自动分裂成四叉树，深度有
上限，热点商圈查询不会拖回线性扫。at 精确查询下钻到目标叶子；box /
circle 范围查询先做格子粗筛再逐点精判。id 用任意可哈希对象，查询
结果一律按登记顺序返回，与全量扫描逐点判定一致。
"""

import math

from .cells import DEFAULT_CELL_DEG, cell_of, cell_row, cell_col, check_cell_deg, per_degree
from .errors import DuplicateId, InvalidCoordinate, UnknownId
from .geo import EARTH_RADIUS_M, check_lat, check_lon, haversine_m, normalize_lon

DEFAULT_MAX_CELL_POINTS = 64
DEFAULT_MAX_DEPTH = 8


def _check_positive_int(name, value, allow_zero=False):
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("%s 必须是整数，收到 %r" % (name, value))
    if value < 0 or (value == 0 and not allow_zero):
        raise ValueError("%s 必须是正整数，收到 %r" % (name, value))
    return value


def _check_radius(radius_m):
    if isinstance(radius_m, bool) or not isinstance(radius_m, (int, float)):
        raise InvalidCoordinate("半径必须是数字，收到 %r" % (radius_m,))
    value = float(radius_m)
    if not math.isfinite(value) or value < 0.0:
        raise InvalidCoordinate("半径必须是非负有限数，收到 %r" % (radius_m,))
    return value


def _quadrant(node, lat, lon):
    """点落在 node 的哪个象限：bit0 东、bit1 北。"""
    idx = 0
    if lon >= (node.lon_min + node.lon_max) / 2.0:
        idx |= 1
    if lat >= (node.lat_min + node.lat_max) / 2.0:
        idx |= 2
    return idx


def _lon_in_spans(lon, lon_spans):
    return any(lo <= lon <= hi for lo, hi in lon_spans)


def _lon_overlap(lon_min, lon_max, lon_spans):
    return any(lon_min <= hi and lo <= lon_max for lo, hi in lon_spans)


class _Cell:
    """格网节点：叶子存 bucket，内部节点存四个象限孩子。"""

    __slots__ = ("lat_min", "lat_max", "lon_min", "lon_max", "bucket", "children", "count")

    def __init__(self, lat_min, lat_max, lon_min, lon_max):
        self.lat_min = lat_min
        self.lat_max = lat_max
        self.lon_min = lon_min
        self.lon_max = lon_max
        self.bucket = []
        self.children = None
        self.count = 0


class PointIndex:
    """经纬度点位集合：精确坐标查询、范围查询加全量遍历。"""

    def __init__(self, cell_deg=DEFAULT_CELL_DEG, max_cell_points=DEFAULT_MAX_CELL_POINTS,
                 max_depth=DEFAULT_MAX_DEPTH):
        self.cell_deg = check_cell_deg(cell_deg)
        self.max_cell_points = _check_positive_int("max_cell_points", max_cell_points)
        self.max_depth = _check_positive_int("max_depth", max_depth, allow_zero=True)
        self._cells = {}
        self._points = {}
        self._seq = {}
        self._next_seq = 0
        self._lookups = 0
        self._hits = 0
        self._cells_visited = 0

    def add(self, pid, lat, lon):
        """登记点 pid；经度归一化后入库，重复 id 报 DuplicateId。"""
        lat = check_lat(lat)
        lon = normalize_lon(check_lon(lon))
        if pid in self._points:
            raise DuplicateId("点 %r 已在索引里" % (pid,))
        self._points[pid] = (lat, lon)
        self._seq[pid] = self._next_seq
        self._next_seq += 1
        key = cell_of(lat, lon, self.cell_deg)
        cell = self._cells.get(key)
        if cell is None:
            row, col = key
            deg = self.cell_deg
            cell = _Cell(row * deg - 90.0, (row + 1) * deg - 90.0,
                         col * deg - 180.0, (col + 1) * deg - 180.0)
            self._cells[key] = cell
        self._insert(cell, pid, lat, lon)

    def _insert(self, cell, pid, lat, lon):
        node = cell
        depth = 0
        node.count += 1
        while node.children is not None:
            node = node.children[_quadrant(node, lat, lon)]
            node.count += 1
            depth += 1
        node.bucket.append(pid)
        if len(node.bucket) > self.max_cell_points and depth < self.max_depth:
            self._split(node)

    def _split(self, node):
        lat_mid = (node.lat_min + node.lat_max) / 2.0
        lon_mid = (node.lon_min + node.lon_max) / 2.0
        node.children = [
            _Cell(node.lat_min, lat_mid, node.lon_min, lon_mid),
            _Cell(node.lat_min, lat_mid, lon_mid, node.lon_max),
            _Cell(lat_mid, node.lat_max, node.lon_min, lon_mid),
            _Cell(lat_mid, node.lat_max, lon_mid, node.lon_max),
        ]
        for pid in node.bucket:
            plat, plon = self._points[pid]
            child = node.children[_quadrant(node, plat, plon)]
            child.bucket.append(pid)
            child.count += 1
        node.bucket = None

    def remove(self, pid):
        """摘除点 pid，返回归一化后的坐标；不在索引里报 UnknownId。"""
        if pid not in self._points:
            raise UnknownId("索引里没有点 %r" % (pid,))
        lat, lon = self._points.pop(pid)
        del self._seq[pid]
        key = cell_of(lat, lon, self.cell_deg)
        path = []
        node = self._cells[key]
        while True:
            path.append(node)
            if node.children is None:
                break
            node = node.children[_quadrant(node, lat, lon)]
        node.bucket.remove(pid)
        for entry in path:
            entry.count -= 1
        for entry in reversed(path):
            if entry.children is not None and all(child.count == 0 for child in entry.children):
                entry.children = None
                entry.bucket = []
        if path[0].count == 0:
            del self._cells[key]
        return (lat, lon)

    def at(self, lat, lon):
        """返回坐标与查询点完全相同的全部 id，按登记顺序。"""
        lat = check_lat(lat)
        lon = normalize_lon(check_lon(lon))
        self._lookups += 1
        target = (lat, lon)
        node = self._cells.get(cell_of(lat, lon, self.cell_deg))
        while node is not None and node.children is not None:
            node = node.children[_quadrant(node, lat, lon)]
        bucket = node.bucket if node is not None else ()
        found = [pid for pid in bucket if self._points[pid] == target]
        if found:
            self._hits += 1
        return found

    def box(self, lat_min, lat_max, lon_min, lon_max):
        """矩形片区内的全部 id，按登记顺序。

        纬度必须 lat_min <= lat_max；经度从 lon_min 向东走到 lon_max，
        跨 180 度线按环绕处理，跨度满 360 度视为全球。
        """
        lat_min = check_lat(lat_min)
        lat_max = check_lat(lat_max)
        lon_min = check_lon(lon_min)
        lon_max = check_lon(lon_max)
        if lat_min > lat_max:
            raise InvalidCoordinate("lat_min 不能大于 lat_max：%r > %r" % (lat_min, lat_max))
        self._lookups += 1
        lon_spans = self._lon_spans(lon_min, lon_max)

        def accept(lat, lon):
            return lat_min <= lat <= lat_max and _lon_in_spans(lon, lon_spans)

        matched = self._range_query(lat_min, lat_max, lon_spans, accept)
        if matched:
            self._hits += 1
        return matched

    def circle(self, lat, lon, radius_m):
        """半径 radius_m 米内的全部 id，按登记顺序。

        先按圆的外接矩形做格子粗筛，再按球面距离逐点精判；高纬度与
        跨 180 度线的圆都能盖全。
        """
        lat = check_lat(lat)
        lon = normalize_lon(check_lon(lon))
        radius = _check_radius(radius_m)
        self._lookups += 1
        delta = radius / EARTH_RADIUS_M
        lat_delta = math.degrees(delta)
        lat_min = max(-90.0, lat - lat_delta)
        lat_max = min(90.0, lat + lat_delta)
        cos_center = math.cos(math.radians(lat))
        if lat_delta >= 180.0 or cos_center <= math.sin(delta):
            # 圆盖住极点或半个地球，经度不再收缩
            lon_spans = [(-180.0, 180.0)]
        else:
            # 圆上经度最大跨度：asin(sin(delta) / cos(lat))
            lon_delta = math.degrees(math.asin(math.sin(delta) / cos_center))
            lon_spans = self._lon_spans(lon - lon_delta, lon + lon_delta)

        def accept(plat, plon):
            return haversine_m(plat, plon, lat, lon) <= radius

        matched = self._range_query(lat_min, lat_max, lon_spans, accept)
        if matched:
            self._hits += 1
        return matched

    @staticmethod
    def _lon_spans(lon_min, lon_max):
        """经度区间折成一到两段不跨 180 度线的闭区间。"""
        if lon_max - lon_min >= 360.0:
            return [(-180.0, 180.0)]
        lo = normalize_lon(lon_min)
        hi = normalize_lon(lon_max)
        if lo <= hi:
            return [(lo, hi)]
        return [(lo, 180.0), (-180.0, hi)]

    def _range_query(self, lat_min, lat_max, lon_spans, accept):
        matched = []
        for cell in self._candidate_cells(lat_min, lat_max, lon_spans):
            self._descend(cell, lat_min, lat_max, lon_spans, accept, matched)
        matched.sort(key=self._seq.__getitem__)
        return matched

    def _candidate_cells(self, lat_min, lat_max, lon_spans):
        pd = per_degree(self.cell_deg)
        ncols = 360 * pd
        row0 = cell_row(lat_min, self.cell_deg)
        row1 = cell_row(lat_max, self.cell_deg)
        cols = set()
        for lo, hi in lon_spans:
            col0 = cell_col(lo, self.cell_deg)
            col1 = ncols - 1 if hi >= 180.0 else cell_col(hi, self.cell_deg)
            col = col0
            while True:
                cols.add(col)
                if col == col1:
                    break
                col = (col + 1) % ncols
        if (row1 - row0 + 1) * len(cols) <= len(self._cells):
            for row in range(row0, row1 + 1):
                for col in cols:
                    cell = self._cells.get((row, col))
                    if cell is not None:
                        yield cell
        else:
            for (row, col), cell in self._cells.items():
                if row0 <= row <= row1 and col in cols:
                    yield cell

    def _descend(self, node, lat_min, lat_max, lon_spans, accept, matched):
        self._cells_visited += 1
        if node.children is None:
            for pid in node.bucket:
                lat, lon = self._points[pid]
                if accept(lat, lon):
                    matched.append(pid)
            return
        for child in node.children:
            if child.count == 0:
                continue
            if child.lat_min > lat_max or child.lat_max < lat_min:
                continue
            if not _lon_overlap(child.lon_min, child.lon_max, lon_spans):
                continue
            self._descend(child, lat_min, lat_max, lon_spans, accept, matched)

    def scan(self):
        """按登记顺序返回全部 (pid, lat, lon)。"""
        return [(pid, lat, lon) for pid, (lat, lon) in self._points.items()]

    def __len__(self):
        return len(self._points)

    def __contains__(self, pid):
        return pid in self._points

    def stats(self):
        """索引状态快照。"""
        max_cell = 0
        stack = list(self._cells.values())
        while stack:
            node = stack.pop()
            if node.children is not None:
                stack.extend(node.children)
            elif len(node.bucket) > max_cell:
                max_cell = len(node.bucket)
        return {
            "points": len(self._points),
            "cells": len(self._cells),
            "max_cell": max_cell,
            "lookups": self._lookups,
            "hits": self._hits,
            "cells_visited": self._cells_visited,
        }
