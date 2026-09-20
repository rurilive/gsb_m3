"""snapline 行为演示：把四类曾经出事的顺序场景逐个跑出来并自检。

依次覆盖：并发写同一对象不重号、同一毫秒按提交先后稳定排序、
回滚后再写版本号不回退不覆盖、删除中间版本后剩余每版都读得出来
且从任意一版往回遍历能一路走到底、不重不漏。

所有场景都带期望断言：输出里有任何一项不符，进程以非零码退出。
"""

import sys
import threading

from snapline.chain import SnapLine


failures = []


def check(label, actual, expected):
    """打印一项校验结果，不符就记下来让进程最终退出码非零。"""
    ok = actual == expected
    mark = "OK  " if ok else "FAIL"
    print(f"  [{mark}] {label}: 实际={actual!r} 期望={expected!r}")
    if not ok:
        failures.append(label)


class StepClock:
    """每次调用前进 1，用来观察版本的自然先后。"""

    def __init__(self, start=1000):
        self._now = start

    def __call__(self):
        self._now += 1
        return self._now


def frozen_clock(now=1000):
    """同一毫秒：所有快照共享一个时间戳。"""
    return lambda: now


def concurrency():
    print("=== 并发写同一对象：版本号严格递增、不重复 ===")
    # 所有提交落在同一时刻，多个线程同时冲到版本分配点。
    store = SnapLine(clock=frozen_clock())
    start = threading.Event()
    got = []
    got_lock = threading.Lock()
    n_threads = 8

    def worker(tag):
        start.wait()
        version = store.snapshot("job-7", tag)
        with got_lock:
            got.append((tag, version))

    threads = [
        threading.Thread(target=worker, args=(f"T{i}",))
        for i in range(n_threads)
    ]
    for thread in threads:
        thread.start()
    start.set()
    for thread in threads:
        thread.join()

    assigned = sorted(version for _, version in got)
    check("版本号数量", len(assigned), n_threads)
    check("版本号无重复", len(set(assigned)), n_threads)
    check("版本号连续递增", assigned, list(range(1, n_threads + 1)))
    check("链上留下全部版本", store.history("job-7"),
          list(range(1, n_threads + 1)))
    check("每版状态都回读正确",
          [store.at("job-7", version) for _, version in got],
          [tag for tag, _ in got])


def same_tick():
    print("=== 同一毫秒：按提交先后稳定排序，回滚不搅乱顺序 ===")
    store = SnapLine(clock=frozen_clock())
    for state in ("v1", "v2", "v3"):
        store.snapshot("doc", state)
    check("同刻三次提交的顺序", store.history("doc"), [1, 2, 3])
    store.rollback("doc", 1)
    check("回滚后历史顺序不变", store.history("doc"), [1, 2, 3])
    check("回滚后当前版本", store.latest("doc"), (1, "v1"))
    check("旧版本仍可回读", store.at("doc", 3), "v3")


def rollback_then_write():
    print("=== 回滚后再写：新版本号不回退，不覆盖历史 ===")
    store = SnapLine(clock=StepClock())
    for state in ("A", "B", "C"):
        store.snapshot("acct", state)
    store.rollback("acct", 1)
    check("回滚后当前版本", store.latest("acct"), (1, "A"))
    version = store.snapshot("acct", "A-restored")
    check("新版本号接着历史最大值发", version, 4)
    check("当前版本指向新版本", store.latest("acct"), (4, "A-restored"))
    check("历史 2 号没被踩掉", store.at("acct", 2), "B")
    check("历史 3 号没被踩掉", store.at("acct", 3), "C")
    check("历史版本齐全", store.history("acct"), [1, 2, 3, 4])


def delete_middle():
    print("=== 删除中间版本：链不断，剩余每版可读、回遍历不重不漏 ===")
    store = SnapLine(clock=StepClock())
    states = {1: "a", 2: "b", 3: "c", 4: "d", 5: "e"}
    for state in states.values():
        store.snapshot("cfg", state)
    store.delete("cfg", 2)
    store.delete("cfg", 4)
    check("删完后的历史", store.history("cfg"), [1, 3, 5])
    check("被删的 2 号读不到", store.at("cfg", 2), None)
    check("被删的 4 号读不到", store.at("cfg", 4), None)
    check("1 号仍然可读", store.at("cfg", 1), "a")
    check("3 号仍然可读", store.at("cfg", 3), "c")
    check("5 号仍然可读", store.at("cfg", 5), "e")
    # 从每一版现存节点往回走，都要一路走到底、不重不漏。
    check("从 5 号往回遍历", store.ancestors("cfg", 5), [5, 3, 1])
    check("从 3 号往回遍历跨过缺口", store.ancestors("cfg", 3), [3, 1])
    check("从 1 号往回遍历到终点", store.ancestors("cfg", 1), [1])


def main():
    concurrency()
    print()
    same_tick()
    print()
    rollback_then_write()
    print()
    delete_middle()
    print()
    if failures:
        print(f"有 {len(failures)} 项校验失败: {failures}")
        return 1
    print("全部不变量校验通过。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
