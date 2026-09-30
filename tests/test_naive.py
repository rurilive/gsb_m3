"""NaiveLines 现状行为的锁定测试（改造前基线，不许改）。

这些用例锁住朴素实现的现状行为：构造校验、插入序号、单点最值、
取到最值的直线标识、半开区间最小值、并列取先的口径，以及全部边界。
测试一个字不改，改造后必须仍然全绿。
"""

import unittest

from lichaotree.lines import Erro, IllegalArgument, Line, NaiveLines


def sample():
    """定义域负二到三，插入五条有代表性直线，返回集合与插入序号。"""
    s = NaiveLines([-2, 3])
    idents = [
        s.add_line(1, 0),    # 0: y = x
        s.add_line(1, 0),    # 1: y = x（与上一条重合）
        s.add_line(0, 2),    # 2: y = 2（水平线）
        s.add_line(-2, 1),   # 3: y = -2x + 1
        s.add_line(3, -5),   # 4: y = 3x - 5
    ]
    return s, idents


class TestBasics(unittest.TestCase):
    def test_domain(self):
        s = NaiveLines([-2, 3])
        self.assertEqual(s.domain(), (-2, 3))

    def test_length(self):
        s, _ = sample()
        self.assertEqual(len(s), 5)

    def test_empty(self):
        s = NaiveLines([0, 10])
        self.assertEqual(len(s), 0)
        self.assertIsNone(s.query_min(3))
        self.assertIsNone(s.query_max(3))
        self.assertIsNone(s.query_argmin(3))
        self.assertIsNone(s.query_argmax(3))
        self.assertIsNone(s.range_min(0, 10))
        self.assertEqual(s.all_values(0), [])

    def test_constructor_rejects_bad_input(self):
        with self.assertRaises(IllegalArgument):
            NaiveLines(3)
        with self.assertRaises(IllegalArgument):
            NaiveLines([1])
        with self.assertRaises(IllegalArgument):
            NaiveLines([0, 1, 2])
        with self.assertRaises(IllegalArgument):
            NaiveLines([3, -2])

    def test_line_object(self):
        line = Line(2, 3, 7)
        self.assertEqual(line.k, 2)
        self.assertEqual(line.b, 3)
        self.assertEqual(line.ident, 7)
        self.assertEqual(line.value_at(4), 2 * 4 + 3)
        self.assertEqual(line.value_at(-4), 2 * (-4) + 3)

    def test_line_rejects_non_int(self):
        with self.assertRaises(IllegalArgument):
            Line(1.5, 0, 0)
        with self.assertRaises(IllegalArgument):
            Line(0, True, 0)

    def test_lines_is_a_copy(self):
        s, _ = sample()
        snapshot = s.lines()
        snapshot.append(Line(9, 9, 99))
        self.assertEqual(len(s), 5)


class TestInsert(unittest.TestCase):
    def test_idents_are_sequential(self):
        s, idents = sample()
        self.assertEqual(idents, [0, 1, 2, 3, 4])

    def test_lines_keep_insertion_order(self):
        s, _ = sample()
        self.assertEqual([ln.ident for ln in s.lines()], [0, 1, 2, 3, 4])


class TestQueryPoint(unittest.TestCase):
    def test_query_min(self):
        s, _ = sample()
        self.assertEqual(s.query_min(2), -3)
        self.assertEqual(s.query_min(-2), -11)
        self.assertEqual(s.query_min(3), -5)

    def test_query_max(self):
        s, _ = sample()
        self.assertEqual(s.query_max(2), 2)
        self.assertEqual(s.query_max(-2), 5)
        self.assertEqual(s.query_max(3), 4)

    def test_all_values(self):
        s, _ = sample()
        self.assertEqual(s.all_values(-2), [-2, -2, 2, 5, -11])
        self.assertEqual(s.all_values(3), [3, 3, 2, -5, 4])

    def test_out_of_domain_raises(self):
        s, _ = sample()
        with self.assertRaises(IllegalArgument):
            s.query_min(9)
        with self.assertRaises(IllegalArgument):
            s.query_max(-3)

    def test_non_int_x_raises(self):
        s, _ = sample()
        with self.assertRaises(IllegalArgument):
            s.query_min(True)
        with self.assertRaises(IllegalArgument):
            s.query_min(None)


class TestLineIdent(unittest.TestCase):
    def test_argmin_and_argmax(self):
        s, _ = sample()
        self.assertEqual(s.query_argmin(2), 3)
        self.assertEqual(s.query_argmax(2), 0)
        self.assertEqual(s.query_argmin(-2), 4)
        self.assertEqual(s.query_argmax(-2), 3)
        self.assertEqual(s.query_argmin(3), 3)
        self.assertEqual(s.query_argmax(3), 4)


class TestRangeMin(unittest.TestCase):
    def test_range_min(self):
        s, _ = sample()
        self.assertEqual(s.range_min(-2, 3), -11)
        self.assertEqual(s.range_min(0, 3), -5)

    def test_empty_range_returns_none(self):
        s, _ = sample()
        self.assertIsNone(s.range_min(0, 0))

    def test_range_out_of_domain_raises(self):
        s, _ = sample()
        with self.assertRaises(IllegalArgument):
            s.range_min(0, 4)
        with self.assertRaises(IllegalArgument):
            s.range_min(3, 1)


class TestTieRule(unittest.TestCase):
    def test_parallel_duplicate_keeps_earlier(self):
        s = NaiveLines([0, 5])
        first = s.add_line(1, 0)
        s.add_line(1, 0)
        # 两条重合直线在横坐标二处取值都为零，取序号较小者。
        self.assertEqual(s.query_min(2), 2)
        self.assertEqual(s.query_argmin(2), first)
        self.assertEqual(s.query_argmax(2), first)

    def test_parallel_levels_keep_earlier(self):
        s = NaiveLines([0, 5])
        first = s.add_line(0, 7)
        s.add_line(0, 7)
        self.assertEqual(s.query_min(2), 7)
        self.assertEqual(s.query_argmin(2), first)

    def test_crossing_at_single_point(self):
        s = NaiveLines([0, 5])
        up = s.add_line(1, 3)      # y = x + 3
        s.add_line(-1, 5)          # y = -x + 5，与上一条恰在横坐标一相交
        self.assertEqual(s.query_min(1), 4)
        self.assertEqual(s.query_max(1), 4)
        self.assertEqual(s.query_argmin(1), up)
        self.assertEqual(s.query_argmax(1), up)


class TestErrorBase(unittest.TestCase):
    def test_all_errors_share_base(self):
        self.assertTrue(issubclass(IllegalArgument, Erro))

    def test_catch_by_base(self):
        s = NaiveLines([0, 5])
        with self.assertRaises(Erro):
            s.query_min(9)


if __name__ == "__main__":
    unittest.main()
