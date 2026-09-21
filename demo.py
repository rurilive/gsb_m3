"""EventCounter 现状演示。

第一段：按事件时间累计计数，乱序到达不影响总和。
第二段：预留的滑动窗口与多窗口演示位子（见文末注释）。
"""

from winagg.sliding import MultiWindow, SlidingWindow
from winagg.window import EventCounter


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

    print("=== 滑动窗口：最近 10 秒计数（按事件时间推进）===")
    win = SlidingWindow(10, clock=clock)
    for ts, v in [(200.0, 2), (205.0, 3), (203.0, 1), (212.0, 4)]:
        clock.tick(1.0)
        win.add(ts, v)
        print(f"  add(ts={ts}, v={v}) -> bounds={win.bounds()} sum={win.sum()}")

    print("=== 乱序与迟到 ===")
    win.add(208.0, 5)   # 迟到但落在窗口内，计入
    print(f"  add(ts=208.0, v=5) 窗口内迟到 -> sum={win.sum()}")
    win.add(201.0, 7)   # 早于左边界 202.0，丢弃并记迟到数
    print(f"  add(ts=201.0, v=7) 早于左边界 -> sum={win.sum()} "
          f"late_count={win.late_count()} late_total={win.late_total()}")

    print("=== 关闭产出与相邻合并 ===")
    win.add(222.0, 1)   # [200,210) 被挤出，聚合成产出
    for c in win.closed():
        print(f"  closed [{c.start}, {c.end}) total={c.total} "
              f"count={c.count} closed_at={c.closed_at}")
    win.add(232.0, 1)   # [210,220) 也被挤出
    merged = win.merge_closed(200.0, 210.0)
    print(f"  merge [200,210)+[210,220) -> [{merged.start}, {merged.end}) "
          f"total={merged.total} count={merged.count}")

    print("=== 多窗口并行：10s 与 30s 各自独立淘汰 ===")
    multi = MultiWindow([10, 30], clock=clock)
    for ts in range(300, 330, 5):
        multi.add(float(ts), 1)
    print(f"  watermark=325 -> sum(10)={multi.sum(10)} "
          f"count(10)={multi.count(10)} | sum(30)={multi.sum(30)} "
          f"count(30)={multi.count(30)}")
    multi.add(340.0, 1)   # 短窗口的旧桶到点关闭，长窗口仍保留
    print(f"  推进到 340 -> 10s 已关闭 {len(multi.window(10).closed())} 个，"
          f"30s 已关闭 {len(multi.window(30).closed())} 个")


if __name__ == "__main__":
    main()
