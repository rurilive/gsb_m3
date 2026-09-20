"""LeaseManager 演示。

第一段：发放 / 查询 / 归还，以及 TTL 到期后 get 变 None。
第二段：看护对象按节拍自动续期、续期失败立刻通知，以及过期租约回收。

全程用假时钟，跑起来不需要真实等待；主循环的节拍直接用 tick 驱动，
不起任何真线程。
"""

from leasekit.lease import LeaseManager, LeaseWatcher


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

    print("=== 看护续期 / 失败通知 / 回收 ===")
    manager.reap_expired()         # 先把上一段到期未收的残留清干净
    long_lease = manager.acquire("long-task", ttl=30.0)

    def report_loss(lease_id, holder):
        print(f"  !! {holder} 收到通知：租约 {lease_id[:8]} 没续上，立刻停手，不再写分片")

    watcher = LeaseWatcher(manager, long_lease, "long-task", interval=10.0,
                           on_lost=report_loss)

    def scheduler_tick(seconds):
        """模拟调度器主循环一拍：推进时钟 -> 驱动看护 -> 顺手回收。"""
        clock.advance(seconds)
        watcher.tick()
        reaped = manager.reap_expired()
        if reaped:
            print(f"  回收了 {reaped} 条过期租约")

    print(f"  long-task 拿到租约 {long_lease[:8]}，expires_at=30.0s，整理任务要跑很久")
    scheduler_tick(10.0)
    scheduler_tick(10.0)
    print(f"  跨过两个续期点后 expires_at={manager.get(long_lease).expires_at}s，任务安全")

    orphan = manager.acquire("forgotten", ttl=10.0)
    print("  forgotten 没配看护，租约放凉中……")
    scheduler_tick(10.0)          # forgotten 到期被回收；long-task 刚续上，活下来
    print(f"  forgotten 还在吗: {manager.get(orphan) is not None}")
    print(f"  long-task 还在吗: {manager.get(long_lease) is not None}")

    print("  -- 主循环卡死 30s（比如 GC），期间没人驱动看护 --")
    clock.advance(30.0)
    manager.reap_expired()        # 回收先跑：租约已过期，被清出内存
    watcher.tick()                # 看护这一拍才醒来，续期落空 -> 立刻通知

    s = manager.stats()
    print(f"  stats: granted={s['granted']} released={s['released']} "
          f"reaped={s['reaped']} live={s['live']}")


if __name__ == "__main__":
    main()
