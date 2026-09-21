"""EventCounter 现状演示。

第一段：按事件时间累计计数，乱序到达不影响总和。
第二段：预留的滑动窗口与多窗口演示位子（见文末注释）。
"""

from winagg.window import EventCounter
from winagg.sliding import MultiWindowCounter, WindowedCounter


class FakeClock:
    """可手动推进的假时钟。"""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def tick(self, dt):
        self.now += dt


def main():
    clock = FakeClock()
    counter = EventCounter(clock=clock)

    print("=== 按事件时间累计计数 ===")
    for ts, v in [(100.0, 2), (103.0, 5), (101.0, 1)]:
        clock.tick(1.0)
        total = counter.add(ts, v)
        print(f"  add(ts={ts}, v={v}) -> total={total}")
    print(f"  count={counter.count()} span={counter.span()} "
          f"last_arrival={counter.last_arrival()}")

    print("=== 滑动窗口：按事件时间推进 ===")
    win = WindowedCounter(10, clock=clock, late_policy="count")
    for ts, v in [(100.0, 2), (105.0, 3), (112.0, 1)]:
        clock.tick(1.0)
        win.add(ts, v)
        print(f"  add(ts={ts}, v={v}) -> 窗口={win.current_window()} "
              f"窗口和={win.window_total()}")
    print(f"  已关闭窗口产出: {win.outputs()}")

    print("=== 迟到事件 ===")
    win.add(108.0, 4)   # 水位线已到 112，[100,110) 已关闭，判迟到
    print(f"  add(ts=108.0, v=4) 被判迟到: late_count={win.late_count()} "
          f"late_total={win.late_total()}")
    win.add(115.0, 2)   # 开口窗口内，计入
    print(f"  add(ts=115.0, v=2) -> 窗口和={win.window_total()}")

    print("=== 多窗口并行 ===")
    multi = MultiWindowCounter([10, 30], clock=clock)
    for ts in [200.0, 205.0, 212.0, 225.0]:
        clock.tick(1.0)
        multi.add(ts, 1)
    print(f"  各窗口当前和: {multi.totals()}")
    print(f"  10s 窗口已关闭产出: {multi.window(10).outputs()}")
    print(f"  30s 窗口已关闭产出: {multi.window(30).outputs()}")

    print("=== 相邻已关闭窗口合并 ===")
    w10 = multi.window(10)
    merged = w10.merge(200.0, 210.0)
    print(f"  合并 [200,210)+[210,220) -> {merged}")
    print(f"  合并后产出缓冲: {w10.outputs()}")


if __name__ == "__main__":
    main()
