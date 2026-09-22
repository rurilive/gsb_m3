"""QuotaTree 行为测试：单测、固定种子对拍参考实现、压力采样与性能。"""

import random
import time
import unittest

from quotatree import Ledger, QuotaTree, UnknownTeam


class RefTree:
    """逐层重算的参考实现：只留原始状态，查询时从头算，用来对拍 QuotaTree。"""

    def __init__(self, total):
        self.limit = {"root": total}
        self.parent = {"root": None}
        self.children = {"root": []}
        self.own_used = {"root": 0}
        self.loans = {"root": {}}  # 借款人 -> {祖先: 数量}

    def _lent(self):
        lent = dict.fromkeys(self.limit, 0)
        for borrowed in self.loans.values():
            for ancestor, amount in borrowed.items():
                lent[ancestor] += amount
        return lent

    def _idle(self, name, lent):
        return (self.limit[name] - self.own_used[name]
                - sum(self.limit[c] for c in self.children[name]) - lent[name])

    def _available(self, name, lent):
        total = 0
        while name is not None:
            total += self._idle(name, lent)
            name = self.parent[name]
        return total

    def snapshot(self):
        lent = self._lent()
        return {
            name: (
                self._available(name, lent),
                self.own_used[name] + sum(self.loans[name].values()),
                self._idle(name, lent),
                self.limit[name],
                sum(self.loans[name].values()),
            )
            for name in self.limit
        }

    def add_node(self, name, parent, limit):
        self.limit[name] = limit
        self.parent[name] = parent
        self.children.setdefault(parent, []).append(name)
        self.children[name] = []
        self.own_used[name] = 0
        self.loans[name] = {}

    def acquire(self, name, amount):
        lent = self._lent()
        if self._available(name, lent) < amount:
            return False
        take = min(amount, self._idle(name, lent))
        self.own_used[name] += take
        need = amount - take
        ancestor = self.parent[name]
        while need > 0:
            part = min(self._idle(ancestor, lent), need)
            if part:
                self.loans[name][ancestor] = self.loans[name].get(ancestor, 0) + part
                lent[ancestor] += part
                need -= part
            ancestor = self.parent[ancestor]
        return True

    def release(self, name, amount):
        repay = min(amount, sum(self.loans[name].values()))
        left = repay
        ancestor = self.parent[name]
        while left > 0:
            loan = self.loans[name].get(ancestor, 0)
            if loan:
                pay = min(loan, left)
                if pay == loan:
                    del self.loans[name][ancestor]
                else:
                    self.loans[name][ancestor] = loan - pay
                left -= pay
            ancestor = self.parent[ancestor]
        self.own_used[name] -= amount - repay

    def shrink(self, name, new_limit):
        lent = self._lent()
        charge = (self.own_used[name] + lent[name]
                  + sum(self.limit[c] for c in self.children[name]))
        target = max(new_limit, charge)
        if target >= self.limit[name]:
            return []
        delta = self.limit[name] - target
        self.limit[name] = target
        ancestor = self.parent[name]
        while ancestor is not None:
            self.limit[ancestor] -= delta
            ancestor = self.parent[ancestor]
        lent = self._lent()
        squeezed = []
        stack = [name]
        while stack:
            current = stack.pop()
            if self._available(current, lent) > 0:
                continue
            squeezed.append(current)
            stack.extend(self.children[current])
        return sorted(squeezed)


def tree_snapshot(tree):
    return {
        name: (
            tree.available(name),
            tree.used(name),
            tree.idle(name),
            tree.limit(name),
            tree.borrowed(name),
        )
        for name in tree.teams()
    }


def build_demo_tree():
    """root(1000) -> eng(600) -> web(150), api(100)；root -> ops(400)。"""
    tree = QuotaTree(1000)
    tree.add_node("eng", "root", 600)
    tree.add_node("ops", "root", 400)
    tree.add_node("web", "eng", 150)
    tree.add_node("api", "eng", 100)
    return tree


