"""直方图现状演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：滑动窗口演示，用注入时钟模拟时间流逝。
"""

from metricbox.histogram import Histogram

LATENCIES = [12, 18, 22, 25, 30, 31, 34, 40, 88, 120, 17, 19, 23, 27, 95]


def main():
    h = Histogram()
    for v in LATENCIES:
        h.observe(v)

    print("=== 直方图现状（全量样本） ===")
    print(f"  count = {h.count()}")
    ps = h.percentiles(0.5, 0.9, 0.99)
    for p in (0.5, 0.9, 0.99):
        print(f"  p{int(p * 100):02d} = {ps[p]}")

    print()
    print("=== 滑动窗口（window_seconds=60，注入时钟） ===")
    now = [0.0]
    w = Histogram(window_seconds=60, clock=lambda: now[0])
    for v in LATENCIES:
        w.observe(v)
    print(f"  t=0    记录 {len(LATENCIES)} 个样本, count = {w.count()}")

    now[0] += 60
    print(f"  t=+60s 恰满窗口仍算窗口内: count = {w.count()}")

    now[0] += 1
    evicted = w.observe(40)
    print(f"  t=+61s observe(40) 挤出 {evicted} 个旧样本, count = {w.count()}")
    print(f"         p50 = {w.percentiles(0.5)[0.5]}（不再被旧样本拖住）")

    w.observe(55)
    w.observe(70)
    print(f"  snapshot([50, 60]) = {w.snapshot([50, 60])}  # 值等于边界归右桶")
    print(f"  compact() = {w.compact()}（窗口内样本无需清理）")


if __name__ == "__main__":
    main()
