"""snapline 现状演示：把四类顺序错乱现象直接跑出来。

依次演示并发下版本号重复、同一毫秒的版本顺序漂移、回滚后版本号回退
覆盖历史、删除中间版本后旧版本读不出来。修好之后这些输出的异常都会消失。
"""

import threading

from snapline.chain import SnapLine


class SyncClock:
    """假时钟：前两次调用在屏障上对齐，让两个线程同时走到版本分配点。"""

    def __init__(self, now=1000):
        self._now = now
        self._calls = 0
        self._lock = threading.Lock()
        self._gate = threading.Barrier(2)

    def __call__(self):
        with self._lock:
            self._calls += 1
            n = self._calls
        if n <= 2:
            # 等另一个线程也走到这里；等不到就放行，别把演示挂死
            try:
                self._gate.wait(timeout=0.5)
            except threading.BrokenBarrierError:
                pass
        return self._now


class StepClock:
    """每次调用前进 1，用来观察版本的自然先后。"""

    def __init__(self, start=1000):
        self._now = start

    def __call__(self):
        self._now += 1
        return self._now


def _freeze(now=1000):
    """同一毫秒：所有快照共享一个时间戳。"""
    return lambda: now


def concurrency():
    print("=== 并发下版本号重复 ===")
    store = SnapLine(clock=SyncClock())
    got = []
    seen = threading.Lock()

    def worker(tag):
        v = store.snapshot("job-7", tag)
        with seen:
            got.append((tag, v))

    threads = [threading.Thread(target=worker, args=(t,)) for t in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    got.sort()
    print(f"  两个线程拿到的版本号: {got}")
    print(f"  链上实际留下的版本:   {store.history('job-7')}")


def same_tick():
    print("=== 同一毫秒的版本顺序漂移 ===")
    store = SnapLine(clock=_freeze())
    for state in ("v1", "v2", "v3"):
        store.snapshot("doc", state)
    print(f"  按 v1,v2,v3 提交 -> history: {store.history('doc')}")
    store.rollback("doc", 1)
    print(f"  回滚到 v1 之后    -> history: {store.history('doc')}（期望 [1, 2, 3]）")


def rollback_then_write():
    print("=== 回滚后写新版本，踩掉历史 ===")
    store = SnapLine(clock=StepClock())
    for state in ("A", "B", "C"):
        store.snapshot("acct", state)
    store.rollback("acct", 1)
    print(f"  回滚后当前版本: {store.latest('acct')}")
    v = store.snapshot("acct", "A-restored")
    print(f"  回滚后再存一版，拿到版本号 {v}（期望 4）")
    print(f"  at(acct, 2) -> {store.at('acct', 2)!r}（期望 'B'）")


def delete_middle():
    print("=== 删除中间版本，链断在半路 ===")
    store = SnapLine(clock=StepClock())
    for state in ("a", "b", "c"):
        store.snapshot("cfg", state)
    store.delete("cfg", 2)
    print(f"  删掉 v2 之后 history: {store.history('cfg')}")
    print(f"  at(cfg, 1) -> {store.at('cfg', 1)!r}（期望 'a'）")
    print(f"  at(cfg, 3) -> {store.at('cfg', 3)!r}（期望 'c'）")


def main():
    concurrency()
    print()
    same_tick()
    print()
    rollback_then_write()
    print()
    delete_middle()


if __name__ == "__main__":
    main()
