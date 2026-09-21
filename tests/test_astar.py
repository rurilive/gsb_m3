"""AStarPlanner 的行为基线：启发式规则、最优性对拍、增量修复与统计。"""

import math
import os
import random
import subprocess
import sys
import time
import unittest

from gridnav import (AStarPlanner, Grid, GridError, dijkstra_path, open_map,
                     random_map, validate_path)
from gridnav.astar import HEURISTIC_SCALE, heuristic

SQRT2 = math.sqrt(2.0)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def step_counts(path):
    """路径的 (斜步数, 直步数)。"""
    diagonals = 0
    straights = 0
    for (ax, ay), (bx, by) in zip(path, path[1:]):
        if ax != bx and ay != by:
            diagonals += 1
        else:
            straights += 1
    return diagonals, straights


def canonical_cost(path):
    """代价的规范形 d*SQRT2 + s，与累加顺序无关，可严格比较。

    sqrt(2) 是无理数，两条路径真实代价相等当且仅当 (斜步数, 直步数)
    完全相同，所以规范形相等就是代价严格相等。
    """
    diagonals, straights = step_counts(path)
    return diagonals * SQRT2 + straights * 1.0


class HeuristicRulesTest(unittest.TestCase):
    """启发式的公式、下压系数与浮点规则在这里锁死。"""

    def test_scale_is_locked(self):
        self.assertEqual(HEURISTIC_SCALE, 1.0 - 1e-12)

    def test_zero_at_goal(self):
        self.assertEqual(heuristic(2, 3, 2, 3), 0.0)

    def test_straight_distance(self):
        self.assertEqual(heuristic(0, 0, 4, 0),
                         (4 + (SQRT2 - 1.0) * 0) * HEURISTIC_SCALE)

    def test_pure_diagonal(self):
        self.assertEqual(heuristic(0, 0, 3, 3),
                         (3 + (SQRT2 - 1.0) * 3) * HEURISTIC_SCALE)

    def test_mixed_distance(self):
        # dx=3, dy=2：2 步斜行 + 1 步直行。
        self.assertEqual(heuristic(2, 1, 5, 3),
                        (3 + (SQRT2 - 1.0) * 2) * HEURISTIC_SCALE)

    def test_symmetric_and_translation_invariant(self):
        self.assertEqual(heuristic(1, 2, 7, 5), heuristic(7, 5, 1, 2))
        self.assertEqual(heuristic(1, 2, 7, 5), heuristic(4, 5, 10, 8))

    def test_never_overestimates_even_in_float(self):
        # 下压后的启发式必须不超过规范形真实代价，含大坐标。
        for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1), (5, 3), (3, 5),
                       (1000, 700), (999, 1000), (123456, 65432)):
            h = heuristic(0, 0, dx, dy)
            diagonals = min(dx, dy)
            straights = max(dx, dy) - diagonals
            true_cost = diagonals * SQRT2 + straights * 1.0
            self.assertLessEqual(h, true_cost)
            if dx or dy:
                self.assertLess(h, true_cost)

    def test_admissible_against_dijkstra_on_random_map(self):
        grid = random_map(20, 15, density=0.25, seed=11,
                          protected=[(19, 14)])
        goal = (19, 14)
        for y in range(grid.height):
            for x in range(grid.width):
                if not grid.passable(x, y):
                    continue
                ref = dijkstra_path(grid, (x, y), goal)
                if ref is None:
                    continue
                self.assertLessEqual(heuristic(x, y, goal[0], goal[1]),
                                     canonical_cost(ref))


