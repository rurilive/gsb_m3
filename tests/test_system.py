"""DifferenceSystem 现有行为的锁定测试。

覆盖登记校验、朴素求解、最大值查询与赋值校验的当前行为。
"""

import unittest

from diffcons.system import (
    Constraint,
    ConstraintError,
    DifferenceSystem,
    Infeasible,
)


def satisfied(system, value):
    """赋值是否满足全部约束。"""
    return system.check_assignment(value) is None


class TestRegistration(unittest.TestCase):
    def test_add_le_returns_constraint(self):
        s = DifferenceSystem()
        c = s.add_le("a", "b", 3)
        self.assertIsInstance(c, Constraint)
        self.assertEqual((c.lhs, c.rhs, c.op, c.bound), ("a", "b", "le", 3))

    def test_variables_sorted(self):
        s = DifferenceSystem()
        s.add_le("b", "a", 1)
        s.add_le("c", "a", 1)
        self.assertEqual(s.variables(), ["a", "b", "c"])

    def test_constraints_keep_order(self):
        s = DifferenceSystem()
        c1 = s.add_le("a", "b", 1)
        c2 = s.add_eq("b", "c", 2)
        self.assertEqual(s.constraints(), [c1, c2])
        self.assertEqual(len(s), 2)

    def test_invalid_name_raises(self):
        s = DifferenceSystem()
        with self.assertRaises(ConstraintError):
            s.add_le("", "b", 1)
        with self.assertRaises(ConstraintError):
            s.add_le("a", None, 1)
        with self.assertRaises(ConstraintError):
            s.add_eq("a", 5, 1)

    def test_invalid_bound_raises(self):
        s = DifferenceSystem()
        with self.assertRaises(ConstraintError):
            s.add_le("a", "b", "x")
        with self.assertRaises(ConstraintError):
            s.add_le("a", "b", True)


class TestSolve(unittest.TestCase):
    def test_empty_system(self):
        self.assertEqual(DifferenceSystem().solve(), {})

    def test_single_constraint(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 4)
        value = s.solve()
        self.assertTrue(satisfied(s, value))
        self.assertEqual(sorted(value), ["a", "b"])

    def test_chain_tightens(self):
        s = DifferenceSystem()
        s.add_le("b", "a", 1)
        s.add_le("c", "b", 1)
        s.add_le("c", "a", 5)
        value = s.solve()
        self.assertTrue(satisfied(s, value))
        self.assertLessEqual(value["c"] - value["a"], 2)

    def test_same_variable_zero(self):
        s = DifferenceSystem()
        s.add_le("a", "a", 0)
        value = s.solve()
        self.assertEqual(value["a"], 0)

    def test_equality_forces_difference(self):
        s = DifferenceSystem()
        s.add_eq("a", "b", 3)
        value = s.solve()
        self.assertEqual(value["a"] - value["b"], 3)

    def test_negative_cycle_infeasible(self):
        s = DifferenceSystem()
        s.add_le("a", "b", -1)
        s.add_le("b", "a", -1)
        with self.assertRaises(Infeasible):
            s.solve()
        self.assertFalse(s.has_solution())

    def test_same_variable_negative_infeasible(self):
        s = DifferenceSystem()
        s.add_le("a", "a", -1)
        with self.assertRaises(Infeasible):
            s.solve()

    def test_feasible_has_solution(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 2)
        self.assertTrue(s.has_solution())

    def test_boundary_equality_allowed(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 0)
        s.add_le("b", "a", 0)
        value = s.solve()
        self.assertEqual(value["a"], value["b"])

    def test_repeat_is_deterministic(self):
        s = DifferenceSystem()
        s.add_le("b", "a", 1)
        s.add_le("c", "b", 1)
        self.assertEqual(s.solve(), s.solve())


class TestDiffMax(unittest.TestCase):
    def test_direct_upper_bound(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 5)
        self.assertEqual(s.diff_max("a", "b"), 5)

    def test_upper_bound_gives_negative(self):
        s = DifferenceSystem()
        s.add_le("a", "b", -3)
        self.assertEqual(s.diff_max("a", "b"), -3)

    def test_unbounded_returns_none(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 5)
        self.assertIsNone(s.diff_max("b", "a"))

    def test_unknown_variable_returns_none(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 5)
        self.assertIsNone(s.diff_max("a", "z"))

    def test_diff_max_value_is_satisfiable(self):
        s = DifferenceSystem()
        s.add_le("b", "a", 1)
        s.add_le("c", "b", 2)
        s.add_le("c", "a", 5)
        got = s.diff_max("c", "a")
        self.assertLessEqual(got, 3)


class TestCheckAssignment(unittest.TestCase):
    def test_all_satisfied_returns_none(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 2)
        self.assertIsNone(s.check_assignment({"a": 1, "b": 0}))

    def test_returns_first_violation(self):
        s = DifferenceSystem()
        c1 = s.add_le("a", "b", 1)
        s.add_le("b", "c", 1)
        bad = s.check_assignment({"a": 5, "b": 0, "c": 0})
        self.assertEqual(bad, c1)

    def test_eq_violation_detected(self):
        s = DifferenceSystem()
        c = s.add_eq("a", "b", 2)
        self.assertEqual(s.check_assignment({"a": 0, "b": 0}), c)

    def test_missing_variable_raises(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 2)
        with self.assertRaises(ConstraintError):
            s.check_assignment({"a": 1})

    def test_non_dict_raises(self):
        s = DifferenceSystem()
        s.add_le("a", "b", 2)
        with self.assertRaises(ConstraintError):
            s.check_assignment([1, 2])


if __name__ == "__main__":
    unittest.main()
