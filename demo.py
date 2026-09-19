"""直方图现状演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：注释里留了滑动窗口演示的位子。
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
    print("=== 滑动窗口（window_seconds=30，注入时钟） ===")
    now = [0.0]
    w = Histogram(window_seconds=30, clock=lambda: now[0])

    for v in (120, 95, 88):  # 切流前的高延迟
        w.observe(v)
    print(f"  t=0s  旧样本 120/95/88: count={w.count()}, "
          f"p50={w.percentiles(0.5)[0.5]}")

    now[0] = 20
    for v in (12, 15, 18):  # 切流后的新常态
        w.observe(v)
    print(f"  t=20s 新样本 12/15/18:  count={w.count()}, "
          f"p50={w.percentiles(0.5)[0.5]}（旧样本仍在窗口内）")

    now[0] = 31  # t=0 的样本已 31s，滑出 30s 窗口
    evicted = w.observe(14)
    print(f"  t=31s observe(14) 挤出 {evicted} 个旧样本: count={w.count()}, "
          f"p50={w.percentiles(0.5)[0.5]}")
    print(f"  t=31s snapshot([20, 50, 100]) = {w.snapshot([20, 50, 100])}")

    now[0] = 51  # t=20 的样本也过期
    print(f"  t=51s compact() 清理 {w.compact()} 个，count={w.count()}")


if __name__ == "__main__":
    main()
