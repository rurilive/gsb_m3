"""LoopTimer 现状演示。

第一段：注册若干延迟任务，推进注入时钟，看到点回调被同步调用；取消一个
任务后不再触发。
第二段：预留的防抖与节流演示位子（见文末注释）。
"""

from timectl.timer import LoopTimer


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def main():
    print("=== 朴素循环触发定时器 ===")
    c = FakeClock()
    t = LoopTimer(clock=c)
    seen = []
    t.register(2, lambda: seen.append("a"))
    t.register(4, lambda: seen.append("b"))
    doomed = t.register(4, lambda: seen.append("c"))
    doomed.cancel()
    print("  注册 3 个任务，取消 1 个，当前 size=%d" % t.size)
    c.advance(2)
    t.tick(2)
    print("  tick(2) 后已触发: %s" % (seen,))
    c.advance(2)
    t.tick(4)
    print("  tick(4) 后已触发: %s" % (seen,))
    print("  剩余 size=%d" % t.size)

    print("=== 连打不合并 ===")
    c2 = FakeClock()
    t2 = LoopTimer(clock=c2)
    hits = []
    for _ in range(5):
        t2.register(1, lambda: hits.append(1))
    c2.advance(1)
    t2.tick(1)
    print("  同一时刻注册 5 个，tick 后触发 %d 次（无防抖，原样放大）" % len(hits))

    # TODO(防抖与节流): 在 timectl 里补出统一的定时器调度器之后，在这里加一段演示：
    # 用同一注入时钟分别展示防抖与节流：对同一 key 连续触发多次，防抖要等最后一次
    # 之后静默满 wait 才回调一次，中途再次触发会把计时重置；节流在 interval 内至多
    # 回调一次，多余的调用按前沿或后沿口径被丢弃或被顺延，并打印两者的触发次数对比。


if __name__ == "__main__":
    main()
