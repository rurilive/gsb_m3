"""本地点位索引。

点按 cell_deg 根格网分桶；根格挤爆后按四叉自动分裂，深度有上限，
热点商圈的查询只翻开覆盖查询范围的叶子格，不退回全量扫描。
id 用任意可哈希对象，查询结果一律按登记顺序返回。
"""

import math

from .cells import DEFAULT_CELL_DEG, cell_of, check_cell_deg, per_degree
from .errors import DuplicateId, InvalidCoordinate, UnknownId
from .geo import EARTH_RADIUS_M, check_lat, check_lon, haversine_m, normalize_lon

DEFAULT_MAX_CELL_POINTS = 64
DEFAULT_MAX_DEPTH = 8


def _check_max_cell_points(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError("单格容量必须是正整数，收到 %r" % (value,))
    return value


def _check_max_depth(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError("分裂深度上限必须是非负整数，收到 %r" % (value,))
    return value


def _check_radius(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InvalidCoordinate("半径必须是数字，收到 %r" % (value,))
    value = float(value)
    if not math.isfinite(value) or value < 0.0:
        raise InvalidCoordinate("半径必须是非负有限数，收到 %r" % (value,))
    return value


def _lon_spans(lon_min, lon_max):
    """把经度区间折成 [-180, 180] 内的一到两段闭区间。

    两端之差达到 360 度视为整条纬带；否则归一化后 lon_min 更大时
    视为跨 ±180 度经线，拆成两段。
    """
    if lon_max - lon_min >= 360.0:
        return [(-180.0, 180.0)]
    lo = normalize_lon(lon_min)
    hi = normalize_lon(lon_max)
    if lo <= hi:
        return [(lo, hi)]
    return [(lo, 180.0), (-180.0, hi)]


class PointIndex:
    """经纬度点位索引：精确查询、矩形与圆形范围查询、全量遍历。"""

    def __init__(self, cell_deg=DEFAULT_CELL_DEG,
                 max_cell_points=DEFAULT_MAX_CELL_POINTS,
                 max_depth=DEFAULT_MAX_DEPTH):
        self.cell_deg = check_cell_deg(cell_deg)
        self.max_cell_points = _check_max_cell_points(max_cell_points)
        self.max_depth = _check_max_depth(max_depth)
        self._per_degree = per_degree(self.cell_deg)
        self._cells = {}
        self._internal = set()
        self._root_counts = {}
        self._points = {}
        self._order = {}
        self._seq = 0
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
        self._order[pid] = self._seq
        self._seq += 1
        root = self._root_key(lat, lon)
        self._root_counts[root] = self._root_counts.get(root, 0) + 1
        key = self._leaf_key(lat, lon)
        bucket = self._cells.setdefault(key, [])
        bucket.append(pid)
        if len(bucket) > self.max_cell_points:
            self._split(key)

    def remove(self, pid):
        """摘除点 pid，返回归一化后的坐标；不在索引里报 UnknownId。"""
        if pid not in self._points:
            raise UnknownId("索引里没有点 %r" % (pid,))
        lat, lon = self._points.pop(pid)
        del self._order[pid]
        root = self._root_key(lat, lon)
        count = self._root_counts[root] - 1
        if count:
            self._root_counts[root] = count
        else:
            del self._root_counts[root]
        key = self._leaf_key(lat, lon)
        bucket = self._cells[key]
        bucket.remove(pid)
        if not bucket:
            del self._cells[key]
        return (lat, lon)

    def at(self, lat, lon):
        """返回坐标与查询点完全相同的全部 id，按登记顺序。"""
        lat = check_lat(lat)
        lon = normalize_lon(check_lon(lon))
        self._lookups += 1
        target = (lat, lon)
        bucket = self._cells.get(self._leaf_key(lat, lon), ())
        if bucket:
            self._cells_visited += 1
        found = [pid for pid in bucket if self._points[pid] == target]
        if found:
            self._hits += 1
        return found

    def box(self, lat_min, lat_max, lon_min, lon_max):
        """矩形片区查询：返回落在闭区间里的 id，按登记顺序。

        纬度必须 lat_min <= lat_max；经度区间见 _lon_spans 的约定，
        跨 ±180 度经线的片区直接传 lon_min > lon_max（如 170 到 -170）。
        """
        lat_min = check_lat(lat_min)
        lat_max = check_lat(lat_max)
        raw_min = check_lon(lon_min)
        raw_max = check_lon(lon_max)
        if lat_min > lat_max:
            raise InvalidCoordinate(
                "lat_min 不能大于 lat_max，收到 %r 与 %r" % (lat_min, lat_max))
        found = self._collect(lat_min, lat_max, _lon_spans(raw_min, raw_max))
        return sorted(found, key=self._order.__getitem__)

    def circle(self, lat, lon, radius_m):
        """圆形查询：返回距 (lat, lon) 不超过 radius_m 米的 id，按登记顺序。

        先按球面外接矩形粗筛格子，再逐点用 haversine 距离判定；
        高纬度与跨 ±180 度经线的圆都按球面实际范围处理。
        """
        lat = check_lat(lat)
        lon = normalize_lon(check_lon(lon))
        radius_m = _check_radius(radius_m)
        angular = radius_m / EARTH_RADIUS_M
        delta_lat = math.degrees(angular)
        lat_min = max(-90.0, lat - delta_lat)
        lat_max = min(90.0, lat + delta_lat)
        if lat - delta_lat <= -90.0 or lat + delta_lat >= 90.0:
            spans = [(-180.0, 180.0)]
        else:
            ratio = math.sin(angular) / math.cos(math.radians(lat))
            delta_lon = math.degrees(math.asin(min(1.0, ratio)))
            spans = _lon_spans(lon - delta_lon, lon + delta_lon)
        found = self._collect(lat_min, lat_max, spans)
        result = [pid for pid in found
                  if haversine_m(lat, lon, *self._points[pid]) <= radius_m]
        result.sort(key=self._order.__getitem__)
        return result

    def scan(self):
        """按登记顺序返回全部 (pid, lat, lon)。"""
        return [(pid, lat, lon) for pid, (lat, lon) in self._points.items()]

    def __len__(self):
        return len(self._points)

    def __contains__(self, pid):
        return pid in self._points

    def stats(self):
        """索引状态快照；cells_visited 是查询累计翻开的叶子格数。"""
        max_cell = max((len(bucket) for bucket in self._cells.values()), default=0)
        return {
            "points": len(self._points),
            "cells": len(self._cells),
            "max_cell": max_cell,
            "lookups": self._lookups,
            "hits": self._hits,
            "cells_visited": self._cells_visited,
        }

    def _root_key(self, lat, lon):
        row, col = cell_of(lat, lon, self.cell_deg)
        return (min(row, 180 * self._per_degree - 1), col)

    def _quadrant(self, lat, lon, depth, row, col):
        size = self.cell_deg / (1 << depth)
        mid_lat = -90.0 + (row + 0.5) * size
        mid_lon = -180.0 + (col + 0.5) * size
        return (1 if lat >= mid_lat else 0, 1 if lon >= mid_lon else 0)

    def _leaf_key(self, lat, lon):
        row, col = self._root_key(lat, lon)
        depth = 0
        while (depth, row, col) in self._internal:
            drow, dcol = self._quadrant(lat, lon, depth, row, col)
            row = 2 * row + drow
            col = 2 * col + dcol
            depth += 1
        return (depth, row, col)

    def _split(self, key):
        depth = key[0]
        if depth >= self.max_depth:
            return
        bucket = self._cells.pop(key)
        self._internal.add(key)
        children = {}
        for pid in bucket:
            lat, lon = self._points[pid]
            children.setdefault(self._leaf_key(lat, lon), []).append(pid)
        for child_key, pids in children.items():
            self._cells[child_key] = pids
        for child_key, pids in children.items():
            if len(pids) > self.max_cell_points:
                self._split(child_key)

    def _collect(self, lat_min, lat_max, spans):
        found = set()
        for lon_min, lon_max in spans:
            self._collect_span(lat_min, lat_max, lon_min, lon_max, found)
        return found

    def _collect_span(self, lat_min, lat_max, lon_min, lon_max, found):
        pd = self._per_degree
        last_row = 180 * pd - 1
        last_col = 360 * pd - 1
        row_lo = min(max(0, int(math.floor((lat_min + 90.0) * pd))), last_row)
        row_hi = min(max(0, int(math.floor((lat_max + 90.0) * pd))), last_row)
        col_lo = min(max(0, int(math.floor((lon_min + 180.0) * pd))), last_col)
        col_hi = min(max(0, int(math.floor((lon_max + 180.0) * pd))), last_col)
        if (row_hi - row_lo + 1) * (col_hi - col_lo + 1) <= len(self._root_counts):
            for row in range(row_lo, row_hi + 1):
                for col in range(col_lo, col_hi + 1):
                    self._descend(0, row, col, lat_min, lat_max,
                                  lon_min, lon_max, found)
        else:
            for row, col in self._root_counts:
                if row_lo <= row <= row_hi and col_lo <= col <= col_hi:
                    self._descend(0, row, col, lat_min, lat_max,
                                  lon_min, lon_max, found)

    def _descend(self, depth, row, col, lat_min, lat_max, lon_min, lon_max, found):
        key = (depth, row, col)
        if key in self._internal:
            size = self.cell_deg / (1 << (depth + 1))
            base_lat = -90.0 + row * 2.0 * size
            base_lon = -180.0 + col * 2.0 * size
            for drow in (0, 1):
                child_lat = base_lat + drow * size
                if child_lat > lat_max or child_lat + size < lat_min:
                    continue
                for dcol in (0, 1):
                    child_lon = base_lon + dcol * size
                    if child_lon > lon_max or child_lon + size < lon_min:
                        continue
                    self._descend(depth + 1, 2 * row + drow, 2 * col + dcol,
                                  lat_min, lat_max, lon_min, lon_max, found)
            return
        bucket = self._cells.get(key)
        if not bucket:
            return
        self._cells_visited += 1
        for pid in bucket:
            lat, lon = self._points[pid]
            if lat_min <= lat <= lat_max and lon_min <= lon <= lon_max:
                found.add(pid)
