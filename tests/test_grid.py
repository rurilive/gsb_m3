"""bit2d 现有行为的锁定测试（基线，一字不改且必须全绿）。"""

import unittest

from bit2d.grid import NaiveGrid


def build():
    return NaiveGrid(2, 3, [1, 2, 3, 4, 5, 6])


class TestNaiveGrid(unittest.TestCase):
    def test_shape(self):
        g = build()
        self.assertEqual(g.shape(), (2, 3))

    def test_value_at(self):
        g = build()
        self.assertEqual(g.value_at(0, 0), 1)
        self.assertEqual(g.value_at(1, 2), 6)

    def test_to_matrix_is_copy(self):
        g = build()
        m = g.to_matrix()
        self.assertEqual(m, [[1, 2, 3], [4, 5, 6]])
        m[0][0] = 99
        self.assertEqual(g.value_at(0, 0), 1)

    def test_empty_grid_default(self):
        g = NaiveGrid(0, 0)
        self.assertEqual(g.shape(), (0, 0))
        self.assertEqual(g.query(0, 0, 0, 0), 0)

    def test_single_cell(self):
        g = NaiveGrid(1, 1, [7])
        self.assertEqual(g.query(0, 0, 1, 1), 7)
        self.assertEqual(g.query(0, 0, 0, 0), 0)

    def test_single_row(self):
        g = NaiveGrid(1, 4, [1, 2, 3, 4])
        self.assertEqual(g.query(0, 1, 1, 3), 5)

    def test_single_col(self):
        g = NaiveGrid(4, 1, [1, 2, 3, 4])
        self.assertEqual(g.query(1, 0, 3, 1), 5)

    def test_query_full_grid(self):
        g = build()
        self.assertEqual(g.query(0, 0, 2, 3), 21)

    def test_query_submatrix(self):
        g = build()
        self.assertEqual(g.query(0, 0, 2, 2), 12)
        self.assertEqual(g.query(0, 1, 1, 3), 5)
        self.assertEqual(g.query(1, 1, 2, 3), 11)

    def test_query_empty_rectangle(self):
        g = build()
        self.assertEqual(g.query(1, 1, 1, 1), 0)
        self.assertEqual(g.query(1, 1, 1, 0), 0)

    def test_query_cost_is_area(self):
        g = NaiveGrid(3, 4, list(range(12)))
        g.query(0, 0, 3, 4)
        self.assertEqual(g.last_cost(), 12)
        g.query(0, 0, 2, 2)
        self.assertEqual(g.last_cost(), 4)
        g.query(1, 1, 1, 1)
        self.assertEqual(g.last_cost(), 0)

    def test_query_bad_rectangle_negative(self):
        g = build()
        with self.assertRaises(IndexError):
            g.query(-1, 0, 2, 3)

    def test_query_bad_rectangle_past_end(self):
        g = build()
        with self.assertRaises(IndexError):
            g.query(0, 0, 3, 3)
        with self.assertRaises(IndexError):
            g.query(0, 0, 2, 4)

    def test_query_bad_rectangle_type(self):
        g = build()
        with self.assertRaises(ValueError):
            g.query(0, 0, 2, "x")

    def test_update_returns_new(self):
        g = build()
        self.assertEqual(g.update(1, 2, 10), 16)
        self.assertEqual(g.value_at(1, 2), 16)
        self.assertEqual(g.query(0, 0, 2, 3), 31)

    def test_update_negative_delta(self):
        g = build()
        self.assertEqual(g.update(0, 0, -1), 0)
        self.assertEqual(g.query(0, 0, 1, 1), 0)

    def test_update_rejects_non_int(self):
        g = build()
        with self.assertRaises(ValueError):
            g.update(0, 0, "x")
        with self.assertRaises(ValueError):
            g.update(0, 0, False)

    def test_update_out_of_range(self):
        g = build()
        with self.assertRaises(IndexError):
            g.update(2, 0, 1)
        with self.assertRaises(IndexError):
            g.update(0, 3, 1)

    def test_negative_values_allowed(self):
        g = NaiveGrid(2, 2, [-1, -2, 3, 4])
        self.assertEqual(g.query(0, 0, 2, 2), 4)
        self.assertEqual(g.query(0, 0, 1, 2), -3)

    def test_dense_prefix_values(self):
        g = build()
        table = g.dense_prefix()
        self.assertEqual(table[0], [0, 0, 0, 0])
        self.assertEqual(table[1], [0, 1, 3, 6])
        self.assertEqual(table[2], [0, 5, 12, 21])

    def test_dense_prefix_matches_query(self):
        g = build()
        table = g.dense_prefix()
        for r in range(2):
            for c in range(3):
                brute = g.query(0, 0, r + 1, c + 1)
                self.assertEqual(table[r + 1][c + 1], brute)

    def test_rebuild_snapshot_counts(self):
        g = build()
        self.assertEqual(g.rebuild_count(), 0)
        g.update(0, 0, 1)
        snap = g.rebuild_snapshot()
        self.assertEqual(g.rebuild_count(), 1)
        self.assertEqual(snap[1][1], 2)

    def test_values_length_must_match(self):
        with self.assertRaises(ValueError):
            NaiveGrid(2, 3, [1, 2, 3])

    def test_values_must_be_int(self):
        with self.assertRaises(ValueError):
            NaiveGrid(1, 2, [1, "x"])
        with self.assertRaises(ValueError):
            NaiveGrid(1, 2, [1, True])

    def test_bad_dimensions(self):
        with self.assertRaises(ValueError):
            NaiveGrid(-1, 2)
        with self.assertRaises(ValueError):
            NaiveGrid(1, 2.0)


if __name__ == "__main__":
    unittest.main()
