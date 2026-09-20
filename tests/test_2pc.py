"""两阶段提交与崩溃恢复的行为测试。

覆盖：prepare/commit/rollback 顺序、反对与抛错按拒绝处理、注入时钟
推进导致的 prepare 超时（记录为 timeout 而非 veto）、决议与参与者
完成状态逐部落盘、崩溃后用同一 store 与同一批参与者 recover 推完，
以及已落盘决议不可翻转。老参与者（只有 begin/commit）仍只服务
单阶段 Coordinator，两阶段不要求它们补方法。
"""

import unittest
import os
import tempfile

from coordx.coordinator import (
    JsonFileStore,
    MemoryStore,
    PrepareParticipant,
    TwoPhaseCoordinator,
    TwoPhaseLedger,
)


class FakeClock(object):
    """可手动推进的时钟，prepare 里往前推即可模拟下游耗时。"""

    def __init__(self, start=0.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeTwoPhase(PrepareParticipant):
    """把 begin/prepare/commit/rollback 记进共享流水的假参与者。

    vote=False 投反对；prepare_raises 在 prepare 里抛错；
    prepare_delay 让注入时钟在 prepare 里前进这么多秒；
    crash_on_prepare=True 时在落完赞成票后抛 SystemExit，模拟被 kill；
    commit_failures 让前 N 次 commit 抛错，之后成功。
    """

    def __init__(self, name, journal, vote=True, prepare_raises=None,
                 prepare_delay=0.0, crash_on_prepare=False,
                 rollback_raises=None, commit_failures=0):
        super().__init__(name)
        self._journal = journal
        self._vote = vote
        self._prepare_raises = prepare_raises
        self._prepare_delay = prepare_delay
        self._crash_on_prepare = crash_on_prepare
        self._rollback_raises = rollback_raises
        self._commit_failures = commit_failures
        self._clock = None
        self.prepared_calls = 0
        self.commit_calls = 0
        self.rollback_calls = 0

    def bind_clock(self, clock):
        self._clock = clock

    def begin(self):
        self._journal.append(("begin", self.name))

    def prepare(self):
        self.prepared_calls += 1
        self._journal.append(("prepare", self.name))
        if self._prepare_raises is not None:
            raise self._prepare_raises
        if self._clock is not None:
            self._clock.advance(self._prepare_delay)
        if self._crash_on_prepare:
            self._journal.append(("crash", self.name))
            raise SystemExit("simulated kill after prepare persisted")
        return self._vote

    def commit(self):
        self.commit_calls += 1
        self._journal.append(("commit", self.name))
        if self.commit_calls <= self._commit_failures:
            raise RuntimeError("%s: commit failed (attempt %d)"
                               % (self.name, self.commit_calls))

    def rollback(self):
        self.rollback_calls += 1
        self._journal.append(("rollback", self.name))
        if self._rollback_raises is not None:
            raise self._rollback_raises


def names_of(journal, op):
    return [name for recorded_op, name in journal if recorded_op == op]


def make(participants, clock=None, timeout=5.0, store=None):
    clock = clock or FakeClock()
    store = store or MemoryStore()
    for participant in participants:
        bind = getattr(participant, "bind_clock", None)
        if bind is not None:
            bind(clock)
    return TwoPhaseCoordinator(participants, store=store, clock=clock,
                               prepare_timeout=timeout), store, clock


class TestHappyPath(unittest.TestCase):
    def test_all_yes_then_commits_in_order(self):
        journal = []
        a = FakeTwoPhase("a", journal)
        b = FakeTwoPhase("b", journal)
        coord, store, _ = make([a, b])

        coord.begin()
        self.assertEqual(coord.prepare(), "committing")
        coord.commit()

        self.assertEqual(names_of(journal, "prepare"), ["a", "b"])
        self.assertEqual(names_of(journal, "commit"), ["a", "b"])
        self.assertEqual(names_of(journal, "rollback"), [])
        self.assertFalse(coord.active())
        last = list(store._records.values())[-1]
        self.assertEqual(last["state"], "committed")
        self.assertEqual(last["decision"], "committing")

    def test_each_commit_ack_persisted_as_done(self):
        journal = []
        a = FakeTwoPhase("a", journal)
        b = FakeTwoPhase("b", journal)
        coord, store, _ = make([a, b])
        coord.begin()
        coord.prepare("tx-fixed")
        self.assertEqual(store.load("tx-fixed")["done"], [])
        coord.commit()
        self.assertEqual(store.load("tx-fixed")["done"], ["a", "b"])

    def test_ledger_only_publishes_on_commit(self):
        left = TwoPhaseLedger("left", value=0)
        right = TwoPhaseLedger("right", value=0)
        coord, _, _ = make([left, right])
        coord.begin()
        left.write(5)
        right.write(6)
        coord.prepare()
        self.assertEqual((left.value, right.value), (0, 0))
        coord.commit()
        self.assertEqual((left.value, right.value), (5, 6))


class TestVetoAndError(unittest.TestCase):
    def test_veto_rolls_back_prepared_in_reverse(self):
        journal = []
        a = FakeTwoPhase("a", journal)
        b = FakeTwoPhase("b", journal, vote=False)
        c = FakeTwoPhase("c", journal)
        coord, store, _ = make([a, b, c])

        coord.begin()
        self.assertEqual(coord.prepare(), "aborting")

        self.assertEqual(names_of(journal, "prepare"), ["a", "b"])
        self.assertEqual(names_of(journal, "rollback"), ["a"])
        self.assertEqual(a.rollback_calls, 1)
        self.assertEqual(b.rollback_calls, 0)  # 反对者自己没进 prepare
        self.assertEqual(c.prepared_calls, 0)  # 短路：不再问后面的人
        self.assertEqual(coord.abort_reason(), "veto")
        only = next(iter(store._records.values()))
        self.assertEqual(only["decision"], "aborting")
        self.assertEqual(only["abort_reason"], "veto")
        self.assertEqual(only["state"], "aborted")
        self.assertFalse(coord.active())

    def test_prepare_exception_is_rejection_with_error_reason(self):
        journal = []
        a = FakeTwoPhase("a", journal)
        b = FakeTwoPhase("b", journal,
                         prepare_raises=RuntimeError("downstream boom"))
        coord, _, _ = make([a, b])
        coord.begin()
        self.assertEqual(coord.prepare(), "aborting")
        self.assertEqual(coord.abort_reason(), "error")
        self.assertIn("downstream boom", coord.abort_detail())
        self.assertEqual(names_of(journal, "rollback"), ["a"])

    def test_commit_after_abort_raises_and_does_not_flip(self):
        journal = []
        a = FakeTwoPhase("a", journal, vote=False)
        coord, store, _ = make([a])
        coord.begin()
        coord.prepare()
        with self.assertRaises(RuntimeError):
            coord.commit()
        record = next(iter(store._records.values()))
        self.assertEqual(record["decision"], "aborting")
        self.assertEqual(a.commit_calls, 0)


class TestTimeout(unittest.TestCase):
    def test_clock_advance_over_timeout_is_timeout_not_veto(self):
        journal = []
        clock = FakeClock()
        a = FakeTwoPhase("a", journal)
        slow = FakeTwoPhase("slow", journal, prepare_delay=6.0)
        c = FakeTwoPhase("c", journal)
        coord, store, _ = make([a, slow, c], clock=clock, timeout=5.0)

        coord.begin()
        self.assertEqual(coord.prepare(), "aborting")

        self.assertEqual(coord.abort_reason(), "timeout")
        self.assertNotEqual(coord.abort_reason(), "veto")
        self.assertIn("timed out", coord.abort_detail())
        self.assertIn("6.000", coord.abort_detail())
        # 已 prepare 的 a 与超时的 slow 都必须收到 rollback 结论。
        self.assertEqual(names_of(journal, "rollback"), ["slow", "a"])
        self.assertEqual(c.prepared_calls, 0)
        record = next(iter(store._records.values()))
        self.assertEqual(record["abort_reason"], "timeout")
        self.assertEqual(record["prepared"], ["a", "slow"])

    def test_delay_equal_to_threshold_is_not_timeout(self):
        journal = []
        clock = FakeClock()
        a = FakeTwoPhase("a", journal, prepare_delay=5.0)
        coord, _, _ = make([a], clock=clock, timeout=5.0)
        coord.begin()
        self.assertEqual(coord.prepare(), "committing")

    def test_small_advance_does_not_timeout(self):
        journal = []
        clock = FakeClock()
        a = FakeTwoPhase("a", journal, prepare_delay=4.9)
        coord, _, _ = make([a], clock=clock, timeout=5.0)
        coord.begin()
        self.assertEqual(coord.prepare(), "committing")

    def test_timeout_then_recover_does_not_commit(self):
        journal = []
        clock = FakeClock()
        a = FakeTwoPhase("a", journal)
        slow = FakeTwoPhase("slow", journal, prepare_delay=9.0)
        coord, store, _ = make([a, slow], clock=clock, timeout=5.0)
        coord.begin()
        coord.prepare()
        restarted = TwoPhaseCoordinator([a, slow], store=store,
                                        clock=FakeClock(),
                                        prepare_timeout=5.0)
        self.assertEqual(restarted.recover(), [])
        self.assertEqual(a.commit_calls, 0)


class TestRecovery(unittest.TestCase):
    def test_recovery_finishes_commit_after_decision_persisted(self):
        journal = []
        a = FakeTwoPhase("a", journal)
        b = FakeTwoPhase("b", journal, commit_failures=1)
        coord, store, _ = make([a, b])
        coord.begin()
        coord.prepare()
        with self.assertRaises(RuntimeError):
            coord.commit()  # b 在收到 commit 后抛错：决议已落盘
        self.assertEqual(names_of(journal, "commit"), ["a", "b"])

        restarted = TwoPhaseCoordinator([a, b], store=store,
                                        clock=FakeClock())
        finished = restarted.recover()
        self.assertEqual(len(finished), 1)
        txid, outcome = finished[0]
        self.assertEqual(outcome, "committed")
        # a 已完成不重放，只有 b 补一次。
        self.assertEqual(names_of(journal, "commit"), ["a", "b", "b"])
        self.assertEqual(store.load(txid)["state"], "committed")
        self.assertEqual(store.pending(), [])

    def test_recovered_commit_decision_never_flips_to_abort(self):
        journal = []
        a = FakeTwoPhase("a", journal, commit_failures=1)
        coord, store, _ = make([a])
        coord.begin()
        coord.prepare()
        with self.assertRaises(RuntimeError):
            coord.commit()
        record = next(iter(store._records.values()))
        self.assertEqual(record["decision"], "committing")

        # 恢复时参与者即便“改了主意”，commit 结论照旧送达。
        a._vote = False
        restarted = TwoPhaseCoordinator([a], store=store, clock=FakeClock())
        self.assertEqual(restarted.recover()[0][1], "committed")
        self.assertEqual(a.rollback_calls, 0)
        self.assertEqual(a.commit_calls, 2)

    def test_recovery_after_kill_before_decision_aborts_prepared(self):
        journal = []
        clock = FakeClock()
        a = FakeTwoPhase("a", journal)
        b = FakeTwoPhase("b", journal, crash_on_prepare=True)
        c = FakeTwoPhase("c", journal)
        coord, store, _ = make([a, b, c], clock=clock)
        coord.begin()
        with self.assertRaises(SystemExit):
            coord.prepare()  # b 投完赞成、决议落盘前进程被 kill

        pending = store.pending()
        self.assertEqual(len(pending), 1)
        stuck = pending[0]
        self.assertIsNone(stuck["decision"])
        self.assertEqual(stuck["prepared"], ["a"])
        self.assertEqual(stuck["asking"], "b")  # b 已 prepare 但投票没落盘

        restarted = TwoPhaseCoordinator([a, b, c], store=store,
                                        clock=FakeClock())
        self.assertEqual(restarted.recover(), [(stuck["id"], "aborted")])
        # 决议前崩溃：没有提交可能；已 prepare 者按相反顺序收到 rollback。
        self.assertEqual(names_of(journal, "rollback"), ["b", "a"])
        self.assertEqual(names_of(journal, "commit"), [])
        self.assertEqual(store.load(stuck["id"])["state"], "aborted")

    def test_recovery_finishes_abort_after_rollback_failure(self):
        journal = []
        first = FakeTwoPhase("first", journal)
        first._rollback_raises = RuntimeError("network gone")
        veto = FakeTwoPhase("veto", journal, vote=False)
        tail = FakeTwoPhase("tail", journal)
        coord, store, _ = make([first, veto, tail])
        coord.begin()
        with self.assertRaises(RuntimeError):
            coord.prepare()
        # abort 决议已落盘（不可翻转），但补偿还没送完。
        stuck = store.pending()[0]
        self.assertEqual(stuck["decision"], "aborting")
        self.assertEqual(stuck["done"], [])

        first._rollback_raises = None
        restarted = TwoPhaseCoordinator([first, veto, tail], store=store,
                                        clock=FakeClock())
        self.assertEqual(restarted.recover(), [(stuck["id"], "aborted")])
        self.assertEqual(first.rollback_calls, 2)
        self.assertEqual(store.pending(), [])

    def test_prepared_participant_waiting_verdict_gets_commit(self):
        # 决议已落盘、a 的 commit 已送达，b 还在等结论时进程崩溃。
        journal = []
        a = FakeTwoPhase("a", journal)
        b = FakeTwoPhase("b", journal)
        coord, store, _ = make([a, b])
        coord.begin()
        coord.prepare("tx-wait")
        # 手工把记录改成“commit 决议已落盘、只完成 a”的崩溃现场。
        a.commit()
        record = store.load("tx-wait")
        record["done"] = ["a"]
        store.save(record)

        restarted = TwoPhaseCoordinator([a, b], store=store,
                                        clock=FakeClock())
        self.assertEqual(restarted.recover(), [("tx-wait", "committed")])
        # b 必须收到它没等到的 commit；a 不重复提交。
        self.assertEqual(names_of(journal, "commit"), ["a", "b"])
        self.assertEqual(b.commit_calls, 1)


class TestDurableStore(unittest.TestCase):
    def test_json_file_store_survives_new_coordinator_instance(self):
        tmpdir = tempfile.mkdtemp()
        path = os.path.join(tmpdir, "tx.json")
        try:
            journal = []
            a = FakeTwoPhase("a", journal)
            b = FakeTwoPhase("b", journal)
            clock = FakeClock()
            store = JsonFileStore(path)
            for participant in (a, b):
                participant.bind_clock(clock)
            coord = TwoPhaseCoordinator([a, b], store=store, clock=clock)
            coord.begin()
            coord.prepare("tx-on-disk")
            # 模拟在任何 commit 送达前崩溃：只留决议在文件里。
            self.assertTrue(os.path.exists(path))

            new_store = JsonFileStore(path)
            restarted = TwoPhaseCoordinator([a, b], store=new_store,
                                            clock=FakeClock())
            self.assertEqual(restarted.recover(),
                             [("tx-on-disk", "committed")])
            self.assertEqual(names_of(journal, "commit"), ["a", "b"])
            self.assertEqual(new_store.pending(), [])
        finally:
            if os.path.exists(path):
                os.remove(path)
            os.rmdir(tmpdir)


class TestLegacyCompatibility(unittest.TestCase):
    def test_old_participant_needs_no_new_methods(self):
        # 老参与者只有 begin/commit，单阶段基线照常工作。
        from coordx.coordinator import Coordinator, Ledger

        left, right = Ledger("left"), Ledger("right")
        coord = Coordinator([left, right])
        coord.begin()
        left.write(1)
        right.write(2)
        coord.commit()
        self.assertEqual((left.value, right.value), (1, 2))
        # 两阶段协调者不碰没有 prepare 的老参与者，直到真正调用。
        twophase = TwoPhaseCoordinator([left, right], store=MemoryStore())
        self.assertEqual(twophase.participants(), ("left", "right"))


if __name__ == "__main__":
    unittest.main()
