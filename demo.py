"""直方图现状演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：注入时钟推进，演示滑动窗口挤出旧样本。
"""

from metricbox.histogram import Histogram

LATENCIES = [12, 18, 22, 25, 30, 31, 34, 40, 88, 120, 17, 19, 23, 27, 95]


class FakeClock:
    """可手动推进的时钟，用于演示窗口滑动。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, dt):
        self.now += dt


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
    clock = FakeClock()
    w = Histogram(window_seconds=60, clock=clock)
    for v in LATENCIES:
        w.observe(v)
    print(f"  t={clock.now:5.1f}s  count = {w.count()}, "
          f"p99 = {w.percentiles(0.99)[0.99]}")

    clock.advance(61)  # 旧样本全部滑出窗口
    evicted = w.observe(18)
    print(f"  t={clock.now:5.1f}s  observe(18) 挤出 {evicted} 个旧样本")
    for v in (19, 21, 23, 25):
        w.observe(v)
    print(f"  t={clock.now:5.1f}s  count = {w.count()}, "
          f"p50 = {w.percentiles(0.5)[0.5]}, "
          f"p99 = {w.percentiles(0.99)[0.99]}")
    print(f"  snapshot([20, 30]) = {w.snapshot([20, 30])}")
    clock.advance(61)
    print(f"  t={clock.now:5.1f}s  compact() 清理 {w.compact()} 个过期样本, "
          f"count = {w.count()}")


if __name__ == "__main__":
    main()
