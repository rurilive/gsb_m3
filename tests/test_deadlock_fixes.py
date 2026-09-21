"""死锁检测修复的回归测试（基线文件一字未改，这里另开新文件）。

覆盖生产上四类误报与性能回归：
1. 环解开后健康检查立刻解除，不留陈旧结论；
2. 曾经互等、当下无等待，以及崩溃幽灵边 + pid 复用，不许再报环；
3. 环成员只含真正成环的节点，且顺序严格等于 oracle 的钉死规则，
   同一张图无论经过什么变动序列，报告恒等；
4. 随机事件序列下每一步都与 waitgraph.oracle.FullScan 对拍一致；
5. 十万节点图上单次变动连带 health() 只碰与变动相关的节点，
   访问计数与节点规模无关，压在千级以内。
"""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from waitgraph import FullScan, ResourceRegistry  # noqa: E402
from waitgraph.detector import DeadlockDetector as Detector  # noqa: E402


WAYNE, TRISH, NEO = 4101, 4102, 4103


def close_pair_registry():
    reg = ResourceRegistry()
    reg.acquire(WAYNE, "idx-a")
    reg.acquire(TRISH, "idx-b")
    reg.acquire(WAYNE, "idx-b")
    reg.acquire(TRISH, "idx-a")
    return reg


class StaleAlarmTest(unittest.TestCase):
    """环解开后结论必须当场失效。"""

    def test_release_breaks_cycle_clears_alarm(self):
        reg = close_pair_registry()
        self.assertTrue(reg.health()["deadlocked"])
        reg.release(TRISH, "idx-b")
        self.assertFalse(reg.detector.deadlocked())
        self.assertEqual(reg.detector.cycle_members(), [])
        self.assertEqual(reg.health(), {"deadlocked": False, "cycle": []})

    def test_drop_breaks_cycle_clears_alarm(self):
        reg = close_pair_registry()
        reg.drop(WAYNE)
        self.assertFalse(reg.health()["deadlocked"])
        self.assertEqual(reg.health()["cycle"], [])

    def test_reclose_after_break_reports_again(self):
        reg = close_pair_registry()
        reg.release(TRISH, "idx-b")
        self.assertFalse(reg.health()["deadlocked"])
        reg.acquire(TRISH, "idx-c")        # TRISH 拿到新资源
        reg.acquire(WAYNE, "idx-c")        # WAYNE 反等 TRISH，与旧边重闭环
        self.assertTrue(reg.health()["deadlocked"])
        self.assertEqual(reg.health()["cycle"], [WAYNE, TRISH])


class GhostEdgeTest(unittest.TestCase):
    """崩溃残留的边要双向摘干净，pid 复用不许诈尸。"""

    def test_drop_removes_both_directions_in_graph(self):
        reg = close_pair_registry()
        reg.drop(TRISH)
        self.assertEqual(reg.detector.graph.waits(), [])
        self.assertEqual(reg.detector.graph.holders(TRISH), [])
        self.assertEqual(reg.detector.graph.waiters_of(TRISH), [])

    def test_pid_reuse_after_drop_not_a_cycle(self):
        reg = ResourceRegistry()
        reg.acquire(TRISH, "job-q")
        reg.acquire(WAYNE, "cfg")
        reg.acquire(WAYNE, "job-q")
        reg.drop(TRISH)
        reg.acquire(TRISH, "cfg")
        oracle = FullScan(reg).cycle_members()
        self.assertEqual(reg.detector.cycle_members(), oracle)
        self.assertEqual(oracle, [])

    def test_mutual_wait_in_history_is_not_a_cycle(self):
        """两个进程先后互相等过，但当下谁都没在等。"""
        reg = ResourceRegistry()
        reg.acquire(WAYNE, "r1")
        reg.acquire(TRISH, "r1")        # TRISH -> WAYNE
        reg.release(WAYNE, "r1")        # 交给 TRISH，边消失
        reg.acquire(TRISH, "r2")
        reg.acquire(WAYNE, "r2")        # WAYNE -> TRISH
        reg.release(TRISH, "r2")        # 交给 WAYNE，边消失
        self.assertEqual(reg.waits(), [])
        self.assertFalse(reg.health()["deadlocked"])
        self.assertEqual(reg.health()["cycle"], [])