class StructureTest(unittest.TestCase):
    def test_add_node_carves_parent_idle(self):
        tree = build_demo_tree()
        self.assertEqual(tree.idle("root"), 0)
        self.assertEqual(tree.idle("eng"), 350)
        self.assertEqual(tree.children("eng"), ["api", "web"])
        self.assertEqual(tree.parent("web"), "eng")
        self.assertIsNone(tree.parent("root"))
        self.assertEqual(tree.root, "root")

    def test_add_node_validates(self):
        tree = build_demo_tree()
        with self.assertRaises(ValueError):
            tree.add_node("web", "root", 10)      # 重名
        with self.assertRaises(ValueError):
            tree.add_node("big", "eng", 351)      # 超出 eng 闲置
        with self.assertRaises(UnknownTeam):
            tree.add_node("x", "nope", 10)        # 父团队不存在
        for bad in ("", None, 7):
            with self.assertRaises(ValueError):
                tree.add_node(bad, "root", 10)
        for bad in (0, -1, 2.5, True, "10"):
            with self.assertRaises(ValueError):
                tree.add_node("y", "root", bad)

    def test_bad_root_args(self):
        for bad in (0, -1, 2.5, True, "10"):
            with self.assertRaises(ValueError):
                QuotaTree(bad)
        with self.assertRaises(ValueError):
            QuotaTree(10, name="")

    def test_unknown_team_raises(self):
        tree = build_demo_tree()
        for call in (tree.acquire, tree.release):
            with self.assertRaises(UnknownTeam):
                call("nope", 1)
        for call in (tree.available, tree.used, tree.limit, tree.idle,
                     tree.borrowed, tree.children, tree.parent):
            with self.assertRaises(UnknownTeam):
                call("nope")
        with self.assertRaises(UnknownTeam):
            tree.shrink("nope", 1)


class BorrowTest(unittest.TestCase):
    def test_available_sums_ancestor_idle(self):
        tree = build_demo_tree()
        self.assertEqual(tree.available("web"), 150 + 350 + 0)
        self.assertEqual(tree.available("ops"), 400)
        self.assertEqual(tree.available("root"), 0)

    def test_borrow_nearest_ancestor_first(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 60)
        tree.add_node("b", "a", 10)
        self.assertTrue(tree.acquire("b", 25))
        self.assertEqual(tree.used("b"), 25)
        self.assertEqual(tree.borrowed("b"), 15)   # 自有 10 + 向 a 借 15
        self.assertEqual(tree.idle("a"), 35)       # 借出的是 a 的闲置
        self.assertEqual(tree.idle("root"), 40)    # 没惊动 root

    def test_borrow_walks_up_the_chain(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 20)
        tree.add_node("b", "a", 10)
        self.assertTrue(tree.acquire("b", 50))
        self.assertEqual(tree.borrowed("b"), 40)   # a 出 10，root 出 30
        self.assertEqual(tree.idle("a"), 0)
        self.assertEqual(tree.idle("root"), 50)
        self.assertEqual(tree.available("b"), 50)

    def test_acquire_rejected_when_chain_dry(self):
        tree = build_demo_tree()
        self.assertFalse(tree.acquire("web", 501))
        self.assertEqual(tree.used("web"), 0)
        self.assertEqual(tree.idle("eng"), 350)

    def test_release_repays_borrowed_first(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 20)
        tree.add_node("b", "a", 10)
        tree.acquire("b", 50)                      # 借 a 10、root 30
        tree.release("b", 25)                      # 先还借的：a 10 + root 15
        self.assertEqual(tree.borrowed("b"), 15)
        self.assertEqual(tree.idle("a"), 10)
        self.assertEqual(tree.idle("root"), 65)
        tree.release("b", 25)                      # 还完借的 15，再退自有 10
        self.assertEqual(tree.used("b"), 0)
        self.assertEqual(tree.idle("a"), 10)
        self.assertEqual(tree.idle("root"), 80)
        self.assertEqual(tree.available("b"), 100)

    def test_release_over_used_raises(self):
        tree = build_demo_tree()
        tree.acquire("web", 20)
        with self.assertRaises(ValueError):
            tree.release("web", 21)
        with self.assertRaises(ValueError):
            tree.release("web", 0)
        with self.assertRaises(ValueError):
            tree.acquire("web", -3)


