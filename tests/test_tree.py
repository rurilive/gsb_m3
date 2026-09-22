"""QuotaTree 行为与性能测试：层级借还、幂等重放、缩容、参考对拍与压力。"""

import random
import time
import unittest

from quotatree import Ledger, QuotaTree, UnknownTeam


class RefTree:
    """逐层重算的参考实现：每次全树自底向上重算 effective 再汇总。"""

    def __init__(self, total):
        self.limit = {"root": total}
        self.used = {"root": 0}
        self.parent = {"root": None}
        self.children = {"root": []}

    def add_node(self, name, parent, limit):
        self.limit[name] = limit
        self.used[name] = 0
        self.parent[name] = parent
        self.children[name] = []
        self.children[parent].append(name)

    def _effective(self):
        eff = {}

        def walk(x):
            sub = self.used[x]
            for c in self.children[x]:
                sub += walk(c)
            eff[x] = max(self.limit[x], sub)
            return eff[x]

        walk("root")
        return eff

    def available(self, name):
        eff = self._effective()
        total = 0
        x = name
        while x is not None:
            total += eff[x] - self.used[x] - sum(eff[c] for c in self.children[x])
            x = self.parent[x]
        return total

    def available_all(self):
        eff = self._effective()
        free = {}
        for x in eff:
            free[x] = eff[x] - self.used[x] - sum(eff[c] for c in self.children[x])
        out = {}
        for x in eff:
            total = 0
            y = x
            while y is not None:
                total += free[y]
                y = self.parent[y]
            out[x] = total
        return out

    def acquire(self, name, amount):
        if amount <= self.available(name):
            self.used[name] += amount
            return True
        return False

    def release(self, name, amount):
        assert 0 < amount <= self.used[name]
        self.used[name] -= amount

    def _subtree(self, name):
        out = []
        stack = [name]
        while stack:
            x = stack.pop()
            out.append(x)
            stack.extend(self.children[x])
        return out

    def shrink(self, name, new_limit):
        if new_limit >= self.limit[name]:
            return []
        eff = self._effective()
        borrowed = eff[name] - self.limit[name]
        cs = sum(eff[c] for c in self.children[name])
        floor = self.used[name] + cs - borrowed
        members = self._subtree(name)
        before = {m: self.available(m) for m in members}
        self.limit[name] = max(new_limit, floor)
        return sorted(m for m in members
                      if before[m] > 0 and self.available(m) == 0)


class BuildTest(unittest.TestCase):
    def test_add_node_carves_from_parent_idle(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 60)
        self.assertEqual(tree.free("root"), 40)
        with self.assertRaises(ValueError):
            tree.add_node("b", "root", 50)
        tree.add_node("b", "root", 40)
        self.assertEqual(tree.free("root"), 0)
        self.assertEqual(tree.nodes(), ["a", "b", "root"])
        self.assertEqual(tree.children("root"), ["a", "b"])
        self.assertEqual(tree.parent("a"), "root")
        self.assertIsNone(tree.parent("root"))

    def test_bad_nodes_rejected(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 10)
        with self.assertRaises(ValueError):
            tree.add_node("a", "root", 5)
        with self.assertRaises(ValueError):
            tree.add_node("", "root", 5)
        with self.assertRaises(ValueError):
            tree.add_node("b", "root", 0)
        with self.assertRaises(UnknownTeam):
            tree.add_node("b", "nope", 5)
        with self.assertRaises(UnknownTeam):
            tree.available("nope")

    def test_bad_total_rejected(self):
        for bad in (0, -1, 2.5, True, "10", None):
            with self.assertRaises(ValueError):
                QuotaTree(bad)


