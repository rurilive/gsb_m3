"""两阶段提交行为测试：征询、超时口径、意图落盘与崩溃恢复。"""

import os
import shutil
import tempfile
import unittest

from coordx.coordinator import Coordinator, Ledger, Participant
from coordx.twophase import (
    ABORT,
    COMMIT,
    ERROR,
    FileStore,
    MemoryStore,
    NO,
    TIMEOUT,
    YES,
    TwoPhaseCoordinator,
    TwoPhaseLedger,
)


class Fake2PC:
    """记录全部调用的两阶段假参与者；可在 prepare 里拨钟、反对或抛错。"""

    def __init__(self, name, journal, vote=True, fail=(), advance=0.0, clock=None):
        self.name = name
        self._journal = journal
        self._vote = vote
        self._fail = set(fail)
        self._advance = advance
        self._clock = clock
        self.state = "new"

    def _note(self, op):
        self._journal.append((op, self.name))

    def begin(self):
        self._note("begin")
        self.state = "open"
        if "begin" in self._fail:
            raise RuntimeError("%s: begin failed" % self.name)

    def prepare(self):
        self._note("prepare")
        if "prepare" in self._fail:
            raise RuntimeError("%s: prepare failed" % self.name)
        if self._clock is not None and self._advance:
            self._clock[0] += self._advance
        self.state = "prepared"
        return self._vote

    def rollback(self):
        self._note("rollback")
        self.state = "aborted"

    def commit(self):
        self._note("commit")
        self.state = "committed"


class FlakyParticipant(Fake2PC):
    """前 fail_times 次 commit 抛错，之后成功。"""

    def __init__(self, name, journal, fail_times):
        super().__init__(name, journal)
        self._fail_times = fail_times

    def commit(self):
        if self._fail_times > 0:
            self._fail_times -= 1
            raise RuntimeError("%s: commit temporarily unavailable" % self.name)
        super().commit()


def names_of(journal, op):
    return [name for recorded_op, name in journal if recorded_op == op]


class MutableClock:
    """可被参与者在 prepare 里往前推的注入时钟。"""

    def __init__(self, start=100.0):
        self.now = [start]

    def __call__(self):
        return self.now[0]


class TwoPhaseCommitTest(unittest.TestCase):
    def setUp(self):
        self.journal = []
        self.a = Fake2PC("a", self.journal)
        self.b = Fake2PC("b", self.journal)
        self.c = Fake2PC("c", self.journal)
        self.store = MemoryStore()
        self.coord = TwoPhaseCoordinator([self.a, self.b, self.c], self.store)

    def test_all_yes_commits_in_order(self):
        self.coord.begin()
        votes = self.coord.prepare()
        self.assertEqual(votes, {"a": YES, "b": YES, "c": YES})
        outcome = self.coord.resolve()
        self.assertEqual(outcome, COMMIT)
        self.assertEqual(names_of(self.journal, "begin"), ["a", "b", "c"])
        self.assertEqual(names_of(self.journal, "prepare"), ["a", "b", "c"])
        self.assertEqual(names_of(self.journal, "commit"), ["a", "b", "c"])
        self.assertEqual(names_of(self.journal, "rollback"), [])
        self.assertFalse(self.coord.active())
        self.assertEqual(self.coord.decision(), COMMIT)

    def test_empty_participant_set_commits(self):
        coord = TwoPhaseCoordinator([], MemoryStore())
        self.assertEqual(coord.run(), COMMIT)
        self.assertEqual(coord.decision(), COMMIT)

    def test_no_vote_aborts_and_prepared_participants_rollback_in_reverse(self):
        self.b._vote = False
        outcome = self.coord.run()
        self.assertEqual(outcome, ABORT)
        self.assertEqual(names_of(self.journal, "prepare"), ["a", "b"])
        self.assertNotIn(("prepare", "c"), self.journal)
        self.assertEqual(names_of(self.journal, "rollback"), ["b", "a"])
        self.assertEqual(names_of(self.journal, "commit"), [])
        self.assertEqual(self.coord.reasons(), "b=no")

    def test_prepare_exception_recorded_as_error_not_no(self):
        self.b._fail.add("prepare")
        self.assertEqual(self.coord.run(), ABORT)
        self.assertEqual(self.coord.votes()["b"], ERROR)
        self.assertEqual(self.coord.reasons(), "b=error")

    def test_timeout_is_measured_from_clock_delta_inside_prepare(self):
        clock = MutableClock()
        slow = Fake2PC("slow", self.journal, advance=15.0, clock=clock.now)
        coord = TwoPhaseCoordinator(
            [self.a, slow], MemoryStore(), clock=clock, timeout=10.0
        )
        coord.begin()
        votes = coord.prepare()
        self.assertEqual(votes["slow"], TIMEOUT)
        self.assertEqual(coord.resolve(), ABORT)
        self.assertEqual(coord.reasons(), "slow=timeout")
        self.assertEqual(names_of(self.journal, "rollback"), ["slow", "a"])

    def test_timeout_delta_equal_to_limit_counts_as_timeout(self):
        clock = MutableClock()
        on_edge = Fake2PC("edge", self.journal, advance=10.0, clock=clock.now)
        coord = TwoPhaseCoordinator(
            [on_edge], MemoryStore(), clock=clock, timeout=10.0
        )
        coord.begin()
        self.assertEqual(coord.prepare()["edge"], TIMEOUT)

    def test_clock_delta_below_limit_is_a_yes(self):
        clock = MutableClock()
        quick = Fake2PC("q", self.journal, advance=9.9, clock=clock.now)
        coord = TwoPhaseCoordinator(
            [quick], MemoryStore(), clock=clock, timeout=10.0
        )
        coord.begin()
        self.assertEqual(coord.prepare()["q"], YES)

    def test_timeout_stops_later_prepares(self):
        clock = MutableClock()
        slow = Fake2PC("slow", self.journal, advance=99.0, clock=clock.now)
        coord = TwoPhaseCoordinator(
            [slow, self.c], MemoryStore(), clock=clock, timeout=10.0
        )
        coord.run()
        self.assertNotIn(("prepare", "c"), self.journal)

    def test_decision_is_persisted_before_any_delivery(self):
        self.coord.begin()
        self.coord.prepare()
        self.coord.decide()
        events = [r["event"] for r in self.store.records()]
        self.assertIn("decision", events)
        self.assertNotIn("delivered", events)
        self.coord.resolve()

    def test_prepare_without_begin_raises(self):
        with self.assertRaises(RuntimeError):
            self.coord.prepare()

    def test_begin_twice_raises(self):
        self.coord.begin()
        with self.assertRaises(RuntimeError):
            self.coord.begin()