class PlanTest(unittest.TestCase):

    def test_open_map_diagonal(self):
        planner = AStarPlanner(open_map(4, 4))
        self.assertEqual(planner.plan((0, 0), (3, 3)),
                         [(0, 0), (1, 1), (2, 2), (3, 3)])

    def test_start_equals_goal(self):
        planner = AStarPlanner(Grid(3, 3))
        self.assertEqual(planner.plan((1, 2), (1, 2)), [(1, 2)])

    def test_around_wall_matches_reference_cost(self):
        grid = Grid(5, 5, [(2, y) for y in range(4)])
        path = AStarPlanner(grid).plan((0, 0), (4, 0))
        self.assertEqual(step_counts(path), (4, 4))
        self.assertEqual(canonical_cost(path), 4 * SQRT2 + 4.0)

    def test_unreachable_returns_none(self):
        grid = Grid(5, 5, [(3, 3), (3, 4), (4, 3)])
        self.assertIsNone(AStarPlanner(grid).plan((0, 0), (4, 4)))

    def test_blocked_endpoint_raises(self):
        grid = Grid(3, 3, [(0, 0)])
        planner = AStarPlanner(grid)
        with self.assertRaises(GridError):
            planner.plan((0, 0), (2, 2))
        with self.assertRaises(GridError):
            planner.plan((2, 2), (0, 0))

    def test_out_of_bounds_endpoint_raises(self):
        planner = AStarPlanner(Grid(3, 3))
        with self.assertRaises(GridError):
            planner.plan((-1, 0), (2, 2))
        with self.assertRaises(GridError):
            planner.plan((0, 0), (0, 3))

    def test_matches_dijkstra_on_random_maps(self):
        cases = [
            (10, 8, 0.20, 3), (14, 10, 0.28, 23), (20, 15, 0.25, 11),
            (31, 17, 0.30, 5), (24, 24, 0.15, 42),
        ]
        for width, height, density, seed in cases:
            grid = random_map(width, height, density=density, seed=seed)
            free = [(x, y) for y in range(height) for x in range(width)
                    if grid.passable(x, y)]
            rng = random.Random(seed)
            planner = AStarPlanner(grid)
            for _ in range(6):
                start = rng.choice(free)
                goal = rng.choice(free)
                ref = dijkstra_path(grid, start, goal)
                got = planner.plan(start, goal)
                if ref is None:
                    self.assertIsNone(got)
                    continue
                self.assertIsNotNone(got)
                validate_path(grid, got)
                self.assertEqual(got[0], start)
                self.assertEqual(got[-1], goal)
                # 代价严格相等：步型计数相同，规范形浮点也相同。
                self.assertEqual(step_counts(got), step_counts(ref))
                self.assertEqual(canonical_cost(got), canonical_cost(ref))

    def test_tie_choice_is_reproducible(self):
        grid = random_map(14, 10, density=0.28, seed=23,
                          protected=[(0, 0), (13, 9)])
        first = AStarPlanner(grid).plan((0, 0), (13, 9))
        self.assertIsNotNone(first)
        self.assertEqual(first, AStarPlanner(grid).plan((0, 0), (13, 9)))
        planner = AStarPlanner(grid)
        self.assertEqual(planner.plan((0, 0), (13, 9)),
                         planner.plan((0, 0), (13, 9)))

    def test_cross_process_consistent(self):
        snippet = (
            "from gridnav import AStarPlanner, random_map\n"
            "g = random_map(14, 10, density=0.28, seed=23,"
            " protected=[(0, 0), (13, 9)])\n"
            "print(AStarPlanner(g).plan((0, 0), (13, 9)))\n"
        )
        outputs = []
        for hash_seed in ("0", "1"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = hash_seed
            env["PYTHONPATH"] = (REPO_ROOT + os.pathsep
                                 + env.get("PYTHONPATH", ""))
            proc = subprocess.run([sys.executable, "-c", snippet],
                                  capture_output=True, text=True, env=env,
                                  check=True)
            outputs.append(proc.stdout)
        self.assertEqual(outputs[0], outputs[1])
        self.assertIn("(13, 9)", outputs[0])


class ReplanTest(unittest.TestCase):

    def setUp(self):
        self.grid = open_map(12, 12)
        self.planner = AStarPlanner(self.grid)
        self.first = self.planner.plan((0, 0), (11, 11))

    def test_no_change_reuses_without_expansions(self):
        before = self.planner.stats()["expansions"]
        again = self.planner.replan((0, 0), (11, 11))
        self.assertEqual(again, self.first)
        stats = self.planner.stats()
        self.assertEqual(stats["expansions"], before)
        self.assertEqual(stats["reuses"], 1)
        self.assertEqual(stats["repairs"], 0)

    def test_off_path_block_reuses_without_expansions(self):
        self.grid.set_blocked(5, 3)  # 不在主对角线路径上
        before = self.planner.stats()["expansions"]
        path = self.planner.replan((0, 0), (11, 11))
        self.assertEqual(path, self.first)
        stats = self.planner.stats()
        self.assertEqual(stats["expansions"], before)
        self.assertEqual(stats["reuses"], 1)

    def test_on_path_block_repairs_only_affected_segment(self):
        self.grid.set_blocked(9, 9)  # 集装箱压断主对角线
        before = self.planner.stats()["expansions"]
        repaired = self.planner.replan((0, 0), (11, 11))
        stats = self.planner.stats()
        self.assertEqual(stats["repairs"], 1)
        # 断点前缀原样保留，只重算了受影响的一段。
        self.assertEqual(repaired[:9], self.first[:9])
        validate_path(self.grid, repaired)
        self.assertEqual(repaired[0], (0, 0))
        self.assertEqual(repaired[-1], (11, 11))
        # 增量展开数大于零但明显少于同图全搜。
        delta = stats["expansions"] - before
        fresh = AStarPlanner(self.grid)
        fresh.plan((0, 0), (11, 11))
        self.assertGreater(delta, 0)
        self.assertLess(delta, fresh.stats()["expansions"])
        # 修完仍是该图上的最短路（与参考实现严格同代价）。
        ref = dijkstra_path(self.grid, (0, 0), (11, 11))
        self.assertEqual(step_counts(repaired), step_counts(ref))
        self.assertEqual(canonical_cost(repaired), canonical_cost(ref))

    def test_repair_to_unreachable_returns_none(self):
        for cell in ((10, 10), (10, 11), (11, 10)):
            self.grid.set_blocked(*cell)
        self.assertIsNone(self.planner.replan((0, 0), (11, 11)))
        self.assertEqual(self.planner.stats()["repairs"], 1)

    def test_blocked_goal_raises_on_replan(self):
        self.grid.set_blocked(11, 11)
        with self.assertRaises(GridError):
            self.planner.replan((0, 0), (11, 11))

    def test_blocked_start_raises_on_replan(self):
        self.grid.set_blocked(0, 0)
        with self.assertRaises(GridError):
            self.planner.replan((0, 0), (11, 11))

    def test_new_query_falls_back_to_full_search(self):
        path = self.planner.replan((0, 0), (5, 5))
        self.assertEqual(path[0], (0, 0))
        self.assertEqual(path[-1], (5, 5))
        self.assertEqual(self.planner.stats()["full_searches"], 2)

    def test_unreachable_stays_none_without_expansions(self):
        grid = Grid(5, 5, [(3, 3), (3, 4), (4, 3)])
        planner = AStarPlanner(grid)
        self.assertIsNone(planner.plan((0, 0), (4, 4)))
        before = planner.stats()["expansions"]
        grid.set_blocked(1, 1)  # 只加堵，不可达结论不可能变
        self.assertIsNone(planner.replan((0, 0), (4, 4)))
        self.assertEqual(planner.stats()["expansions"], before)
        self.assertEqual(planner.stats()["reuses"], 1)

    def test_unblock_falls_back_to_full_search(self):
        grid = Grid(5, 5, [(3, 3), (3, 4), (4, 3)])
        planner = AStarPlanner(grid)
        self.assertIsNone(planner.plan((0, 0), (4, 4)))
        grid.set_blocked(4, 3, False)  # 解除阻塞可能开出新路
        path = planner.replan((0, 0), (4, 4))
        self.assertIsNotNone(path)
        validate_path(grid, path)
        self.assertEqual(planner.stats()["full_searches"], 2)


class StatsTest(unittest.TestCase):

    def test_expansions_accumulate_across_queries(self):
        grid = random_map(10, 8, density=0.2, seed=3,
                          protected=[(0, 0), (9, 7), (9, 0)])
        planner = AStarPlanner(grid)
        planner.plan((0, 0), (9, 7))
        first = planner.stats()
        self.assertEqual(first["full_searches"], 1)
        self.assertGreater(first["expansions"], 0)
        planner.plan((0, 0), (9, 0))
        second = planner.stats()
        self.assertEqual(second["full_searches"], 2)
        self.assertGreater(second["expansions"], first["expansions"])

    def test_stats_returns_independent_snapshot(self):
        planner = AStarPlanner(Grid(3, 3))
        planner.plan((0, 0), (2, 2))
        snapshot = planner.stats()
        snapshot["expansions"] = -1
        self.assertGreater(planner.stats()["expansions"], 0)


class PerformanceTest(unittest.TestCase):

    def test_large_map_many_queries(self):
        # 二十万格、上百次查询：秒级完成，开放列表为堆。
        grid = random_map(450, 450, density=0.22, seed=99)
        free = [(x, y) for y in range(450) for x in range(450)
                if grid.passable(x, y)]
        rng = random.Random(7)
        queries = [(rng.choice(free), rng.choice(free)) for _ in range(100)]
        planner = AStarPlanner(grid)
        started = time.perf_counter()
        for start, goal in queries:
            planner.plan(start, goal)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 15.0)


if __name__ == "__main__":
    unittest.main()
