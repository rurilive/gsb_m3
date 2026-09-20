"""直方图演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：用注入时钟演示滑动窗口推进：旧样本被挤出、count 与分位数
随之变化、observe 返回挤出数、惰性清理与 compact、snapshot 分桶。
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

    demo_window()


class Clock:
    """可手动推进的演示时钟，替换默认的 time.monotonic。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def demo_window():
    clock = Clock()
    wh = Histogram(window_seconds=10, clock=clock)
    edges = [15, 50, 100]

    print("\n=== 滑动窗口（window=10s，注入时钟） ===")
    for v in (90, 95, 100):
        evicted = wh.observe(v)
    print(f"  t=0  观察 90/95/100，count={wh.count()}，末次挤出={evicted}")

    clock.advance(8)
    for v in (12, 18):
        evicted = wh.observe(v)
    print(f"  t=8  观察 12/18，count={wh.count()}，末次挤出={evicted}")

    evicted = wh.observe(15)
    print(f"  t=8  观察 15，count={wh.count()}，挤出={evicted}")
    ps = wh.percentiles(0.5, 0.99)
    print(f"       p50={ps[0.5]} p99={ps[0.99]}")

    clock.advance(2)
    print(f"  t=10 恰满窗口：旧样本仍在，count={wh.count()}（惰性，不清理）")

    clock.advance(0.001)
    print(f"  t>10 旧样本滑出：count={wh.count()}，物理仍保留 {len(wh._values)} 条")
    evicted = wh.observe(16)
    ps = wh.percentiles(0.5, 0.99)
    print(f"       observe 惰性清理挤出 {evicted} 条，p50={ps[0.5]} p99={ps[0.99]}")

    clock.advance(9)
    print(f"  t=19 t=8 一批滑出：count={wh.count()}，物理仍保留 {len(wh._values)} 条")
    removed = wh.compact()
    print(f"       compact 清理 {removed} 条，snapshot{edges}={wh.snapshot(edges)}（值等于边界归右桶）")


if __name__ == "__main__":
    main()
