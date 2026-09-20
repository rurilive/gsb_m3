"""coordx 现状演示。

第一段：协调者按注册顺序驱动两个账本参与者，提交后改动才可见。
第二段：两阶段提交：prepare 超时触发整体 rollback；决议落盘后
“崩溃”，用同一个文件 store、同一批参与者 recover 推完决议。
"""

import os
import tempfile

from coordx.coordinator import (
    Coordinator,
    JsonFileStore,
    Ledger,
    TwoPhaseCoordinator,
    TwoPhaseLedger,
)


class SlowLedger(TwoPhaseLedger):
    """prepare 时把注入时钟往前推，制造协调者侧超时。"""

    def __init__(self, name, clock, delay, value=0):
        super().__init__(name, value=value)
        self._clock = clock
        self._delay = delay

    def prepare(self):
        self._clock.advance(self._delay)
        return super().prepare()


class FlakyLedger(TwoPhaseLedger):
    """第一次 commit 抛错（模拟决议送达时进程被杀/网络失败），再试就成。"""

    def __init__(self, name, value=0):
        super().__init__(name, value=value)
        self._commit_attempts = 0

    def commit(self):
        self._commit_attempts += 1
        if self._commit_attempts == 1:
            raise RuntimeError("%s: connection lost while committing"
                               % self.name)
        super().commit()


def main():
    print("=== 顺序提交（当前行为） ===")
    left = Ledger("left", value=0)
    right = Ledger("right", value=0)
    coord = Coordinator([left, right])
    print("  participants:", coord.participants())

    coord.begin()
    left.write(10)
    right.write(20)
    print("  事务中 left=%r right=%r" % (left.value, right.value))

    coord.commit()
    print("  提交后 left=%r right=%r" % (left.value, right.value))
    print("  active=%r elapsed=%r" % (coord.active(), coord.elapsed()))

    print()
    print("=== 两阶段提交：prepare 超时 => 整体 rollback ===")
    clock = _ManualClock()
    fast = SlowLedger("fast", clock, delay=0.0, value=0)
    slow = SlowLedger("slow", clock, delay=8.0, value=0)
    store_dir = tempfile.mkdtemp(prefix="coordx-demo-")
    store_path = os.path.join(store_dir, "tx.json")
    tpc = TwoPhaseCoordinator([fast, slow], store=JsonFileStore(store_path),
                              clock=clock, prepare_timeout=5.0)
    tpc.begin()
    fast.write(10)
    decision = tpc.prepare()
    print("  prepare 决议: %s（原因=%s）" % (decision, tpc.abort_reason()))
    print("  rollback 后: fast=%s slow=%s" % (fast.phase(), slow.phase()))
    print("  细节: %s" % tpc.abort_detail())

    print()
    print("=== 崩溃恢复：决议已落盘，重启推完未完成提交 ===")
    clock2 = _ManualClock()
    alpha = FlakyLedger("alpha", value=100)
    beta = TwoPhaseLedger("beta", value=200)
    store = JsonFileStore(store_path)
    tpc = TwoPhaseCoordinator([alpha, beta], store=store, clock=clock2)
    tpc.begin()
    alpha.write(110)
    beta.write(220)
    print("  prepare: %s" % tpc.prepare("demo-tx-1"))
    try:
        tpc.commit()
    except RuntimeError as exc:
        print("  commit 阶段“崩溃”: %s" % exc)
    print("  崩溃现场: alpha=%r beta=%r（决议已在 %s）"
          % (alpha.value, beta.value, store_path))

    restarted = TwoPhaseCoordinator([alpha, beta],
                                    store=JsonFileStore(store_path),
                                    clock=_ManualClock())
    print("  recover 推完: %r" % restarted.recover())
    print("  恢复后: alpha=%r beta=%r" % (alpha.value, beta.value))

    os.remove(store_path)
    os.rmdir(store_dir)


class _ManualClock(object):
    """演示用假时钟：参与者在 prepare 里可把它往前推。"""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


if __name__ == "__main__":
    main()