class BorrowTest(unittest.TestCase):
    def setUp(self):
        self.tree = QuotaTree(100)
        self.tree.add_node("a", "root", 60)
        self.tree.add_node("b", "a", 50)

    def test_acquire_nets_out_children_share(self):
        # 下级 b 占着 50 份额，a 自留闲置只有 10
        self.assertTrue(self.tree.acquire("a", 10))
        self.assertEqual(self.tree.used("a"), 10)
        self.assertEqual(self.tree.borrowed("a"), 0)
        self.assertEqual(self.tree.available("a"), 40)
        self.assertTrue(self.tree.acquire("a", 20))
        self.assertEqual(self.tree.borrowed("a"), 20)
        self.assertEqual(self.tree.available("a"), 20)

    def test_borrow_from_parent_idle(self):
        self.assertTrue(self.tree.acquire("b", 70))
        self.assertEqual(self.tree.used("b"), 70)
        self.assertEqual(self.tree.borrowed("b"), 20)
        self.assertEqual(self.tree.effective("b"), 70)
        # b 的 70 超出 a 的份额，a 自己也被迫向 root 借 10
        self.assertEqual(self.tree.borrowed("a"), 10)
        self.assertEqual(self.tree.free("a"), 0)
        self.assertEqual(self.tree.available("b"), 30)

    def test_borrow_cascades_to_grandparent(self):
        self.assertTrue(self.tree.acquire("b", 50))
        self.assertTrue(self.tree.acquire("a", 30))
        # a 自用 30 + 下级 50 = 80，超出自己份额 60，向 root 借 20
        self.assertEqual(self.tree.borrowed("a"), 20)
        self.assertEqual(self.tree.effective("a"), 80)
        self.assertEqual(self.tree.free("root"), 100 - 80)
        self.assertEqual(self.tree.available("b"), 20)

    def test_rejected_when_ancestors_full(self):
        self.assertTrue(self.tree.acquire("b", 50))
        self.assertTrue(self.tree.acquire("a", 50))
        self.assertEqual(self.tree.free("root"), 0)
        self.assertFalse(self.tree.acquire("b", 1))
        self.assertFalse(self.tree.acquire("a", 1))
        self.assertEqual(self.tree.available("b"), 0)
        self.assertEqual(self.tree.used("b"), 50)

    def test_rejected_acquire_changes_nothing(self):
        self.assertFalse(self.tree.acquire("b", 200))
        self.assertEqual(self.tree.used("b"), 0)
        self.assertEqual(self.tree.borrowed("b"), 0)
        self.assertEqual(self.tree.available("b"), 100)

    def test_bad_amounts_rejected(self):
        for bad in (0, -3, 1.5, True, None, "5"):
            with self.assertRaises(ValueError):
                self.tree.acquire("b", bad)
            with self.assertRaises(ValueError):
                self.tree.release("b", bad)


class ReleaseTest(unittest.TestCase):
    def setUp(self):
        self.tree = QuotaTree(100)
        self.tree.add_node("a", "root", 60)
        self.tree.add_node("b", "a", 50)

    def test_release_repays_borrowed_first(self):
        self.tree.acquire("b", 70)
        self.assertEqual(self.tree.borrowed("b"), 20)
        self.tree.release("b", 10)
        self.assertEqual(self.tree.used("b"), 60)
        self.assertEqual(self.tree.borrowed("b"), 10)
        self.tree.release("b", 15)
        self.assertEqual(self.tree.used("b"), 45)
        self.assertEqual(self.tree.borrowed("b"), 0)
        self.assertEqual(self.tree.free("a"), 60 - 50)

    def test_release_cascades_back_to_root(self):
        self.tree.acquire("b", 50)
        self.tree.acquire("a", 50)
        self.assertEqual(self.tree.borrowed("a"), 40)
        self.assertEqual(self.tree.free("root"), 0)
        self.tree.release("a", 50)
        self.assertEqual(self.tree.borrowed("a"), 0)
        self.assertEqual(self.tree.free("root"), 40)

    def test_release_over_used_raises(self):
        self.tree.acquire("b", 10)
        with self.assertRaises(ValueError):
            self.tree.release("b", 11)
        self.assertEqual(self.tree.used("b"), 10)


