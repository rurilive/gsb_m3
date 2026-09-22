"""geogrid 演示。

第一段：登记一批门店点位，按精确坐标查询。
第二段：全量遍历、球面距离与索引状态。
第三段：geocode 格子码的编解码与邻格。
第四段：box/circle 范围查询，对照全量 scan 的耗时与翻格数。
"""

import random
import time

from geogrid import PointIndex, decode, encode, neighbors
from geogrid.geo import haversine_m


def main():
    index = PointIndex()
    shops = [
        ("s-1001", 31.2304, 121.4737),
        ("s-1002", 31.2304, 121.4737),
        ("s-1003", 31.2319, 121.4699),
        ("s-1004", 39.9042, 116.4074),
        ("s-1005", -33.8688, 151.2093),
    ]
    for pid, lat, lon in shops:
        index.add(pid, lat, lon)

    print("=== 精确坐标查询 ===")
    print("  at(31.2304, 121.4737) ->", index.at(31.2304, 121.4737))
    print("  at(31.2304, 121.4738) ->", index.at(31.2304, 121.4738))
    print("  同一坐标的两家店一起返回，差一点坐标的不返回")

    print("=== 全量遍历与状态 ===")
    for pid, lat, lon in index.scan():
        print("  %-7s %.4f, %.4f" % (pid, lat, lon))
    print("  上海到北京 %.0f 米" % haversine_m(31.2304, 121.4737, 39.9042, 116.4074))
    print("  stats:", index.stats())

    print("=== 格子码 geocode ===")
    code = encode(31.2304, 121.4737, 7)
    cell = decode(code)
    print("  encode(31.2304, 121.4737, 7) ->", code)
    print("  decode 范围: lat %.5f~%.5f lon %.5f~%.5f"
          % (cell.lat_min, cell.lat_max, cell.lon_min, cell.lon_max))
    coarse = decode(code[:4])
    print("  截断到 4 位 %s: lat %.3f~%.3f lon %.3f~%.3f（包住原格子）"
          % (code[:4], coarse.lat_min, coarse.lat_max, coarse.lon_min, coarse.lon_max))
    print("  邻格:", " ".join(neighbors(code)))

    print("=== 范围查询 box / circle ===")
    rng = random.Random(20260922)
    city = PointIndex()
    for i in range(100000):
        if i < 15000:  # 热点商圈：人民广场周边两公里内密集铺点
            lat = 31.2304 + rng.uniform(-0.01, 0.01)
            lon = 121.4737 + rng.uniform(-0.01, 0.01)
        else:
            lat = 31.2304 + rng.uniform(-0.5, 0.5)
            lon = 121.4737 + rng.uniform(-0.5, 0.5)
        city.add("n%06d" % i, lat, lon)
    print("  全城 %d 家门店，%d 个叶子格" % (len(city), city.stats()["cells"]))

    def report(label, query):
        before = city.stats()["cells_visited"]
        start = time.perf_counter()
        ids = query()
        ms = (time.perf_counter() - start) * 1000.0
        visited = city.stats()["cells_visited"] - before
        print("  %s: %d 家, %.2f ms, 翻格 %d" % (label, len(ids), ms, visited))
        return ids

    report("box 人民广场片区", lambda: city.box(31.20, 31.26, 121.44, 121.50))
    report("circle 三公里内竞品", lambda: city.circle(31.2304, 121.4737, 3000.0))

    start = time.perf_counter()
    brute = [pid for pid, lat, lon in city.scan()
             if haversine_m(31.2304, 121.4737, lat, lon) <= 3000.0]
    ms = (time.perf_counter() - start) * 1000.0
    print("  对照：全量 scan 逐点算距离 %d 家, %.2f ms" % (len(brute), ms))

    print("=== 收尾: points=%d cells=%d ===" % (len(index), index.stats()["cells"]))


if __name__ == "__main__":
    main()
