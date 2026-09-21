"""预领批量站点的行为锁定测试。

全程假时钟、假链路（set_link 直接切），不真 sleep。红线：累计放行任何
时刻不越总配额；配额够就放够；断链花手里这批，恢复先对账再放行；对账重
发只记一次；收工退干净。
"""

import threading
import unittest

from slotledger.buffer import (
    BufferedSite,
    Reconciler,
    UsageReport,
)
from slotledger.ledger import Ledger, LinkDown
from slotledger.plan import (
    Round,
    Script,
    ideal_admissions,
    make_script,
    playout,
)


class FakeClock:
    """手工拨的假时钟，批大小自适应拿它量消耗速度。"""

    def __init__(self, start=100.0):
        self.t = start

    def __call__(self):
        return self.t

    def tick(self, dt):
        self.t += dt


class FlakyReconciler:
    """第一遍上报丢回执（抛 LinkDown），重发才收到，模拟专线重发。"""

    def __init__(self, real):
        self._real = real
        self._dropped = set()
        self.calls = 0

    def submit(self, report):
        self.calls += 1
        key = (report.site, report.req_id)
        if key not in self._dropped:
            self._dropped.add(key)
            raise LinkDown("lost ack")
        return self._real.submit(report)

    def reports(self, site=None):
        return self._real.reports(site)


def make_site(total=1000, name="alpha", batch=8, clock=None,
              reconciler=True):
    ledger = Ledger(total=total)
    rec = Reconciler(ledger) if reconciler else None
    site = BufferedSite(ledger, name, batch=batch, reconciler=rec,
                        clock=clock)
    return ledger, rec, site


class BatchTest(unittest.TestCase):
    def test_first_admit_pulls_one_batch_not_per_slot(self):
        ledger, _, site = make_site(total=1000, batch=16)
        self.assertEqual(site.admit(3), 3)
        self.assertEqual(site.grant_trips(), 1)
        grants = [e for e in ledger.history() if e.kind == "grant"]
        self.assertEqual(len(grants), 1)
        self.assertEqual(grants[0].amount, 16)
        self.assertEqual(site.in_hand(), 13)
        self.assertEqual(site.released(), 3)

    def test_batch_spent_before_next_trip(self):
        ledger, _, site = make_site(total=1000, batch=8)
        site.admit(5)
        self.assertEqual(site.grant_trips(), 1)
        site.admit(3)
        self.assertEqual(site.grant_trips(), 1)
        site.admit(1)
        self.assertEqual(site.grant_trips(), 2)

    def test_large_admit_pulls_multiple_batches(self):
        ledger, _, site = make_site(total=1000, batch=8)
        self.assertEqual(site.admit(20), 20)
        self.assertEqual(site.grant_trips(), 3)
        self.assertEqual(site.in_hand(), 4)

    def test_nonpositive_n_is_noop(self):
        ledger, _, site = make_site(total=10)
        self.assertEqual(site.admit(0), 0)
        self.assertEqual(site.admit(-3), 0)
        self.assertEqual(site.grant_trips(), 0)
        self.assertEqual(len(ledger.history()), 0)
        self.assertIsNone(site.blocked_last())

    def test_full_run_clears_block_reason(self):
        _, _, site = make_site(total=100)
        self.assertEqual(site.admit(10), 10)
        self.assertIsNone(site.blocked_last())


class SteadyTripTest(unittest.TestCase):
    def test_at_most_one_trip_per_eight_admissions(self):
        # 平稳期：每批花完拨 1 个时间单位，自适应维持批大小，640 个到达
        # 最多 80 趟账本。
        clock = FakeClock()
        ledger, _, site = make_site(total=10 ** 6, batch=8, clock=clock)
        served = 0
        for _ in range(80):
            clock.tick(1.0)
            served += site.admit(8)
        self.assertEqual(served, 640)
        self.assertLessEqual(site.grant_trips(), 80)

    def test_fast_consumption_grows_batch(self):
        clock = FakeClock()
        _, _, site = make_site(total=10 ** 6, batch=8, clock=clock)
        site.admit(1)  # 首批 8 在 t=100 划到，手里 7
        clock.tick(0.25)
        site.admit(7)  # 0.25 个时间单位花完 8 个，下批瞄准 32
        self.assertEqual(site.admit(32), 32)  # 一批 32，一趟划齐
        self.assertEqual(site.grant_trips(), 2)

    def test_slow_consumption_stays_at_floor(self):
        clock = FakeClock()
        _, _, site = make_site(total=10 ** 6, batch=8, clock=clock)
        for _ in range(3):
            clock.tick(4.0)
            site.admit(8)
        self.assertEqual(site.grant_trips(), 3)


