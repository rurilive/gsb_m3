"""snapline 演示：把四类顺序错乱场景跑出来，并校验修复后的不变量。

依次覆盖并发写同一对象、同一毫秒连续提交、回滚后再写新版本、删除
中间版本。每个场景末尾对照期望断言：链没修坏时全部打印 [OK]，进程
退出码为 0；哪条不变量被破坏，对应行打印 [FAIL] 并以退出码 1 结束。
直接运行：python3 demo.py
"""

import sys
import threading

from snapline.chain import SnapLine


class SyncClock:
    """假时钟：前两次调用在屏障上对齐，让两个线程同时走到发号点。

    时刻恒定，时间本身不提供任何先后信息，发号是否互斥全靠链内部的锁。
    """

    def __init__(self, now=1000.0):
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


def _freeze(now=1000.0):
    """同一毫秒：所有快照共享一个时间戳。"""
    return lambda: now


failures = []


def check(label, actual, expected):
    """对照期望，打印一行结论并登记失败。"""
    ok = actual == expected
    mark = "OK" if ok else "FAIL"
    print(f"  [{mark}] {label}: 实际 {actual!r}，期望 {expected!r}")
    if not ok:
        failures.append(label)


def concurrency():
    print("=== 场景一：两个线程并发写同一对象 ===")
    # 多跑几轮，把发号点的竞争真正压出来
    for round_no in range(1, 21):
        store = SnapLine(clock=SyncClock())
        got = []
        seen = threading.Lock()

        def worker(tag):
            version = store.snapshot("job-7", tag)
            with seen:
                got.append((tag, version))

        threads = [threading.Thread(target=worker, args=(t,)) for t in ("A", "B")]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        versions = sorted(v for _, v in got)
        if round_no == 1:
            got.sort()
            print(f"  两个线程拿到的版本号: {got}")
        check(f"第 {round_no:>2} 轮版本号互不相同且严格递增", versions, [1, 2])
        check(f"第 {round_no:>2} 轮链上留下两版", store.history("job-7"), [1, 2])
    states = {store.at("job-7", 1), store.at("job-7", 2)}
    check("两版状态都还在，谁也没顶掉谁", states, {"A", "B"})


def same_tick():
    print("=== 场景二：同一毫秒连续提交，顺序不能漂移 ===")
    store = SnapLine(clock=_freeze())
    for state in ("v1", "v2", "v3"):
        store.snapshot("doc", state)
    check("按 v1,v2,v3 提交，history 保持提交先后", store.history("doc"), [1, 2, 3])
    check("latest 落在最后提交的 v3", store.latest("doc"), (3, "v3"))
    # 回滚只挪游标，不应打乱历史的排列
    store.rollback("doc", 1)
    check("回滚到 v1 后 history 仍是完整提交序", store.history("doc"), [1, 2, 3])
    check("回滚后 latest 指向 v1", store.latest("doc"), (1, "v1"))


def rollback_then_write():
    print("=== 场景三：回滚到旧版后再写新版本 ===")
    store = SnapLine(clock=StepClock())
    for state in ("A", "B", "C"):
        store.snapshot("acct", state)
    store.rollback("acct", 1)
    check("回滚后当前版本", store.latest("acct"), (1, "A"))
    version = store.snapshot("acct", "A-restored")
    check("新版本号从历史最大号往后发，不回退", version, 4)
    check("旧 v2 没被冲掉，仍然读得出来", store.at("acct", 2), "B")
    check("旧 v3 没被冲掉，仍然读得出来", store.at("acct", 3), "C")
    check("新版本内容可读", store.at("acct", 4), "A-restored")
    check("history 包含全部四个版本", store.history("acct"), [1, 2, 3, 4])
    check("latest 落在新版本", store.latest("acct"), (4, "A-restored"))


def delete_middle():
    print("=== 场景四：删掉中间版本，链子不能断 ===")
    store = SnapLine(clock=StepClock())
    states = ("a", "b", "c", "d")
    for state in states:
        store.snapshot("cfg", state)
    check("删除存在的中间版本返回 True", store.delete("cfg", 2), True)
    check("删除不存在的版本返回 False", store.delete("cfg", 2), False)
    check("history 只少了被删的那一版", store.history("cfg"), [1, 3, 4])
    check("被删版本读不出来", store.at("cfg", 2), None)
    check("比它旧的 v1 还读得出来", store.at("cfg", 1), "a")
    check("比它新的 v3 还读得出来", store.at("cfg", 3), "c")
    check("最新的 v4 还读得出来", store.at("cfg", 4), "d")
    # 再删一版中间的，验证多次摘链后剩余节点依旧完整、不重不漏
    check("再删中间的 v3 返回 True", store.delete("cfg", 3), True)
    check("两次删除后 history 只剩 v1,v4", store.history("cfg"), [1, 4])
    check("v1 依旧可读", store.at("cfg", 1), "a")
    check("v4 依旧可读", store.at("cfg", 4), "d")
    check("latest 退到 v4 且不受影响", store.latest("cfg"), (4, "d"))


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
        print(f"有 {len(failures)} 条不变量被破坏。")
        return 1
    print("全部不变量成立。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