class ReplayTest(unittest.TestCase):
    def setUp(self):
        self.ledger = Ledger()
        self.tree = QuotaTree(100, ledger=self.ledger)
        self.tree.add_node("a", "root", 60)
        self.tree.add_node("b", "a", 50)

    def test_same_req_id_charges_once(self):
        self.assertTrue(self.tree.acquire("b", 40, req_id="r1"))
        self.assertTrue(self.tree.acquire("b", 40, req_id="r1"))
        self.assertEqual(self.tree.used("b"), 40)
        kinds = [e["kind"] for e in self.ledger.by_team("b")]
        self.assertEqual(kinds, ["acquire", "replay"])

    def test_repeated_release_does_not_over_credit(self):
        self.tree.acquire("b", 40, req_id="r1")
        self.tree.release("b", 40, req_id="r2")
        self.tree.release("b", 40, req_id="r2")
        self.assertEqual(self.tree.used("b"), 0)
        self.assertEqual(self.tree.free("b"), 50)
        self.assertEqual(self.tree.available("b"), 100)

    def test_failed_acquire_replay_stays_failed(self):
        self.assertFalse(self.tree.acquire("b", 200, req_id="r3"))
        self.assertFalse(self.tree.acquire("b", 200, req_id="r3"))
        self.assertEqual(self.tree.used("b"), 0)

    def test_reused_req_id_with_other_params_raises(self):
        self.tree.acquire("b", 10, req_id="r4")
        with self.assertRaises(ValueError):
            self.tree.acquire("b", 20, req_id="r4")
        with self.assertRaises(ValueError):
            self.tree.acquire("a", 10, req_id="r4")
        with self.assertRaises(ValueError):
            self.tree.release("b", 10, req_id="r4")
        self.assertEqual(self.tree.used("b"), 10)

    def test_rejected_release_does_not_burn_req_id(self):
        self.tree.acquire("b", 10)
        with self.assertRaises(ValueError):
            self.tree.release("b", 20, req_id="r9")
        self.assertTrue(self.tree.release("b", 10, req_id="r9"))
        self.assertEqual(self.tree.used("b"), 0)


class ShrinkTest(unittest.TestCase):
    def setUp(self):
        self.tree = QuotaTree(100)
        self.tree.add_node("a", "root", 60)
        self.tree.add_node("b", "a", 20)

    def test_shrink_reclaims_idle_share(self):
        self.tree.acquire("a", 20)
        self.assertEqual(self.tree.shrink("a", 40), [])
        self.assertEqual(self.tree.limit("a"), 40)
        self.assertEqual(self.tree.free("root"), 60)

    def test_shrink_stops_at_floor(self):
        # 自用 30 + 下级 20 = 50，下限就是 50，缩不到 10
        self.tree.acquire("a", 30)
        self.tree.shrink("a", 10)
        self.assertEqual(self.tree.limit("a"), 50)
        self.assertEqual(self.tree.free("root"), 50)
        with self.assertRaises(ValueError):
            self.tree.shrink("a", -1)
        with self.assertRaises(ValueError):
            self.tree.shrink("a", 2.5)

    def test_shrink_growth_is_noop(self):
        self.assertEqual(self.tree.shrink("a", 80), [])
        self.assertEqual(self.tree.limit("a"), 60)

    def test_shrink_middle_node_keeps_subtree_reach(self):
        self.tree.acquire("b", 20)
        self.assertEqual(self.tree.shrink("a", 50), [])
        self.assertEqual(self.tree.available("b"), 80)

    def test_shrink_root_presses_teams_to_zero(self):
        self.tree.acquire("b", 20)
        self.tree.acquire("a", 40)
        # root 闲置 40，a、b、root 可用各 40；砍掉 40 后全部压零
        pressed = self.tree.shrink("root", 60)
        self.assertEqual(pressed, ["a", "b", "root"])
        self.assertEqual(self.tree.available("a"), 0)
        self.assertFalse(self.tree.acquire("b", 1))

    def test_shrink_root_partial_press(self):
        self.tree.acquire("b", 20)
        self.tree.acquire("a", 40)
        self.assertEqual(self.tree.shrink("root", 80), [])
        self.assertEqual(self.tree.available("b"), 20)


