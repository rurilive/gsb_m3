"""quota 限流器演示。

第一段：单进程固定窗口——放行到上限后被拒，跨过窗口边界恢复。
第二段：多实例共享一份配额——本地预领、用不完归还、掉线回收。
"""
from quota import FixedWindowLimiter, InMemoryLeaseStore, SharedWindowLimiter


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

    # 第二段：多实例共享配额（limit=6，窗口 10s，每次预领 3 个）
    print()
    print("=== 六实例共享配额（limit=6，窗口 10s，预领 3） ===")
    store_clock = ManualClock()
    store = InMemoryLeaseStore(window=10.0, clock=store_clock)
    nodes = [SharedWindowLimiter(limit=6, window=10.0, store=store,
                                 node_id="node-%d" % i, batch=3,
                                 lease_ttl=5.0, clock=ManualClock())
             for i in range(6)]

    ok = sum(1 for _ in range(2) for n in nodes if n.allow())
    print("  六台实例各来 2 个请求：共放行 %d 个" % ok)
    print("  node-0/node-1 各预领 3 个，手里还剩未花完的额度")

    nodes[0].release_unused()
    print("  node-0 归还本地余额后，全窗口剩余 %d" % nodes[2].remaining())

    print("  node-2 申领 -> %s" % ("放行" if nodes[2].allow() else "拒绝"))
    print("  node-1 掉线（余额没还），node-2 再申领 -> %s"
          % ("放行" if nodes[2].allow() else "拒绝"))
    store_clock.advance(5.0)
    print("  租约到期，node-1 的余额被回收，node-2 再申领 -> %s"
          % ("放行" if nodes[2].allow() else "拒绝"))


if __name__ == "__main__":
    main()
