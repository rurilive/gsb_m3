"""shapeq 演示。

第一段：固定窗口计数——窗口内额度用满就拒，跨窗口重新放行。
第二段：令牌桶整形 + 多租户公平——按速率补充、突发被桶容量吸收；
某租户打满自己那份后超出的请求排队（等不到则拒绝），其他租户照常拿。
"""

from shapeq.limiter import FixedWindowLimiter
from shapeq.shaper import TokenBucketShaper


class ManualClock:
    """demo 用的手动时钟，逐段推进时间，不真正 sleep。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def main():
    clock = ManualClock()
    lim = FixedWindowLimiter(limit=3, window=10.0, clock=clock)

    print("=== 固定窗口计数（每窗口 3 次） ===")
    for i in range(4):
        ok = lim.allow("tenant-a")
        print(f"  t={clock.now:.0f}s 第 {i + 1} 次 -> {'放行' if ok else '拒绝'}")

    clock.advance(10.0)
    print(f"  t={clock.now:.0f}s（新窗口）-> {'放行' if lim.allow('tenant-a') else '拒绝'}")

    s = lim.stats()
    print(f"  stats: allowed={s['allowed']} rejected={s['rejected']} keys={s['keys']}")

    print()
    print("=== 令牌桶整形 + 多租户公平（每租户 容量3、1 令牌/秒，超出排队，最多等 3s） ===")
    tc = ManualClock()
    shaper = TokenBucketShaper(
        rate=1.0, capacity=3, overflow="queue", max_wait=3.0, clock=tc
    )

    print("  -- 突发：hog 瞬间来 9 个 --")
    tickets = []
    for i in range(9):
        r = shaper.acquire("hog")
        note = "放行" if r.allowed else (
            f"排队(将在 {r._ticket['ready_at']:.0f}s 放)" if r.queued
            else f"拒绝({r.reason})"
        )
        print(f"  t={tc.now:.0f}s hog 第 {i + 1} 个 -> {note}")
        if r.queued:
            tickets.append(r)

    print("  -- 同时刻 calm 照常拿到自己整桶 3 个 --")
    for i in range(3):
        print(f"  t={tc.now:.0f}s calm 第 {i + 1} 个 -> "
              f"{'放行' if shaper.acquire('calm').allowed else '拒绝'}")

    print("  -- 时间推进 3s，排队请求按补充速率逐个放出 --")
    step = 0.0
    while step < 3.0:
        step += 1.0
        tc.advance(1.0)
        shaper.pump(tc.now)
    for r in tickets:
        r.wait()
        print(f"  hog 排队请求 -> {r.status}，实际等待 {r.waited:.0f}s")

    st = shaper.stats()
    by = st["tokens_by_tenant"]
    print(f"  stats: allowed={st['allowed']} rejected={st['rejected']} "
          f"queued={st['queued']} tokens_remaining={st['tokens_remaining']:.1f}")
    print(f"         hog 剩余令牌={max(0.0, by['hog']):.1f} "
          f"calm 剩余令牌={max(0.0, by['calm']):.1f}")


if __name__ == "__main__":
    main()