class LedgerWiringTest(unittest.TestCase):
    def test_attempts_are_recorded_in_order(self):
        ledger = Ledger()
        tree = QuotaTree(100, ledger=ledger)
        tree.add_node("a", "root", 60)
        tree.acquire("a", 30, req_id="a1")
        tree.acquire("a", 90, req_id="a2")
        tree.release("a", 10, req_id="a3")
        self.assertEqual(
            [(e["seq"], e["team"], e["kind"], e["amount"], e["ok"])
             for e in ledger.entries()],
            [(1, "a", "acquire", 30, True),
             (2, "a", "acquire", 90, False),
             (3, "a", "release", 10, True)])
        stats = ledger.stats()
        self.assertEqual(stats["acquire"], 2)
        self.assertEqual(stats["release"], 1)
        self.assertEqual(stats["rejected"], 1)

    def test_tree_makes_own_ledger(self):
        self.assertIsInstance(QuotaTree(10).ledger, Ledger)


class DifferentialTest(unittest.TestCase):
    def test_random_ops_match_reference(self):
        rng = random.Random(20260922)
        tree = QuotaTree(500)
        ref = RefTree(500)
        names = ["root"]
        while len(names) < 120:
            parent = rng.choice(names)
            if tree.free(parent) < 1:
                continue
            name = "n%d" % len(names)
            limit = rng.randint(1, tree.free(parent))
            tree.add_node(name, parent, limit)
            ref.add_node(name, parent, limit)
            names.append(name)

        for _ in range(3000):
            roll = rng.random()
            name = rng.choice(names)
            if roll < 0.45:
                amount = rng.randint(1, 60)
                got = tree.acquire(name, amount)
                self.assertEqual(got, ref.acquire(name, amount))
            elif roll < 0.9:
                used = tree.used(name)
                if used == 0:
                    continue
                amount = rng.randint(1, used)
                tree.release(name, amount)
                ref.release(name, amount)
            else:
                new_limit = rng.randint(0, tree.limit(name) + 30)
                pressed = tree.shrink(name, new_limit)
                self.assertEqual(pressed, ref.shrink(name, new_limit))
            snapshot = ref.available_all()
            for n in names:
                self.assertEqual(tree.available(n), snapshot[n],
                                 "available 不一致: %s" % n)
                self.assertEqual(tree.used(n), ref.used[n],
                                 "used 不一致: %s" % n)


class StressTest(unittest.TestCase):
    def test_15k_nodes_100k_ops_under_10s(self):
        rng = random.Random(165)
        tree = QuotaTree(200_000)
        names = ["root"]
        started = time.monotonic()
        while len(names) < 15_000:
            parent = rng.choice(names)
            free = tree.free(parent)
            if free < 1:
                continue
            name = "n%d" % len(names)
            tree.add_node(name, parent, rng.randint(1, free))
            names.append(name)

        for i in range(100_000):
            name = rng.choice(names)
            if rng.random() < 0.5:
                tree.acquire(name, rng.randint(1, 40))
            else:
                used = tree.used(name)
                if used:
                    tree.release(name, rng.randint(1, used))
            if i % 500 == 0:
                for probe in rng.sample(names, 20) + ["root"]:
                    # 占用不超额度
                    self.assertLessEqual(tree.used(probe), tree.effective(probe))
                    # 下级之和加自用不超上级
                    self.assertGreaterEqual(tree.free(probe), 0)
                    sub = sum(tree.effective(c) for c in tree.children(probe))
                    self.assertLessEqual(sub + tree.used(probe),
                                         tree.effective(probe))
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 10.0,
                        "一万五千节点十万次借还耗时 %.1fs，超了 10s" % elapsed)


if __name__ == "__main__":
    unittest.main()