class TwoPhaseLedgerTest(unittest.TestCase):
    def test_commit_makes_pending_visible(self):
        ledger = TwoPhaseLedger("l", value=0)
        coord = TwoPhaseCoordinator([ledger], MemoryStore())
        coord.begin()
        ledger.write(42)
        self.assertEqual(ledger.value, 0)
        coord.prepare()
        coord.resolve()
        self.assertEqual(ledger.value, 42)

    def test_rollback_discards_pending(self):
        ledger = TwoPhaseLedger("l", value=3)
        naysayer = Fake2PC("naysayer", [], vote=False)
        coord = TwoPhaseCoordinator([ledger, naysayer], MemoryStore())
        coord.begin()
        ledger.write(42)
        coord.prepare()
        coord.resolve()
        self.assertEqual(ledger.value, 3)


class BeginFailureTest(unittest.TestCase):
    def test_begin_failure_persists_abort_and_rolls_back(self):
        journal = []
        good = Fake2PC("good", journal)
        bad = Fake2PC("bad", journal, fail=("begin",))
        store = MemoryStore()
        coord = TwoPhaseCoordinator([good, bad], store)
        with self.assertRaises(RuntimeError):
            coord.begin()
        self.assertEqual(names_of(journal, "rollback"), ["good"])
        events = [r["event"] for r in store.records()]
        self.assertEqual(events[0], "begin")
        self.assertIn("decision", events)

        restarted = TwoPhaseCoordinator([good, bad], store)
        self.assertEqual(restarted.recover(), ABORT)
        self.assertEqual(names_of(journal, "rollback"), ["good"])


class RecoveryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.log_path = os.path.join(self.tmp, "txn.log")

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _participants(self, journal):
        return (
            Fake2PC("a", journal),
            Fake2PC("b", journal),
            Fake2PC("c", journal),
        )

    def test_crash_after_commit_decision_still_commits_everyone(self):
        journal = []
        a, b, c = self._participants(journal)
        coord = TwoPhaseCoordinator([a, b, c], FileStore(self.log_path))
        coord.begin()
        coord.prepare()
        coord.decide(COMMIT)  # 决议已落盘，但谁都还没收到

        restarted = TwoPhaseCoordinator([a, b, c], FileStore(self.log_path))
        self.assertEqual(restarted.recover(), COMMIT)
        self.assertEqual(names_of(journal, "commit"), ["a", "b", "c"])

    def test_prepared_without_decision_gets_rollback_after_restart(self):
        journal = []
        a, b, c = self._participants(journal)
        coord = TwoPhaseCoordinator([a, b, c], FileStore(self.log_path))
        coord.begin()
        self.assertEqual(coord.prepare(), {"a": YES, "b": YES, "c": YES})
        # 此时进程被杀：prepare 全过，但没有任何决议落盘。

        restarted = TwoPhaseCoordinator([a, b, c], FileStore(self.log_path))
        self.assertEqual(restarted.recover(), ABORT)
        self.assertEqual(names_of(journal, "commit"), [])
        self.assertEqual(names_of(journal, "rollback"), ["c", "b", "a"])
        for participant in (a, b, c):
            self.assertEqual(participant.state, "aborted")

    def test_recovery_even_with_fresh_downstream_objects_delivers_conclusion(self):
        journal1 = []
        coord = TwoPhaseCoordinator(
            self._participants(journal1), FileStore(self.log_path)
        )
        coord.begin()
        coord.prepare()
        # 没决议就被杀。

        journal2 = []
        restarted = TwoPhaseCoordinator(
            self._participants(journal2), FileStore(self.log_path)
        )
        self.assertEqual(restarted.recover(), ABORT)
        self.assertEqual(names_of(journal2, "rollback"), ["c", "b", "a"])

    def test_committed_decision_never_flips_on_recovery(self):
        journal = []
        a, b, c = self._participants(journal)
        coord = TwoPhaseCoordinator([a, b, c], FileStore(self.log_path))
        coord.run()
        commits_after_run = len(names_of(journal, "commit"))

        restarted = TwoPhaseCoordinator([a, b, c], FileStore(self.log_path))
        self.assertEqual(restarted.decide(ABORT), COMMIT)
        self.assertEqual(restarted.recover(), COMMIT)
        self.assertEqual(restarted.recover(), COMMIT)
        self.assertEqual(len(names_of(journal, "commit")), commits_after_run)
        self.assertEqual(names_of(journal, "rollback"), [])

    def test_recovery_resumes_after_failed_delivery_without_repeats(self):
        journal = []
        flaky = FlakyParticipant("flaky", journal, fail_times=1)
        other = Fake2PC("other", journal)
        coord = TwoPhaseCoordinator([flaky, other], FileStore(self.log_path))
        coord.begin()
        coord.prepare()
        with self.assertRaises(RuntimeError):
            coord.resolve()  # flaky 第一次 commit 抛错，进程中止

        restarted = TwoPhaseCoordinator([flaky, other], FileStore(self.log_path))
        self.assertEqual(restarted.recover(), COMMIT)
        self.assertEqual(names_of(journal, "commit").count("other"), 1)
        self.assertEqual(flaky.state, "committed")

    def test_timeout_abort_survives_restart(self):
        clock = MutableClock()
        journal = []
        fast = Fake2PC("fast", journal)
        slow = Fake2PC("slow", journal, advance=30.0, clock=clock.now)
        coord = TwoPhaseCoordinator(
            [fast, slow], FileStore(self.log_path), clock=clock, timeout=5.0
        )
        coord.begin()
        coord.prepare()
        coord.decide()  # abort=timeout 已落盘，投递前被杀

        restarted = TwoPhaseCoordinator(
            [fast, slow], FileStore(self.log_path), clock=clock, timeout=5.0
        )
        self.assertEqual(restarted.recover(), ABORT)
        self.assertEqual(restarted.reasons(), "slow=timeout")
        self.assertEqual(names_of(journal, "rollback"), ["slow", "fast"])

    def test_recover_with_participant_mismatch_raises(self):
        journal = []
        coord = TwoPhaseCoordinator(
            self._participants(journal), FileStore(self.log_path)
        )
        coord.begin()
        coord.prepare()
        with self.assertRaises(RuntimeError):
            TwoPhaseCoordinator(
                [Fake2PC("a", journal), Fake2PC("x", journal)],
                FileStore(self.log_path),
            )

    def test_recover_empty_store_raises(self):
        with self.assertRaises(RuntimeError):
            TwoPhaseCoordinator(
                self._participants([]), FileStore(self.log_path)
            ).recover()


class LegacyParticipantTest(unittest.TestCase):
    def test_old_participant_only_begin_commit_is_rejected_for_twophase(self):
        class OldStyle(Participant):
            def __init__(self):
                super().__init__("old")

            def begin(self):
                pass

            def commit(self):
                pass

        with self.assertRaises(TypeError):
            TwoPhaseCoordinator([OldStyle()], MemoryStore())

    def test_old_participant_still_works_with_single_phase_coordinator(self):
        ledger = Ledger("legacy", value=1)
        coord = Coordinator([ledger])
        coord.begin()
        ledger.write(9)
        coord.commit()
        self.assertEqual(ledger.value, 9)

    def test_duplicate_participant_names_rejected(self):
        with self.assertRaises(ValueError):
            TwoPhaseCoordinator(
                [Fake2PC("x", []), Fake2PC("x", [])], MemoryStore()
            )


if __name__ == "__main__":
    unittest.main()