class ReplayTest(unittest.TestCase):
    def test_same_req_id_counts_once(self):
        ledger = Ledger()
        tree = QuotaTree(100, ledger=ledger)
        tree.add_node("a", "root", 50)
        self.assertTrue(tree.acquire("a", 30, req_id="r1"))
        self.assertTrue(tree.acquire("a", 30, req_id="r1"))
        self.assertEqual(tree.used("a"), 30)
        stats = ledger.stats()
        self.assertEqual(stats["acquire"], 1)
        self.assertEqual(stats["replay"], 1)

    def test_rejected_acquire_replays_as_rejected(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 50)
        self.assertFalse(tree.acquire("a", 101, req_id="r2"))
        self.assertFalse(tree.acquire("a", 101, req_id="r2"))
        self.assertEqual(tree.used("a"), 0)

    def test_release_replay_does_not_inflate_available(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 50)
        tree.acquire("a", 40)
        tree.release("a", 40, req_id="r3")
        tree.release("a", 40, req_id="r3")
        self.assertEqual(tree.used("a"), 0)
        self.assertEqual(tree.available("a"), 100)  # 不超上限

    def test_req_id_reuse_with_other_params_raises(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 50)
        tree.add_node("b", "root", 50)
        tree.acquire("a", 10, req_id="r4")
        with self.assertRaises(ValueError):
            tree.acquire("a", 11, req_id="r4")
        with self.assertRaises(ValueError):
            tree.acquire("b", 10, req_id="r4")
        with self.assertRaises(ValueError):
            tree.release("a", 10, req_id="r4")


class ShrinkTest(unittest.TestCase):
    def test_shrink_cuts_subtree_available(self):
        tree = build_demo_tree()
        squeezed = tree.shrink("eng", 200)
        self.assertEqual(tree.limit("eng"), 250)   # 下级占着 250，缩不动
        self.assertEqual(tree.idle("eng"), 0)      # 下级占去 150+100
        self.assertEqual(tree.limit("root"), 650)  # 收走的额度整链减掉
        self.assertEqual(tree.available("web"), 150)
        self.assertEqual(tree.available("ops"), 400)  # 别的子树不受影响
        self.assertEqual(squeezed, ["eng"])        # eng 自己没余量了

    def test_shrink_stops_at_charge(self):
        tree = build_demo_tree()
        tree.acquire("web", 200)                   # web 借 eng 50
        squeezed = tree.shrink("eng", 100)
        self.assertEqual(tree.limit("eng"), 300)   # 250 下级 + 50 借出，缩不动
        self.assertEqual(squeezed, ["eng", "web"])
        self.assertFalse(tree.acquire("web", 1))   # 没余量，新申请被拒
        self.assertTrue(tree.acquire("api", 1))    # api 自己还有闲置

    def test_shrink_noop_when_not_shrinking(self):
        tree = build_demo_tree()
        self.assertEqual(tree.shrink("eng", 600), [])
        self.assertEqual(tree.shrink("eng", 900), [])
        self.assertEqual(tree.limit("eng"), 600)

    def test_shrink_validates_args(self):
        tree = build_demo_tree()
        for bad in (-1, 2.5, True, "10", None):
            with self.assertRaises(ValueError):
                tree.shrink("eng", bad)

    def test_shrink_root(self):
        tree = QuotaTree(100)
        tree.add_node("a", "root", 40)
        self.assertEqual(tree.shrink("root", 60), [])
        self.assertEqual(tree.limit("root"), 60)
        self.assertEqual(tree.available("a"), 60)
        self.assertEqual(tree.shrink("root", 10), ["root"])  # 占用压到 40 为止
        self.assertEqual(tree.limit("root"), 40)
        self.assertFalse(tree.acquire("a", 41))


class LedgerTest(unittest.TestCase):
    def test_entries_flow_through_ledger(self):
        ledger = Ledger()
        tree = QuotaTree(100, ledger=ledger)
        tree.add_node("a", "root", 50)
        tree.acquire("a", 101, req_id="no")        # 被拒也留痕
        tree.acquire("a", 30, req_id="yes")
        tree.release("a", 10)
        entries = ledger.entries()
        self.assertEqual(
            [(e["team"], e["kind"], e["amount"], e["ok"], e["req_id"])
             for e in entries],
            [("a", "acquire", 101, False, "no"),
             ("a", "acquire", 30, True, "yes"),
             ("a", "release", 10, True, None)])


