"""LeaseManager 演示。

第一段：发放 / 查询 / 归还，以及 TTL 到期后 get 变 None。
第二段：看护对象按周期自动续期、续期失败通知，以及回收过期租约。

全程用假时钟，跑起来不需要真实等待。
"""

from leasekit.lease import LeaseManager, LeaseWatchdog


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

    print("=== 看护自动续期 ===")
    lease_id = manager.acquire("worker-3", ttl=30.0)
    print(f"  worker-3 拿到长任务租约 {lease_id[:8]}，初始到期 {manager.get(lease_id).expires_at}s")

    def on_lost(lost_id, holder, reason):
        print(f"  !! {holder} 收到通知：租约 {lost_id[:8]} 续不上了（{reason}），立刻停手")

    watchdog = LeaseWatchdog(manager, lease_id, "worker-3", 10.0, on_lost)
    for _ in range(3):                          # 主循环每轮 tick，不起线程
        clock.advance(10.0)
        watchdog.tick()
        print(f"  现在 {clock.now}s，租约到期点被推到 {manager.get(lease_id).expires_at}s")

    print("=== 续期失败通知 ===")
    ghost = manager.acquire("worker-4", ttl=30.0)
    ghost_wd = LeaseWatchdog(manager, ghost, "worker-4", 25.0,
                             lambda *a: on_lost(*a))
    print("  worker-4 停在 GC 边界没再 tick，租约先过期又被回收：")
    clock.advance(35.0)
    swept = manager.reap_expired()
    print(f"  回收顺手清掉 {len(swept)} 条（含 worker-4 和之前没人续的）")
    ghost_wd.tick()                            # 下一 tick 立刻发现并通知

    print("=== 回收过期租约 ===")
    manager.acquire("worker-5", ttl=5.0)
    manager.acquire("worker-6", ttl=5.0)
    keep = manager.acquire("worker-7", ttl=100.0)
    clock.advance(10.0)
    reaped = manager.reap_expired()
    print(f"  回收了 {len(reaped)} 条过期租约，worker-7 的长租约还在: {manager.get(keep) is not None}")
    s = manager.stats()
    print(f"  stats: granted={s['granted']} released={s['released']} reaped={s['reaped']} live={s['live']}")


if __name__ == "__main__":
    main()