class ExhaustionTest(unittest.TestCase):
    def test_stops_at_pool_without_overgrant(self):
        ledger = Ledger(total=20)
        rec = Reconciler(ledger)
        site = BufferedSite(ledger, "alpha", batch=8, reconciler=rec)
        self.assertEqual(site.admit(15), 15)
        self.assertEqual(site.grant_trips(), 2)
        self.assertEqual(site.admit(10), 5)
        self.assertEqual(site.blocked_last(), "exhausted")
        self.assertEqual(site.admit(1), 0)
        self.assertEqual(site.released(), 20)
        self.assertEqual(ledger.remaining(), 0)
        self.assertEqual(
            ledger.remaining() + ledger.outstanding(), ledger.total()
        )


class LocalConcurrencyTest(unittest.TestCase):
    def test_dozens_of_threads_deduct_without_loss_or_dup(self):
        ledger = Ledger(total=400)
        rec = Reconciler(ledger)
        site = BufferedSite(ledger, "alpha", batch=16, reconciler=rec)
        got = []
        lock = threading.Lock()
        barrier = threading.Barrier(40)

        def work():
            barrier.wait()
            n = site.admit(10)
            with lock:
                got.append(n)

        workers = [threading.Thread(target=work) for _ in range(40)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(sum(got), 400)
        self.assertEqual(site.released(), 400)
        self.assertEqual(site.in_hand(), 0)
        self.assertEqual(ledger.remaining(), 0)
        self.assertEqual(ledger.outstanding("alpha"), 400)


class PartitionTest(unittest.TestCase):
    def test_keeps_serving_from_hand_when_link_drops(self):
        ledger, rec, site = make_site(total=100, batch=8)
        self.assertEqual(site.admit(3), 3)
        ledger.set_link("alpha", False)
        self.assertEqual(site.admit(5), 5)  # 手里剩 5，全放掉
        self.assertIsNone(site.blocked_last())
        self.assertEqual(site.admit(1), 0)  # 花完了，如实拒
        self.assertEqual(site.blocked_last(), "link_down")
        self.assertEqual(site.released(), 8)
        # 断链期间账本分毫不动
        self.assertEqual(len(rec.reports("alpha")), 0)

    def test_reconciles_before_serving_after_recovery(self):
        ledger, rec, site = make_site(total=100, batch=8)
        site.admit(3)
        ledger.set_link("alpha", False)
        self.assertEqual(site.admit(5), 5)
        self.assertEqual(site.admit(2), 0)
        self.assertEqual(site.blocked_last(), "link_down")
        ledger.set_link("alpha", True)
        # 恢复后第一次放行：先对账再放行
        self.assertEqual(site.admit(4), 4)
        reports = rec.reports("alpha")
        self.assertEqual(len(reports), 1)
        report = reports[0]
        # 对账快照在补划新批之前：断链那批已用 8、手里 0
        self.assertEqual(report.used, 8)
        self.assertEqual(report.remaining, 0)
        self.assertTrue(site.last_reconcile_matched())
        self.assertEqual(site.released(), 12)

    def test_no_report_while_link_never_dropped(self):
        _, rec, site = make_site(total=100, batch=8)
        site.admit(20)
        self.assertEqual(len(rec.reports("alpha")), 0)


class ReconcilerTest(unittest.TestCase):
    def test_resend_same_request_counts_once(self):
        ledger = Ledger(total=100)
        rec = Reconciler(ledger)
        ledger.grant("alpha", 10)
        report = UsageReport("alpha", 1, used=7, remaining=3)
        ack1 = rec.submit(report)
        ack2 = rec.submit(report)
        self.assertTrue(ack1.matched)
        self.assertFalse(ack1.duplicate)
        self.assertTrue(ack2.duplicate)
        self.assertEqual(len(rec.reports("alpha")), 1)
        self.assertEqual(rec.last_report("alpha"), report)

    def test_flaky_link_resend_does_not_double_count(self):
        ledger = Ledger(total=100)
        rec = Reconciler(ledger)
        flaky = FlakyReconciler(rec)
        site = BufferedSite(ledger, "alpha", batch=8, reconciler=flaky)
        site.admit(2)
        ledger.set_link("alpha", False)
        site.admit(6)
        self.assertEqual(site.admit(1), 0)
        ledger.set_link("alpha", True)
        # 第一遍重发回执又丢，站点如实拒；第二遍成功，之后才放行
        self.assertEqual(site.admit(1), 0)
        self.assertEqual(site.blocked_last(), "link_down")
        self.assertEqual(site.admit(1), 1)
        self.assertEqual(flaky.calls, 2)
        self.assertEqual(len(rec.reports("alpha")), 1)
        report = rec.last_report("alpha")
        self.assertEqual(report.used, 8)
        self.assertEqual(report.remaining, 0)
        self.assertTrue(site.last_reconcile_matched())

    def test_submit_checks_books(self):
        ledger = Ledger(total=100)
        rec = Reconciler(ledger)
        ledger.grant("alpha", 10)
        ack = rec.submit(UsageReport("alpha", 1, used=9, remaining=3))
        self.assertFalse(ack.matched)

    def test_submit_blocked_while_link_down(self):
        ledger = Ledger(total=10)
        rec = Reconciler(ledger)
        ledger.set_link("alpha", False)
        with self.assertRaises(LinkDown):
            rec.submit(UsageReport("alpha", 1, used=0, remaining=0))
        self.assertEqual(len(rec.reports()), 0)

    def test_req_id_must_not_go_backwards(self):
        ledger = Ledger(total=10)
        rec = Reconciler(ledger)
        rec.submit(UsageReport("alpha", 2, used=0, remaining=0))
        with self.assertRaises(ValueError):
            rec.submit(UsageReport("alpha", 1, used=0, remaining=0))


class CloseTest(unittest.TestCase):
    def test_close_returns_all_held_in_one_trip(self):
        ledger, rec, site = make_site(total=100, batch=16)
        site.admit(5)
        back = site.close()
        self.assertEqual(back, 11)
        self.assertEqual(site.in_hand(), 0)
        # 放出去的 5 个是有效放行留在池外，囤的 11 个退回
        self.assertEqual(ledger.remaining(), 95)
        self.assertEqual(ledger.outstanding("alpha"), 5)
        self.assertEqual(
            ledger.remaining() + ledger.outstanding(), ledger.total()
        )
        retires = [e for e in ledger.history() if e.kind == "retire"]
        self.assertEqual(len(retires), 1)
        self.assertEqual(retires[0].amount, 11)
        self.assertEqual(rec.last_report("alpha").used, 5)
        self.assertEqual(rec.last_report("alpha").remaining, 0)

    def test_close_while_down_keeps_stock_and_retries(self):
        ledger, _, site = make_site(total=100, batch=8)
        site.admit(3)
        ledger.set_link("alpha", False)
        with self.assertRaises(LinkDown):
            site.close()
        self.assertEqual(site.in_hand(), 5)
        ledger.set_link("alpha", True)
        self.assertEqual(site.close(), 5)
        self.assertEqual(ledger.remaining(), 97)
        self.assertEqual(ledger.outstanding("alpha"), 3)

    def test_admit_after_close_raises(self):
        _, _, site = make_site(total=10)
        site.close()
        with self.assertRaises(RuntimeError):
            site.admit(1)


class TwoSiteRedlineTest(unittest.TestCase):
    def test_two_sites_serve_everyone_when_quota_covers_demand(self):
        ledger = Ledger(total=32)
        rec = Reconciler(ledger)
        alpha = BufferedSite(ledger, "alpha", batch=16, reconciler=rec)
        beta = BufferedSite(ledger, "beta", batch=16, reconciler=rec)
        # 两站并发到达量之和没越过配额：配额够就不许冤枉人
        box = []
        lock = threading.Lock()
        barrier = threading.Barrier(2)

        def grab(site, n):
            barrier.wait()
            with lock:
                box.append((site.name, site.admit(n)))

        workers = [
            threading.Thread(target=grab, args=(alpha, 16)),
            threading.Thread(target=grab, args=(beta, 16)),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        self.assertEqual(sorted(box), [("alpha", 16), ("beta", 16)])
        self.assertEqual(alpha.released(), 16)
        self.assertEqual(beta.released(), 16)
        self.assertEqual(
            ledger.remaining() + ledger.outstanding(), ledger.total()
        )
        self.assertEqual(ledger.remaining(), 0)

    def test_concurrent_grab_never_crosses_total(self):
        # 总需求超过配额的突发：红线只守不超放，累计放行任何时刻 <= 30。
        ledger = Ledger(total=30)
        rec = Reconciler(ledger)
        alpha = BufferedSite(ledger, "alpha", batch=16, reconciler=rec)
        beta = BufferedSite(ledger, "beta", batch=16, reconciler=rec)
        box = []
        lock = threading.Lock()
        barrier = threading.Barrier(2)

        def both(site):
            barrier.wait()
            n = site.admit(20)
            with lock:
                box.append(n)

        workers = [
            threading.Thread(target=both, args=(alpha,)),
            threading.Thread(target=both, args=(beta,)),
        ]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join()
        served = alpha.released() + beta.released()
        self.assertEqual(served, sum(box))
        self.assertLessEqual(served, 30)
        self.assertEqual(ledger.outstanding(), served + alpha.in_hand()
                         + beta.in_hand())
        self.assertEqual(
            ledger.remaining() + ledger.outstanding(), ledger.total()
        )
        # 收工后退净囤货，账本两边对得上
        alpha.close()
        beta.close()
        self.assertEqual(ledger.remaining(), 30 - served)
        self.assertEqual(ledger.outstanding(), served)

    def test_partition_then_recovery_balances_books(self):
        ledger = Ledger(total=40)
        rec = Reconciler(ledger)
        alpha = BufferedSite(ledger, "alpha", batch=8, reconciler=rec)
        beta = BufferedSite(ledger, "beta", batch=8, reconciler=rec)
        alpha.admit(3)
        beta.admit(5)
        ledger.set_link("alpha", False)
        self.assertEqual(alpha.admit(5), 5)   # 手里剩 5 续放
        self.assertEqual(alpha.admit(4), 0)  # 花完挨拒
        self.assertEqual(beta.admit(10), 10)
        ledger.set_link("alpha", True)
        self.assertEqual(alpha.admit(2), 2)
        self.assertTrue(alpha.last_reconcile_matched())
        self.assertEqual(alpha.released(), 10)
        self.assertEqual(
            ledger.remaining() + ledger.outstanding(), ledger.total()
        )
        alpha.close()
        beta.close()
        self.assertEqual(ledger.remaining(), 15)  # 已放 25 个留在池外
        self.assertEqual(ledger.outstanding(), 25)


class PlayoutIntegrationTest(unittest.TestCase):
    def test_matches_ideal_without_partition(self):
        script = make_script(7, quota=10 ** 6, rounds=4, partitions=0)
        ideal = ideal_admissions(script)

        def factory(ledger, name, rec_holder={}):
            if "rec" not in rec_holder:
                rec_holder["rec"] = Reconciler(ledger)
            return BufferedSite(ledger, name, reconciler=rec_holder["rec"])

        result = playout(script, factory)
        self.assertEqual(sum(result.admitted.values()), ideal.total)
        self.assertEqual(result.admitted["alpha"], ideal.per_site["alpha"])
        self.assertEqual(result.admitted["beta"], ideal.per_site["beta"])

    def test_partition_round_served_from_hand_then_reconciled(self):
        # 手工脚本：首批划 64，第 1 轮 alpha 断链到达 50，凭手里 34 续放，
        # 恢复后下一轮先对账（用 64、剩 0）再放行。
        script = Script(
            quota=1000,
            sites=("alpha", "beta"),
            rounds=(
                Round({"alpha": 30, "beta": 30}),
                Round({"alpha": 50, "beta": 50}, down=("alpha",)),
                Round({"alpha": 10, "beta": 0}),
            ),
        )

        def factory(ledger, name, holder={}):
            if "rec" not in holder:
                holder["rec"] = Reconciler(ledger)
            return BufferedSite(ledger, name, batch=64,
                                reconciler=holder["rec"])

        result = playout(script, factory)
        self.assertEqual(result.admitted, {"alpha": 74, "beta": 80})
        ledger = result.ledger
        self.assertEqual(
            ledger.remaining() + ledger.outstanding(), ledger.total()
        )
        alpha_site = result.sites["alpha"]
        self.assertTrue(alpha_site.last_reconcile_matched())
        # 断链期间没有账本动账
        down_grants = [
            e for e in ledger.history()
            if e.site == "alpha" and e.kind == "grant"
        ]
        self.assertEqual(len(down_grants), 2)


if __name__ == "__main__":
    unittest.main()
