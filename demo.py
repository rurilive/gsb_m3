"""直方图现状演示。

第一段：记录一批样本，输出 count 与常用分位数。
第二段：滑动窗口推进，展示旧样本被挤出、count/分位变化、
observe 返回值与 snapshot 分桶。
"""

from metricbox.histogram import Histogram

LATENCIES = [12, 18, 22, 25, 30, 31, 34, 40, 88, 120, 17, 19, 23, 27, 95]


class ManualClock:
    """演示用的可推进时钟（秒）。"""

    def __init__(self):
        self.now = 0.0

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

    print()
    print("=== 滑动窗口（window_seconds=60，注入时钟） ===")
    clock = ManualClock()
    wh = Histogram(window_seconds=60, clock=clock)

    print("-- t=0s：旧流量，延迟普遍偏高 --")
    old = [88, 95, 120, 102, 97]
    for v in old:
        wh.observe(v)
    print(f"  count = {wh.count()}，snapshot([25, 50, 100]) = "
          f"{wh.snapshot([25, 50, 100])}")

    print("-- t=60s：切流/扩容后，新流量延迟变低 --")
    clock.advance(60)
    for v in (12, 18, 22):
        wh.observe(v)  # 恰满 60s 的旧样本仍在窗口内，返回 0
    print(f"  count = {wh.count()}（旧样本恰好保留）")

    print("-- t=61s：旧样本滑出窗口 --")
    clock.advance(1)
    evicted = wh.observe(25)
    print(f"  observe 返回挤出数 = {evicted}")
    print(f"  count = {wh.count()}，compact() = {wh.compact()}")
    wps = wh.percentiles(0.5, 0.9, 0.99)
    for p in (0.5, 0.9, 0.99):
        print(f"  p{int(p * 100):02d} = {wps[p]}")
    print("  snapshot([25, 50, 100]) = "
          f"{wh.snapshot([25, 50, 100])}（值=25 归右桶 [25,50)）")


if __name__ == "__main__":
    main()
