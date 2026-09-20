"""quota 限流器演示。

第一段：单进程固定窗口——放行到上限后被拒，跨过窗口边界恢复。
第二段：六实例共享一份配额——本地预领、用不完归还、掉线被回收。
"""
from quota import FAIL_OPEN, FixedWindowLimiter, MemoryStore, SharedFixedWindowLimiter


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

    print()
    print("=== 六实例共享配额（总量 limit=6，窗口 60s，每批预领 2） ===")
    store_clock = ManualClock(1000.0)
    store = MemoryStore(window=60.0, clock=store_clock)

    def make_instance(iid, skew=0.0):
        return SharedFixedWindowLimiter(
            store,
            limit=6,
            window=60.0,
            batch_size=2,
            lease_ttl=10.0,
            instance_id=iid,
            clock=ManualClock(1000.0 + skew),
        )

    instances = [make_instance("inst-%d" % i, skew=(i - 3) * 0.8)
                 for i in range(6)]

    def each_requests(n):
        for r in range(n):
            verdicts = [("放行" if lim.allow("user-x") else "拒绝")
                        for lim in instances]
            print("  第 %d 轮：%s" % (r + 1, "，".join(
                "%s=%s" % (lim.instance_id, v)
                for lim, v in zip(instances, verdicts))))

    each_requests(1)
    print("  存储记账：窗口已领 %d（六台预领的总和，含已花/在手里）"
          % store.leased("user-x"))

    print("  -- inst-0 优雅下线，手里没花完的 1 个额度立即归还 --")
    instances[0].shutdown("user-x")
    print("  inst-5 立刻补领 -> %s"
          % ("放行" if instances[5].allow("user-x") else "拒绝"))

    print("  -- inst-1 直接掉线（不归还），前 10s 租约未过期别人领不到 --")
    store_clock.advance(9.9)
    print("  inst-5 补领 -> %s（租约还差 0.1s）"
          % ("放行" if instances[5].allow("user-x") else "拒绝"))
    store_clock.advance(0.1)
    print("  inst-5 补领 -> %s（租约到期，掉线者未花额度已回收）"
          % ("放行" if instances[5].allow("user-x") else "拒绝"))

    print()
    print("=== 存储抖动的两种口径（同一时刻按 key 各配各的） ===")

    class FlakyStore(MemoryStore):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.down = False

        def acquire(self, *args, **kwargs):
            if self.down:
                raise RuntimeError("存储抖动")
            return super().acquire(*args, **kwargs)

    flaky = FlakyStore(window=60.0, clock=ManualClock(1000.0))
    opener = SharedFixedWindowLimiter(
        flaky, limit=6, window=60.0, fail_policy=FAIL_OPEN,
        instance_id="open", clock=ManualClock(1000.0))
    closer = SharedFixedWindowLimiter(
        flaky, limit=6, window=60.0, fail_policy="fail_closed",
        instance_id="closed", clock=ManualClock(1000.0))
    flaky.down = True
    print("  本地无额度且存储抖动：fail_open=%s，fail_closed=%s"
          % ("放行" if opener.allow("pay") else "拒绝",
             "放行" if closer.allow("pay") else "拒绝"))


if __name__ == "__main__":
    main()
