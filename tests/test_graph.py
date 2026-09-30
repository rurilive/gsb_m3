"""基线测试：锁住改造前 gtheor.graph.GameKit 的现状行为。

这些断言描述的是当前朴素实现的事实，不是最终应当的样子：

  - outcome 对给定起点递归枚举全部后继，不记忆化，反复重入同一局面；
  - winning_move 按后继顺序逐个试走，返回第一个制胜走法；
  - min_moves 在必胜局面上取走到必败后继的步数，否则在后继里取最小再加一；
  - grundy 取后继格林数集合的最小不出现非负整数；
  - xor_outcome 把多个独立子游戏起点格林数取异或判胜负；
  - all_outcomes 对每个结点逐个判赢输。

改造时本文件一字不得修改，且必须保持全绿。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from gtheor.graph import (  # noqa: E402
    GameKit,
    GameErro,
    GraphErro,
    StateErro,
)


def chain(n):
    """一条长 n 的直链：结点 n 只能走到 n 减一，结点 0 无路可走。"""
    g = {}
    for i in range(n + 1):
        g[i] = (i - 1,) if i > 0 else ()
    return g


class TestOutcomeBaseline(unittest.TestCase):
    def setUp(self):
        self.k = GameKit()

    def test_terminal_is_loss(self):
        self.assertEqual(self.k.outcome({0: ()}, 0), "loss")

    def test_one_move_to_terminal_is_win(self):
        self.assertEqual(self.k.outcome({0: (), 1: (0,)}, 1), "win")

    def test_two_step_chain_is_loss(self):
        self.assertEqual(self.k.outcome(chain(2), 2), "loss")

    def test_three_step_chain_is_win(self):
        self.assertEqual(self.k.outcome(chain(3), 3), "win")

    def test_odd_chain_win_even_chain_loss(self):
        self.assertEqual(self.k.outcome(chain(7), 7), "win")
        self.assertEqual(self.k.outcome(chain(8), 8), "loss")

    def test_two_branches_one_losing_is_win(self):
        g = {0: (), 1: (0,), 2: (0, 1)}
        self.assertEqual(self.k.outcome(g, 2), "win")

    def test_all_successors_winning_is_loss(self):
        g = {0: (), 1: (0,), 2: (1,)}
        self.assertEqual(self.k.outcome(g, 2), "loss")

    def test_expansions_positive(self):
        self.k.outcome(chain(3), 3)
        self.assertGreater(self.k.expansions, 0)

    def test_self_loop_raises(self):
        with self.assertRaises(GraphErro):
            self.k.outcome({0: (0,)}, 0)

    def test_cycle_raises(self):
        with self.assertRaises(GraphErro):
            self.k.outcome({0: (1,), 1: (0,)}, 0)

    def test_missing_successor_raises(self):
        with self.assertRaises(GraphErro):
            self.k.outcome({0: (9,)}, 0)

    def test_non_dict_graph_raises(self):
        with self.assertRaises(GraphErro):
            self.k.outcome([(0, ())], 0)

    def test_unclosed_start_raises(self):
        with self.assertRaises(StateErro):
            self.k.outcome({0: ()}, 5)

    def test_bool_state_raises(self):
        with self.assertRaises(StateErro):
            self.k.outcome({0: ()}, True)

    def test_erro_hierarchy(self):
        self.assertTrue(issubclass(GraphErro, GameErro))
        self.assertTrue(issubclass(StateErro, GameErro))
        self.assertTrue(issubclass(GameErro, Exception))


class TestWinningMoveBaseline(unittest.TestCase):
    def setUp(self):
        self.k = GameKit()

    def test_no_winning_move_on_loss(self):
        self.assertIsNone(self.k.winning_move(chain(2), 2))

    def test_winning_move_points_to_loss(self):
        g = {0: (), 1: (0,), 2: (1, 0)}
        move = self.k.winning_move(g, 2)
        self.assertIsNotNone(move)
        self.assertEqual(self.k.outcome(g, move), "loss")

    def test_picks_first_losing_successor(self):
        g = {0: (), 1: (0,), 2: (1, 0)}
        self.assertEqual(self.k.winning_move(g, 2), 0)

    def test_terminal_state_has_no_move(self):
        self.assertIsNone(self.k.winning_move({0: ()}, 0))

    def test_cycle_raises(self):
        with self.assertRaises(GraphErro):
            self.k.winning_move({0: (1,), 1: (0,)}, 0)


class TestMinMovesBaseline(unittest.TestCase):
    def setUp(self):
        self.k = GameKit()

    def test_loss_has_no_solution(self):
        self.assertIsNone(self.k.min_moves(chain(2), 2))

    def test_one_step_win(self):
        self.assertEqual(self.k.min_moves({0: (), 1: (0,)}, 1), 1)

    def test_three_step_win(self):
        g = {0: (), 1: (0,), 2: (1, 0), 3: (2, 1), 4: (3, 2)}
        self.assertEqual(self.k.outcome(g, 4), "win")
        self.assertEqual(self.k.min_moves(g, 4), 3)

    def test_picks_shortest(self):
        g = {0: (), 1: (0,), 2: (0, 1)}
        self.assertEqual(self.k.min_moves(g, 2), 1)

    def test_loser_delays(self):
        g = {0: (), 1: (0,), 2: (1, 0), 3: (2, 1), 4: (3, 2)}
        self.assertEqual(self.k.min_moves(g, 4), 3)

    def test_odd_ply_count(self):
        g = {0: (), 1: (0,), 2: (1, 0), 3: (2, 1), 4: (3, 2)}
        self.assertEqual(self.k.min_moves(g, 4) % 2, 1)

    def test_terminal_has_no_solution(self):
        self.assertIsNone(self.k.min_moves({0: ()}, 0))

    def test_cycle_raises(self):
        with self.assertRaises(GraphErro):
            self.k.min_moves({0: (1,), 1: (0,)}, 0)


class TestGrundyBaseline(unittest.TestCase):
    def setUp(self):
        self.k = GameKit()

    def test_terminal_is_zero(self):
        self.assertEqual(self.k.grundy({0: ()}, 0), 0)

    def test_single_move_is_one(self):
        self.assertEqual(self.k.grundy({0: (), 1: (0,)}, 1), 1)

    def test_chain_two_is_zero(self):
        self.assertEqual(self.k.grundy(chain(2), 2), 0)

    def test_chain_three_is_one(self):
        self.assertEqual(self.k.grundy(chain(3), 3), 1)

    def test_branch_mex(self):
        g = {0: (), 1: (0,), 2: (0, 1)}
        self.assertEqual(self.k.grundy(g, 2), 2)

    def test_cycle_raises(self):
        with self.assertRaises(GraphErro):
            self.k.grundy({0: (0,)}, 0)


class TestXorBaseline(unittest.TestCase):
    def setUp(self):
        self.k = GameKit()

    def test_empty_games_is_loss(self):
        self.assertEqual(self.k.xor_outcome([]), "loss")

    def test_single_nim_one_is_win(self):
        g = {0: (), 1: (0,)}
        self.assertEqual(self.k.xor_outcome([(g, 1)]), "win")

    def test_two_equal_chains_cancel(self):
        g = chain(2)
        self.assertEqual(self.k.xor_outcome([(g, 2), (g, 2)]), "loss")

    def test_unequal_chains_win(self):
        a = chain(1)
        b = chain(2)
        self.assertEqual(self.k.xor_outcome([(a, 1), (b, 2)]), "win")

    def test_heap_game_matches_grundy_xor(self):
        ga = GameKit().heap_game(3, 3)
        gb = GameKit().heap_game(1, 3)
        va = GameKit().grundy(ga, 3)
        vb = GameKit().grundy(gb, 1)
        expect = "win" if (va ^ vb) != 0 else "loss"
        self.assertEqual(self.k.xor_outcome([(ga, 3), (gb, 1)]), expect)


class TestAllOutcomesBaseline(unittest.TestCase):
    def setUp(self):
        self.k = GameKit()

    def test_chain_outcomes(self):
        result = self.k.all_outcomes(chain(3))
        self.assertEqual(result, {0: "loss", 1: "win", 2: "loss", 3: "win"})

    def test_covers_every_node(self):
        g = {0: (), 1: (0,), 2: (1, 0)}
        result = self.k.all_outcomes(g)
        self.assertEqual(set(result.keys()), set(g.keys()))

    def test_cycle_raises(self):
        with self.assertRaises(GraphErro):
            self.k.all_outcomes({0: (1,), 1: (0,)})


class TestHeapGameBaseline(unittest.TestCase):
    def test_empty_pile(self):
        self.assertEqual(GameKit().heap_game(0, 3), {0: ()})

    def test_small_pile(self):
        self.assertEqual(GameKit().heap_game(2, 3), {0: (), 1: (0,), 2: (1, 0)})

    def test_bad_size_raises(self):
        with self.assertRaises(GraphErro):
            GameKit().heap_game(-1, 3)

    def test_bad_take_raises(self):
        with self.assertRaises(GraphErro):
            GameKit().heap_game(5, 0)


class TestDeterminismBaseline(unittest.TestCase):
    def test_repeated_calls_agree(self):
        g = {0: (), 1: (0,), 2: (1, 0), 3: (2, 1)}
        k1 = GameKit()
        k2 = GameKit()
        self.assertEqual(k1.outcome(g, 3), k2.outcome(g, 3))
        self.assertEqual(k1.min_moves(g, 3), k2.min_moves(g, 3))
        self.assertEqual(k1.grundy(g, 3), k2.grundy(g, 3))
        self.assertEqual(k1.all_outcomes(g), k2.all_outcomes(g))

    def test_expansions_reset_between_calls(self):
        k = GameKit()
        g = chain(3)
        k.outcome(g, 3)
        first = k.expansions
        k.outcome(g, 3)
        self.assertEqual(k.expansions, first)

    def test_fresh_instance_has_zero_expansions(self):
        self.assertEqual(GameKit().expansions, 0)


if __name__ == "__main__":
    unittest.main()
