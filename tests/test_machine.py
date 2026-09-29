"""Machine 现有行为的锁定测试：注册、推进、路径与非法转移。

只覆盖当前已支持的能力，后面新增的守卫与动作、子状态机、历史态与冲突
检测另开测试文件。
"""

import unittest

from flowkit import DefinitionError, InvalidTransition, Machine
from flowkit.machine import Machine as MachineFromModule


def build():
    """一个最小可用的三层流水线：草稿到评审到发布。"""
    return Machine(
        initial="draft",
        states=["draft", "review", "published"],
        transitions=[("draft", "review"), ("review", "published")],
    )


class TestConstruction(unittest.TestCase):
    def test_initial_is_current(self):
        m = build()
        self.assertEqual(m.current, "draft")
        self.assertEqual(m.initial, "draft")

    def test_states_sorted(self):
        m = build()
        self.assertEqual(m.states, ("draft", "published", "review"))

    def test_unknown_initial_is_rejected(self):
        with self.assertRaises(DefinitionError):
            Machine(initial="ghost", states=["draft"])

    def test_duplicate_state_is_rejected(self):
        m = Machine(initial="a", states=["a"])
        with self.assertRaises(DefinitionError):
            m.add_state("a")

    def test_empty_state_name_is_rejected(self):
        m = Machine(initial="a", states=["a"])
        with self.assertRaises(DefinitionError):
            m.add_state("")

    def test_non_string_state_is_rejected(self):
        m = Machine(initial="a", states=["a"])
        with self.assertRaises(DefinitionError):
            m.add_state(7)

    def test_transition_to_unknown_state_is_rejected(self):
        m = Machine(initial="a", states=["a"])
        with self.assertRaises(DefinitionError):
            m.add_transition("a", "zzz")

    def test_transition_from_unknown_state_is_rejected(self):
        m = Machine(initial="a", states=["a"])
        with self.assertRaises(DefinitionError):
            m.add_transition("zzz", "a")

    def test_add_state_returns_self(self):
        m = Machine(initial="a", states=["a"])
        self.assertIs(m.add_state("b"), m)
        self.assertIs(m.add_transition("a", "b"), m)

    def test_exported_from_package_and_module(self):
        self.assertIs(Machine, MachineFromModule)


class TestStepping(unittest.TestCase):
    def test_step_moves_current(self):
        m = build()
        self.assertEqual(m.step("review"), "review")
        self.assertEqual(m.current, "review")

    def test_full_path(self):
        m = build()
        m.step("review")
        m.step("published")
        self.assertEqual(m.current, "published")

    def test_trail_records_path(self):
        m = build()
        m.step("review")
        m.step("published")
        self.assertEqual(m.trail, ["draft", "review", "published"])

    def test_initial_trail_has_initial_state(self):
        self.assertEqual(build().trail, ["draft"])

    def test_trail_is_a_copy(self):
        m = build()
        m.trail.append("hacked")
        self.assertEqual(m.trail, ["draft"])

    def test_reset_returns_to_initial(self):
        m = build()
        m.step("review")
        self.assertEqual(m.reset(), "draft")
        self.assertEqual(m.trail, ["draft"])


class TestQueries(unittest.TestCase):
    def test_can_reports_available_target(self):
        m = build()
        self.assertTrue(m.can("review"))
        self.assertFalse(m.can("published"))

    def test_can_ignores_registered_but_unreachable_target(self):
        m = build()
        self.assertFalse(m.can("draft"))

    def test_can_rejects_unknown_target(self):
        m = build()
        with self.assertRaises(DefinitionError):
            m.can("ghost")

    def test_targets_defaults_to_current(self):
        m = build()
        self.assertEqual(m.targets(), ("review",))

    def test_targets_of_named_source(self):
        m = build()
        self.assertEqual(m.targets("review"), ("published",))
        self.assertEqual(m.targets("published"), ())

    def test_targets_rejects_unknown_source(self):
        m = build()
        with self.assertRaises(DefinitionError):
            m.targets("ghost")

    def test_repr(self):
        self.assertIn("draft", repr(build()))


class TestIllegalTransition(unittest.TestCase):
    def test_illegal_target_is_rejected(self):
        m = build()
        with self.assertRaises(InvalidTransition):
            m.step("published")

    def test_unknown_target_is_rejected(self):
        m = build()
        with self.assertRaises(InvalidTransition):
            m.step("ghost")

    def test_failed_step_leaves_state_untouched(self):
        m = build()
        with self.assertRaises(InvalidTransition):
            m.step("published")
        self.assertEqual(m.current, "draft")
        self.assertEqual(m.trail, ["draft"])


if __name__ == "__main__":
    unittest.main()