class CrossCheckTest(unittest.TestCase):
    def test_random_ops_match_reference(self):
        rng = random.Random(20260922)
        tree = QuotaTree(3000)
        ref = RefTree(3000)
        names = ["root"]
        for i in range(150):
            parent = rng.choice(names)
            idle = tree.idle(parent)
            if idle < 1:
                continue
            name = "t%03d" % i
            limit = rng.randint(1, idle)
            tree.add_node(name, parent, limit)
            ref.add_node(name, parent, limit)
            names.append(name)
        history = {}  # req_id -> (kind, name, amount, result)
        for step in range(3000):
            roll = rng.random()
            if roll < 0.10 and history:
                req_id = rng.choice(sorted(history))
                kind, name, amount, result = history[req_id]
                call = tree.acquire if kind == "acquire" else tree.release
                self.assertEqual(call(name, amount, req_id=req_id), result)
                continue
            name = rng.choice(names)
            req_id = "req-%d" % step if rng.random() < 0.4 else None
            if roll < 0.55:
                amount = rng.randint(1, 80)
                got = tree.acquire(name, amount, req_id=req_id)
                self.assertEqual(got, ref.acquire(name, amount))
                if req_id is not None:
                    history[req_id] = ("acquire", name, amount, got)
            elif roll < 0.90:
                used = tree.used(name)
                if used == 0:
                    continue
                amount = rng.randint(1, used)
                self.assertTrue(tree.release(name, amount, req_id=req_id))
                ref.release(name, amount)
                if req_id is not None:
                    history[req_id] = ("release", name, amount, True)
            else:
                new_limit = rng.randint(0, tree.limit(name) + 20)
                self.assertEqual(tree.shrink(name, new_limit),
                                 ref.shrink(name, new_limit))
            self.assertEqual(tree_snapshot(tree), ref.snapshot())


class StressTest(unittest.TestCase):
    def test_invariants_hold_under_random_load(self):
        rng = random.Random(415)
        total = 10 ** 7
        tree = QuotaTree(total)
        names = ["root"]
        for i in range(2000):
            parent = rng.choice(names)
            if tree.idle(parent) < 1:
                continue
            name = "n%04d" % i
            tree.add_node(name, parent, rng.randint(1, tree.idle(parent)))
            names.append(name)
        for step in range(30000):
            name = rng.choice(names)
            roll = rng.random()
            if roll < 0.6:
                tree.acquire(name, rng.randint(1, 300))
            elif roll < 0.97:
                used = tree.used(name)
                if used:
                    tree.release(name, rng.randint(1, used))
            else:
                tree.shrink(name, rng.randint(0, tree.limit(name)))
            if step % 449 == 0:
                self._check_invariants(tree, rng.sample(names, 40))
        self._check_invariants(tree, names)
        # 占用不超额度：全树占用合计不超过当前总额度
        self.assertLessEqual(sum(tree.used(n) for n in names),
                             tree.limit("root"))

    def _check_invariants(self, tree, names):
        for name in names:
            own_used = tree.used(name) - tree.borrowed(name)
            children_sum = sum(tree.limit(c) for c in tree.children(name))
            self.assertGreaterEqual(tree.idle(name), 0)
            self.assertGreaterEqual(own_used, 0)
            self.assertGreaterEqual(tree.borrowed(name), 0)
            self.assertGreaterEqual(tree.available(name), 0)
            # 下级之和加自用不超上级
            self.assertLessEqual(children_sum + own_used, tree.limit(name))


class PerfTest(unittest.TestCase):
    def test_15k_nodes_100k_ops_within_10s(self):
        rng = random.Random(2026)
        tree = QuotaTree(10 ** 8)
        names = ["root"]
        for i in range(15000):
            parent = rng.choice(names)
            while tree.idle(parent) < 1:
                parent = rng.choice(names)
            tree.add_node("p%05d" % i, parent,
                          rng.randint(1, min(tree.idle(parent), 20000)))
            names.append("p%05d" % i)
        started = time.perf_counter()
        for _ in range(100000):
            name = rng.choice(names)
            if rng.random() < 0.6:
                tree.acquire(name, rng.randint(1, 400))
            else:
                used = tree.used(name)
                if used:
                    tree.release(name, rng.randint(1, used))
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 10.0,
                        "十万次借还耗时 %.2fs，超了 10s" % elapsed)
        self.assertLessEqual(sum(tree.used(n) for n in names),
                             tree.limit("root"))


if __name__ == "__main__":
    unittest.main()
