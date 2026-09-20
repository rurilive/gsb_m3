"""LeaseManager 现状演示。

第一段：发放 / 查询 / 归还，以及 TTL 到期后 get 变 None。
第二段：预留的续期与回收演示位子（见文末注释）。

全程用假时钟，跑起来不需要真实等待。
"""

from leasekit.lease import LeaseManager


class DemoClock:
    """演示用假时钟，可以手动往前拨。"""

    def __init__(self, now=0.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds
        print(f"  ..时钟前进 {seconds}s，现在是 {self.now}s")
        return self.now


def main():
    clock = DemoClock()
    manager = LeaseManager(clock=clock, default_ttl=30.0)

    print("=== 发放与归还 ===")
    lease_id = manager.acquire("worker-1", ttl=30.0)
    print(f"  worker-1 拿到租约 {lease_id[:8]}，expires_at={manager.get(lease_id).expires_at}s")

    clock.advance(20.0)
    print(f"  20s 后还活着吗: {manager.get(lease_id) is not None}")

    print(f"  worker-2 想归还: {manager.release(lease_id, 'worker-2')}（不是持有者，被拒）")
    print(f"  worker-1 归还:   {manager.release(lease_id, 'worker-1')}")
    print(f"  归还后再查:      {manager.get(lease_id)}")

    print("=== TTL 到期 ===")
    lease_id = manager.acquire("worker-2", ttl=10.0)
    clock.advance(10.0)
    print(f"  到期后 get -> {manager.get(lease_id)}")
    print(f"  再想归还     -> {manager.release(lease_id, 'worker-2')}")
    s = manager.stats()
    print(f"  stats: granted={s['granted']} released={s['released']} live={s['live']}")

    # TODO(续期改造): 续期与回收实现后，在这里加第三段演示：
    # 让 worker-2 拿一条租约、由一个看护对象按周期自动续期，
    # 推进时钟跨过若干续期点看 expires_at 往后走；再让续期失败
    # （比如持有者被换掉），看持有者怎么收到通知；最后把几条
    # 没人续的租约放凉，跑一次回收，看它们从内存消失、stats 里
    # reaped 计数上涨。


if __name__ == "__main__":
    main()