class CycleMembersAndOrderTest(unittest.TestCase):
    """成员只能是环上节点；顺序逐字等于 oracle。"""

    def test_chain_upstream_not_in_members(self):
        reg = ResourceRegistry()
        reg.acquire(TRISH, "a")
        reg.acquire(NEO, "b")
        reg.acquire(WAYNE, "a")         # 链条上游：WAYNE -> TRISH
        reg.acquire(TRISH, "b")         # TRISH -> NEO
        reg.acquire(NEO, "a")           # NEO -> TRISH，环是 TRISH<->NEO
        self.assertEqual(reg.detector.cycle_members(),
                         FullScan(reg).cycle_members())
        self.assertEqual(reg.detector.cycle_members(), [TRISH, NEO])

    def test_cycle_starts_with_smallest_pid(self):
        reg = ResourceRegistry()
        reg.load_state({}, [(5, "a", 8), (8, "b", 3), (3, "c", 5)])
        self.assertEqual(reg.detector.cycle_members(), [3, 5, 8])

    def test_smallest_root_reaching_any_cycle_wins(self):
        # 环 2->3->4->2；1 是环上游；0 指向 1。oracle 从 0 起搜，
        # 命中的第一个环成员是 2，报告从 2 开始旋转。
        reg = ResourceRegistry()
        reg.load_state({}, [(0, "x", 1), (1, "y", 2),
                            (2, "a", 3), (3, "b", 4), (4, "c", 2)])
        self.assertEqual(reg.detector.cycle_members(),
                         FullScan(reg).cycle_members())
        self.assertEqual(reg.detector.cycle_members(), [2, 3, 4])

    def test_same_graph_different_histories_same_report(self):
        target = [(0, 1, "a"), (1, 2, "b"), (2, 0, "c"),
                  (3, 4, "d"), (4, 3, "e"), (5, 1, "f")]
        expected = [0, 1, 2]

        det_a = Detector()
        for waiter, holder, resource in target:
            det_a.note_wait(waiter, holder, resource)

        det_b = Detector()
        for waiter, holder, resource in reversed(target):
            det_b.note_wait(waiter, holder, resource)

        det_c = Detector()
        det_c.note_wait(7, 8, "z")
        det_c.note_wait(8, 7, "y")
        det_c.note_wait(6, 0, "x")
        for waiter, holder, resource in target:
            det_c.note_wait(waiter, holder, resource)
        det_c.note_wake(7, "z", 8)
        det_c.note_wake(8, "y", 7)
        det_c.note_wake(6, "x", 0)

        for det in (det_a, det_b, det_c):
            self.assertEqual(det.cycle_members(), expected)

    def test_replace_edge_can_break_and_form_cycles(self):
        """同一等待者改等别人：旧环裂开、新环合上都要判对。"""
        det = Detector()
        det.note_wait(1, 2, "r")
        det.note_wait(2, 1, "s")
        self.assertEqual(det.cycle_members(), [1, 2])
        det.note_wait(2, 3, "s")       # 2 改等 3，1<->2 环解开
        self.assertEqual(det.cycle_members(), [])
        det.note_wait(3, 1, "t")       # 1->2->3->1 新环
        self.assertEqual(det.cycle_members(), [1, 2, 3])


class OracleDifferentialTest(unittest.TestCase):
    """随机注册操作序列，每一步与 FullScan 对拍。"""

    SEQUENCES = 60
    STEPS = 200

    def _run(self, seed, npids=6, nres=5):
        random.seed(seed)
        reg = ResourceRegistry()
        oracle = FullScan(reg)
        for _ in range(self.STEPS):
            choice = random.random()
            pid = random.randrange(npids)
            if choice < 0.55:
                try:
                    reg.acquire(pid, "r%d" % random.randrange(nres))
                except Exception:
                    pass
            elif choice < 0.8:
                held = reg.holds(pid)
                if held:
                    reg.release(pid, random.choice(held))
            else:
                reg.drop(pid)
            oracle_cycle = oracle.cycle_members()
            self.assertEqual(reg.detector.deadlocked(),
                             bool(oracle_cycle),
                             msg="seed=%d waits=%r" % (seed, reg.waits()))
            self.assertEqual(reg.detector.cycle_members(), oracle_cycle,
                             msg="seed=%d waits=%r" % (seed, reg.waits()))
            self.assertEqual(sorted(reg.detector.graph.waits()),
                             sorted(reg.waits()),
                             msg="detector graph drifted from registry")

    def test_random_sequences_match_oracle(self):
        for seed in range(self.SEQUENCES):
            self._run(seed)


class LocalizedCostTest(unittest.TestCase):
    """十万节点：单次变动只碰相关节点，访问计数压在千级以内。"""

    NODES = 100000
    WIDTH = 5
    LIMIT = 1000

    def _chain_registry(self):
        holds = {}
        waits = []
        for base in range(0, self.NODES, self.WIDTH):
            pids = [100000 + base + i for i in range(self.WIDTH)]
            for i in range(self.WIDTH - 1):
                resource = "r-%d" % pids[i]
                holds[resource] = pids[i + 1]
                waits.append((pids[i], resource, pids[i + 1]))
        reg = ResourceRegistry()
        reg.load_state(holds, waits)
        return reg

    def test_changes_and_health_do_not_scale_with_nodes(self):
        reg = self._chain_registry()
        detector = reg.detector
        self.assertEqual(detector.stats()["nodes"], self.NODES)

        detector.reset_stats()
        reg.acquire(100000, "x")
        reg.acquire(100004, "x")          # 局部闭环
        health = reg.health()
        close_visits = detector.stats()["visits"]
        self.assertTrue(health["deadlocked"])

        detector.reset_stats()
        reg.release(100000, "x")          # 环解开
        health = reg.health()
        open_visits = detector.stats()["visits"]
        self.assertFalse(health["deadlocked"])

        detector.reset_stats()
        reg.acquire(50000, "y")
        reg.acquire(50002, "y")
        mid_visits = detector.stats()["visits"]

        detector.reset_stats()
        reg.drop(50002)
        drop_visits = detector.stats()["visits"]

        for visits in (close_visits, open_visits, mid_visits, drop_visits):
            self.assertLess(visits, self.LIMIT)

    def test_chained_single_wait_added_in_middle_stays_local(self):
        reg = self._chain_registry()
        detector = reg.detector
        detector.reset_stats()
        reg.acquire(150004, "m")
        reg.acquire(150000, "m")          # 沿链方向加一条平行等待，不闭环
        self.assertFalse(reg.health()["deadlocked"])
        self.assertLess(detector.stats()["visits"], self.LIMIT)


if __name__ == "__main__":
    unittest.main()
