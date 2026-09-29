"""Small demo for ratelib.

The first block exercises the shipped CountLimit limiter: a few calls are
allowed, then everything after the budget is rejected until reset. The second
block is a placeholder for the fixed window, token bucket and sliding window
work described in the task.
"""

from ratelib import CountLimit


class StepClock:
    """An injected integer clock advanced by hand, so the demo is repeatable."""

    def __init__(self, now=0):
        self.now = now

    def __call__(self):
        return self.now


def demo_count_limit():
    print("== CountLimit baseline ==")
    limiter = CountLimit(limit=3, clock=StepClock())
    for i in range(1, 6):
        print("call %d -> %s" % (i, "allow" if limiter.allow() else "reject"))
    print("used:", limiter.used())
    limiter.reset()
    print("after reset allow ->", limiter.allow())
    print("used:", limiter.used())


# TODO: 第二段演示（实现后补）——补一轮固定窗口、令牌桶与滑动窗口的演示：
# 用注入时钟推进时间，展示固定窗口滚动后计数自动清零、令牌桶按速率补充，
# 以及滑动窗口里旧记录过期后请求重新放行。此处暂不实现。


if __name__ == "__main__":
    demo_count_limit()
