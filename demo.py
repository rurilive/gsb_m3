"""geogrid 现状演示。

第一段：登记一批门店点位，按精确坐标查询。
第二段：全量遍历、球面距离与索引状态。
第三段：范围查询——矩形片区、三公里圆、跨 180 度线，附格子访问数。
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

    print("=== 范围查询 ===")
    rng = random.Random(7)
    city = PointIndex()
    for i in range(20000):
        city.add("shop-%d" % i, 31.0 + rng.random() * 0.5, 121.2 + rng.random() * 0.6)
    for i in range(5000):  # 热点商圈：两万家之外再挤五千家进同一个格子
        city.add("hot-%d" % i, 31.2304 + rng.random() * 0.019, 121.4737 + rng.random() * 0.019)

    def timed(query, *args):
        before = city.stats()["cells_visited"]
        start = time.perf_counter()
        hits = query(*args)
        elapsed = (time.perf_counter() - start) * 1000.0
        visited = city.stats()["cells_visited"] - before
        return hits, elapsed, visited

    hits, ms, visited = timed(city.box, 31.20, 31.26, 121.44, 121.50)
    print("  box(人民广场片区)   -> %d 家，%.2f ms，访问格子 %d" % (len(hits), ms, visited))
    hits, ms, visited = timed(city.circle, 31.2304, 121.4737, 3000.0)
    print("  circle(三公里竞品)  -> %d 家，%.2f ms，访问格子 %d" % (len(hits), ms, visited))

    pacific = PointIndex()
    pacific.add("fiji", -17.7, 179.9)
    pacific.add("samoa", -13.8, -171.8)
    pacific.add("tokyo", 35.7, 139.7)
    got = pacific.box(-20.0, 0.0, 170.0, -170.0)
    print("  box(跨 180 度线)    ->", got, "（东京不在片区里）")

    print("=== 格子码 ===")
    code = encode(31.2304, 121.4737, 6)
    print("  encode(31.2304, 121.4737, 6) ->", code)
    print("  decode -> (lat_min, lat_max, lon_min, lon_max) =",
          tuple(round(v, 5) for v in decode(code)))
    print("  neighbors ->", " ".join(neighbors(code)))

    print("=== 收尾: points=%d cells=%d ===" % (len(index), index.stats()["cells"]))


if __name__ == "__main__":
    main()
