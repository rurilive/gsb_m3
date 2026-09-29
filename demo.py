"""FixedWindowLimiter 现状演示。

第一段：固定窗口下按键放行与窗口到点复位。
第二段：预留的多策略演示位子（见文末注释）。
"""

from ratelimit.limiter import FixedWindowLimiter


class FakeClock:
    def __init__(self, t=0.0):
        self.t = t

    def __call__(self):
        return self.t

    def advance(self, dt):
        self.t += dt


def main():
    print("=== 固定窗口 ===")
    c = FakeClock()
    rl = FixedWindowLimiter(3, 10, clock=c)
    for i in range(4):
        print(f"  allow() -> {rl.allow('u1')}  remaining={rl.remaining('u1')}")
    c.advance(10)
    print(f"  窗口到点 -> allow() = {rl.allow('u1')}")

    # TODO(策略改造): 多策略实现后，在这里加一段演示：
    # 令牌桶与滑动窗口各自的放行曲线，以及 near-limit 下两者的差异。


if __name__ == "__main__":
    main()
