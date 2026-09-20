"""quota 限流器演示。

第一段：单进程固定窗口——放行到上限后被拒，跨过窗口边界恢复。
第二段：六个实例共享一份配额——本地预领、用不完归还、掉线回收。
"""
from quota import FixedWindowLimiter, InMemoryStore, SharedLimiter


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
    print("=== 六实例共享配额（limit=6，窗口 1s，每台预领 2，租约 0.5s） ===")
    store_clock = ManualClock()
    store = InMemoryStore(clock=store_clock)
    skews = (0.0, 0.4, -0.3, 0.2, -0.1, 0.1)  # 各机时钟差零点几秒
    nodes = [SharedLimiter(store, limit=6, window=1.0, batch=2,
                           owner="node-%d" % i, lease_ttl=0.5,
                           clock=ManualClock(skew))
             for i, skew in enumerate(skews)]

    for node in nodes:  # 总额度 6，先到的三台各预领 2 个就瓜分了
        print("  %s 请求 -> %s" % (node.owner, "放行" if node.allow() else "拒绝"))

    print("  node-2 再来一个 -> %s（本地预领的还有剩，不用再问存储）"
          % ("放行" if nodes[2].allow() else "拒绝"))

    nodes[0].close()  # node-0 主动归还手里没花完的 1 个
    print("  node-0 归还余量后，node-3 重试 -> %s"
          % ("放行" if nodes[3].allow() else "拒绝"))

    store_clock.advance(0.6)  # node-1 宕机没归还，租约到期被存储回收
    print("  node-1 宕机，租约到期回收后，node-4 重试 -> %s"
          % ("放行" if nodes[4].allow() else "拒绝"))

    store_clock.advance(0.5)  # 存储时钟跨过窗口边界，配额重置
    print("  跨窗口后 node-5 重试 -> %s"
          % ("放行" if nodes[5].allow() else "拒绝"))


if __name__ == "__main__":
    main()
