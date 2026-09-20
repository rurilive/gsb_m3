"""quota 限流器演示。

第一段：单进程固定窗口——放行到上限后被拒，跨过窗口边界恢复。
第二段：多实例共享配额——本地预领、用不完归还、掉线后租约到期回收。
"""
from quota import FixedWindowLimiter, InMemoryLeaseStore, SharedLimiter


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
    print("=== 多实例共享配额（limit=6，窗口 10s，每实例预领 2） ===")
    shared_clock = ManualClock()
    store = InMemoryLeaseStore(clock=shared_clock)
    nodes = [SharedLimiter(limit=6, window=10.0, store=store, clock=shared_clock,
                           batch=2, lease_ttl=5.0, owner="node-%d" % i)
             for i in range(6)]

    allowed = sum(1 for n in nodes if n.allow())
    print("  六台各请 1 次：放行 %d 次（前三台各预领 2 个，把额度占完了）" % allowed)
    print("  node-3 再请 -> %s" % ("放行" if nodes[3].allow() else "拒绝"))

    print("  node-0 主动下线，close() 归还手里没用完的 1 个")
    nodes[0].close()
    print("  node-3 再请 -> %s" % ("放行" if nodes[3].allow() else "拒绝"))

    print("  node-1 直接挂掉（没 close），手里还攥着 1 个额度")
    shared_clock.advance(5.0)
    print("  租约到期后 node-4 再请 -> %s" % ("放行" if nodes[4].allow() else "拒绝"))


if __name__ == "__main__":
    main()
