"""shapeq 现状演示。

第一段：固定窗口计数——窗口内额度用满就拒，跨窗口重新放行。
第二段：令牌桶整形——按速率补充、吸收突发，多租户共享配额下的排队与拒绝。
"""

from shapeq.limiter import FixedWindowLimiter
from shapeq.shaper import QUEUE, REJECT, TokenBucketShaper


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

    print("=== 令牌桶整形（租户容量 2、补 1/秒；队列最多等 5 秒） ===")
    clock = ManualClock()  # 整形段从 t=0 单独演示
    shaper = TokenBucketShaper(
        capacity=2,
        refill_rate=1.0,
        global_capacity=4,
        global_refill_rate=2.0,
        policy=QUEUE,
        max_wait=5.0,
        clock=clock,
        sleep=lambda seconds: clock.advance(seconds),  # 等待即推进假时钟
    )
    burst = [shaper.try_acquire("noisy") for _ in range(4)]
    for i, decision in enumerate(burst):
        label = {"allowed": "放行", "queued": "排队", "rejected": "拒绝"}[
            decision.status
        ]
        detail = (
            f"预计 t={decision.ready_at:.0f}s 放行"
            if decision.status == "queued"
            else decision.reason or "即时放行"
        )
        print(f"  t=0 noisy 第 {i + 1} 次 -> {label}（{detail}）")

    quiet = shaper.try_acquire("quiet")
    print(f"  t=0 quiet 申请 -> 放行（noisy 排队不影响其他租户）")
    snapshot = shaper.stats()
    print(
        "  stats: "
        f"queued={snapshot['queued']} rejected={snapshot['rejected']} "
        f"noisy 令牌={snapshot['tokens']['noisy']:.0f} "
        f"quiet 令牌={snapshot['tokens']['quiet']:.0f} "
        f"全局令牌={snapshot['global_tokens']:.0f}"
    )

    for decision in burst:
        if decision.status == "queued":
            shaper.wait(decision)
            print(
                f"  t={clock.now:.0f}s noisy 排队请求放行"
                f"（实际等待 {decision.waited:.0f}s）"
            )

    print("=== REJECT 策略：打满自己那份就被拒，别人照常拿 ===")
    clock.advance(10.0)  # 等令牌桶补满，再单独看拒绝策略
    rejecter = TokenBucketShaper(
        capacity=2,
        refill_rate=1.0,
        global_capacity=4,
        global_refill_rate=2.0,
        policy=REJECT,
        clock=clock,
    )
    for i in range(4):
        decision = rejecter.try_acquire("noisy")
        label = {"allowed": "放行", "queued": "排队", "rejected": "拒绝"}[
            decision.status
        ]
        print(f"  t={clock.now:.0f}s noisy 第 {i + 1} 次 -> {label}")
    decision = rejecter.try_acquire("quiet")
    print(f"  t={clock.now:.0f}s quiet 申请 -> 放行")
    snapshot = rejecter.stats()
    print(
        "  stats: "
        f"allowed={snapshot['allowed']} rejected={snapshot['rejected']} "
        f"queued={snapshot['queued']} "
        f"noisy 令牌={snapshot['tokens']['noisy']:.0f} "
        f"quiet 令牌={snapshot['tokens']['quiet']:.0f}"
    )


if __name__ == "__main__":
    main()
