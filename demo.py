"""quota 限流器演示。

第一段：单进程固定窗口——放行到上限后被拒，跨过窗口边界恢复。
第二段：注释里留了多实例共享配额的演示位子。
"""
from quota import FixedWindowLimiter


class ManualClock:
    """demo 用的手动时钟，逐段推进，不真正 sleep。"""

    def __init__(self, now=0.0):
        self.now = float(now)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def main():
    clock = ManualClock()
    lim = FixedWindowLimiter(limit=3, window=1.0, clock=clock)

    print("=== 单进程固定窗口（limit=3，窗口 1s） ===")
    for i in range(5):
        ok = lim.allow()
        print("  第 %d 次请求 -> %s，剩余 %d"
              % (i + 1, "放行" if ok else "拒绝", lim.remaining()))

    clock.advance(1.0)
    print("  秒表跨过窗口边界 -> %s" % ("放行" if lim.allow() else "拒绝"))

    # 第二段：多实例演示（留给实现者补）
    # 六个实例共用一份配额时，演示某个实例本地预领、用不完归还，
    # 以及它挂掉后额度被其他实例收回的场景。


if __name__ == "__main__":
    main()
