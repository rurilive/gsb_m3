"""事故脚本与纯算术参考的锁定测试，基线不许动。"""

import threading
import unittest

from slotledger.plan import Round, Script, ideal_admissions, make_script, playout
from slotledger.site import Site


def naive_site(ledger, name):
    return Site(ledger, name)


class ScriptTest(unittest.TestCase):
    def test_same_seed_same_script(self):
        self.assertEqual(
            make_script(5, rounds=4),
            make_script(5, rounds=4),
        )

    def test_different_seed_differs(self):
        self.assertNotEqual(
            make_script(5, rounds=4),
            make_script(6, rounds=4),
        )

    def test_script_shape(self):
        script = make_script(1, rounds=5, low=20, high=160)
        self.assertEqual(script.sites, ("alpha", "beta"))
        self.assertEqual(len(script.rounds), 5)
        for rnd in script.rounds:
            self.assertEqual(set(rnd.arrivals), {"alpha", "beta"})
            for n in rnd.arrivals.values():
                self.assertGreaterEqual(n, 20)
                self.assertLessEqual(n, 160)

    def test_partitions_honored_and_not_first_round(self):
        script = make_script(3, rounds=6, partitions=2)
        down_rounds = [i for i, rnd in enumerate(script.rounds) if rnd.down]
        self.assertEqual(len(down_rounds), 2)
        self.assertNotIn(0, down_rounds)
        for rnd in script.rounds:
            if rnd.down:
                self.assertEqual(len(rnd.down), 1)
                self.assertIn(rnd.down[0], script.sites)

    def test_single_site_script(self):
        script = make_script(9, sites=("solo",), quota=500, rounds=3, partitions=0)
        self.assertEqual(len(script.rounds), 3)
        self.assertEqual(set(script.rounds[0].arrivals), {"solo"})


class IdealTest(unittest.TestCase):
    def test_ideal_respects_quota(self):
        script = Script(quota=5, sites=("alpha", "beta"),
                        rounds=(Round({"alpha": 3, "beta": 4}),))
        ideal = ideal_admissions(script)
        self.assertEqual(ideal.total, 5)
        self.assertEqual(ideal.unserved, 2)
        self.assertEqual(ideal.per_site, {"alpha": 3, "beta": 2})

    def test_ideal_plenty_serves_all(self):
        script = Script(quota=1000, sites=("alpha", "beta"),
                        rounds=(Round({"alpha": 7, "beta": 9}),))
        ideal = ideal_admissions(script)
        self.assertEqual(ideal.total, 16)
        self.assertEqual(ideal.unserved, 0)

    def test_ideal_walks_rounds_in_order(self):
        script = Script(quota=10, sites=("alpha", "beta"),
                        rounds=(Round({"alpha": 12, "beta": 2}),
                                Round({"alpha": 5, "beta": 5})))
        ideal = ideal_admissions(script)
        self.assertEqual(ideal.total, 10)
        self.assertEqual(ideal.per_site["alpha"], 10)
        self.assertEqual(ideal.per_site["beta"], 0)

    def test_ideal_ignores_partition(self):
        partitioned = Script(quota=100, sites=("alpha", "beta"),
                             rounds=(Round({"alpha": 4, "beta": 6}, down=("alpha",)),))
        ideal = ideal_admissions(partitioned)
        self.assertEqual(ideal.total, 10)


class PlayoutTest(unittest.TestCase):
    def test_playout_matches_ideal_without_partition(self):
        script = make_script(7, quota=10 ** 6, rounds=4, partitions=0)
        ideal = ideal_admissions(script)
        result = playout(script, naive_site)
        total = sum(result.admitted.values())
        self.assertEqual(total, ideal.total)
        self.assertEqual(ideal.unserved, 0)
        self.assertEqual(result.admitted["alpha"], ideal.per_site["alpha"])
        self.assertEqual(result.admitted["beta"], ideal.per_site["beta"])

    def test_playout_loses_partition_round_arrivals(self):
        script = make_script(11, quota=10 ** 6, rounds=4, partitions=2)
        lost = 0
        for rnd in script.rounds:
            for name in rnd.down:
                lost += rnd.arrivals[name]
        ideal = ideal_admissions(script)
        reasons = {}

        def watch(index, rnd, ledger, sites):
            for name in rnd.down:
                reasons[(index, name)] = sites[name].blocked_last()

        result = playout(script, naive_site, on_round=watch)
        self.assertEqual(sum(result.admitted.values()), ideal.total - lost)
        self.assertEqual(len(reasons), 2)
        for reason in reasons.values():
            self.assertEqual(reason, "link_down")

    def test_playout_quota_binding_hits_pool_limit(self):
        script = make_script(13, quota=120, rounds=4, partitions=0)
        ideal = ideal_admissions(script)
        self.assertEqual(ideal.total, 120)
        result = playout(script, naive_site)
        self.assertEqual(sum(result.admitted.values()), 120)
        self.assertEqual(result.ledger.remaining(), 0)

    def test_playout_totals_reproducible(self):
        script = make_script(17, quota=10 ** 6, rounds=3, partitions=1)
        first = playout(script, naive_site)
        second = playout(script, naive_site)
        self.assertEqual(first.admitted, second.admitted)

    def test_playout_keeps_books_balanced(self):
        script = make_script(19, quota=300, rounds=3, partitions=1)
        result = playout(script, naive_site)
        ledger = result.ledger
        self.assertEqual(ledger.remaining() + ledger.outstanding(), ledger.total())
        self.assertEqual(sum(result.admitted.values()), ledger.outstanding())

    def test_playout_joins_all_workers(self):
        script = make_script(23, rounds=2, partitions=0)
        threads_before = threading.active_count()
        playout(script, naive_site)
        self.assertEqual(threading.active_count(), threads_before)

    def test_on_round_observes_each_round(self):
        script = make_script(29, rounds=3, partitions=1)
        seen = []
        playout(script, naive_site,
                on_round=lambda index, rnd, ledger, sites: seen.append(index))
        self.assertEqual(seen, [0, 1, 2])


if __name__ == "__main__":
    unittest.main()
