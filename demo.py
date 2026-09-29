"""ListTimer 现状演示。

第一段：注册若干任务，推进时钟，看到期任务被取走；取消一个任务后不再触发。
第二段：预留的分层时间轮演示位子（见文末注释）。
"""

from wheelish.timer import ListTimer


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def main():
    print("=== 列表式定时器 ===")
    c = FakeClock()
    t = ListTimer(clock=c)
    t.register(2, payload="a")
    t.register(4, payload="b")
    doomed = t.register(4, payload="c")
    doomed.cancel()
    print(f"  注册 3 个任务，取消 1 个，当前 size={t.size}")
    c.advance(2)
    print(f"  tick(2) 到期 -> {[h.payload for h in t.tick(2)]}")
    c.advance(2)
    print(f"  tick(4) 到期 -> {[h.payload for h in t.tick(4)]}")
    print(f"  剩余 size={t.size}")

    # TODO(分层时间轮): 在 wheelish/wheel.py 实现 HierarchicalTimer 后，在这里加一段演示：
    # 多级轮的分层挂载、跨级降级、同刻按注册顺序触发，以及大量任务下的复杂度与内存回收。


if __name__ == "__main__":
    main()