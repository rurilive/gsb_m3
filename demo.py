"""lockfolio 现状演示。

第一段：朴素全局互斥锁的获取、释放与按 key 互斥。
第二段：预留的租约过期与续约演示位子（见文末注释）。
"""

from lockfolio.lock import MutexLock


def main():
    print("=== 朴素全局互斥锁 ===")
    lock = MutexLock()
    print(f"  acquire(a, t1) = {lock.acquire('a', 't1')}")
    print(f"  acquire(a, t2) = {lock.acquire('a', 't2')}")
    print(f"  holder(a)      = {lock.holder('a')}")
    print(f"  release(a, t2) = {lock.release('a', 't2')}")
    print(f"  release(a, t1) = {lock.release('a', 't1')}")
    print(f"  is_locked(a)   = {lock.is_locked('a')}")
    print(f"  keys           = {lock.keys()}")

    # TODO(租约过期与续约): LeaseLock 实现后，在这里加一段演示：
    # 注入一个可手动推进的假时钟，acquire 一个带 ttl 的 key 拿到 fencing token，
    # 观察续约把到期时刻往后推、时钟越过 ttl 后租约自动失效，
    # 等待者按先后顺序拿到同一个 key，以及旧 token 的写被拒。


if __name__ == "__main__":
    main()