"""直方图现状演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：注入时钟推进滑动窗口，展示旧样本被挤出。
"""

from metricbox.histogram import Histogram

LATENCIES = [12, 18, 22, 25, 30, 31, 34, 40, 88, 120, 17, 19, 23, 27, 95]


class FakeClock:
    """可手动推进的时钟，用于演示窗口滑动。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def main():
    h = Histogram()
    for v in LATENCIES:
        h.observe(v)

    print("=== 直方图现状（全量样本） ===")
    print(f"  count = {h.count()}")
    ps = h.percentiles(0.5, 0.9, 0.99)
    for p in (0.5, 0.9, 0.99):
        print(f"  p{int(p * 100):02d} = {ps[p]}")

    print("=== 滑动窗口（window_seconds=30，注入时钟） ===")
    clock = FakeClock()
    w = Histogram(window_seconds=30, clock=clock)
    for v in LATENCIES:
        w.observe(v)
    print(f"  t=0   count={w.count()} p99={w.percentiles(0.99)[0.99]:.1f}")

    clock.advance(31)  # 旧样本全部滑出窗口
    evicted = w.observe(20)
    print(f"  t=31  observe(20) 挤出 {evicted} 个旧样本，count={w.count()}")
    for v in (22, 25, 18, 21):
        w.observe(v)
    print(f"  t=31  新样本后 p99={w.percentiles(0.99)[0.99]:.1f}（不再被旧样本拖住）")
    print(f"  t=31  snapshot([20, 30, 50]) = {w.snapshot([20, 30, 50])}")

    clock.advance(31)
    print(f"  t=62  compact() 清理 {w.compact()} 个过期样本，count={w.count()}")


if __name__ == "__main__":
    main()
