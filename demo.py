"""coordx 演示。

第一段：单阶段协调者按注册顺序驱动两个账本，提交后改动才可见。
第二段：两阶段提交——prepare 征询、超时按拒绝处理、决议落盘，
以及用同一个 FileStore 重启后 recover 推完未完成决议。
"""

import os
import tempfile

from coordx.coordinator import Coordinator, Ledger
from coordx.twophase import (
    ABORT,
    FileStore,
    TwoPhaseCoordinator,
    TwoPhaseLedger,
)


class Clock:
    """可被参与者在 prepare 里往前推的假时钟。"""

    def __init__(self, start=0.0):
        self.now = [start]

    def __call__(self):
        return self.now[0]


class SlowBank(TwoPhaseLedger):
    """prepare 时把时钟往前拨，模拟银行侧响应超时。"""

    def __init__(self, name, clock, stall):
        super().__init__(name)
        self._clock = clock
        self._stall = stall

    def prepare(self):
        self._clock[0] += self._stall
        return super().prepare()


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
    print("=== 两阶段提交：超时即作废 ===")
    clock = Clock()
    shop = TwoPhaseLedger("shop", value=0)
    bank = SlowBank("bank", clock.now, stall=8.0)  # 超时阈值只有 5 秒
    store = FileStore(os.path.join(tempfile.mkdtemp(), "txn.log"))
    tpc = TwoPhaseCoordinator([shop, bank], store, clock=clock, timeout=5.0)
    tpc.begin()
    shop.write(100)
    bank.write(-100)
    votes = tpc.prepare()
    print("  prepare 结论:", votes)
    outcome = tpc.resolve()
    print("  最终决议: %s，原因: %s" % (outcome, tpc.reasons()))
    print("  回滚后 shop=%r bank=%r" % (shop.value, bank.value))

    print()
    print("=== 崩溃恢复：决议落盘后被杀，重启推完 ===")
    log_path = os.path.join(tempfile.mkdtemp(), "txn.log")
    clock2 = Clock()
    left2 = TwoPhaseLedger("left2", value=0)
    right2 = TwoPhaseLedger("right2", value=0)
    tpc = TwoPhaseCoordinator(
        [left2, right2], FileStore(log_path), clock=clock2
    )
    tpc.begin()
    left2.write(7)
    right2.write(8)
    tpc.prepare()
    tpc.decide()  # commit 决议已 fsync 落盘，但结论尚未投递给参与者
    print("  被杀瞬间: left2=%r right2=%r（参与者还没收到 commit）"
          % (left2.value, right2.value))

    restarted = TwoPhaseCoordinator(
        [left2, right2], FileStore(log_path), clock=clock2
    )
    outcome = restarted.recover()
    print("  同一 store 重启 recover: %s" % outcome)
    print("  推完后 left2=%r right2=%r" % (left2.value, right2.value))
    print("  再 recover 一次也不改判: %s" % restarted.recover())

    print()
    print("=== 崩溃恢复：prepare 全过却没等到裁决 ===")
    doubt_path = os.path.join(tempfile.mkdtemp(), "txn.log")
    p1 = TwoPhaseLedger("p1", value=0)
    p2 = TwoPhaseLedger("p2", value=0)
    tpc = TwoPhaseCoordinator([p1, p2], FileStore(doubt_path))
    tpc.begin()
    p1.write(1)
    p2.write(2)
    tpc.prepare()  # 两人都同意，但决议还没落盘进程就被杀

    recovered = TwoPhaseCoordinator([p1, p2], FileStore(doubt_path))
    outcome = recovered.recover()  # 不确定就作废
    print("  recover 决议: %s" % outcome)
    print("  已 prepare 的参与者收到 rollback: p1=%r p2=%r"
          % (p1.value, p2.value))


if __name__ == "__main__":
    main()
