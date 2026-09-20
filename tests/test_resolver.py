"""depsolve 回归测试：覆盖四个已修复缺陷及既有解析语义。"""

import os
import subprocess
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from depsolve import (
    CircularDependencyError,
    ConflictError,
    UnknownPackageError,
    resolve,
)

MANIFEST = {
    "unicode":     {"versions": ["1.0.0"]},
    "fmt":         {"versions": ["1.1.0", "1.2.0"], "depends": ["unicode>=0.9"]},
    "json":        {"versions": ["1.1.0", "2.0.1", "2.1.0"], "depends": ["unicode>=0.5"]},
    "cli":         {"versions": ["1.0.0"], "depends": ["fmt>=1.0", "json>=2.0"]},
    "gateway":     {"versions": ["1.0.0"], "depends": ["json>=2.0", "oldcache"]},
    "oldcache":    {"versions": ["0.9.0"], "depends": ["json<2.0"]},
    "report":      {"versions": ["2.0.0"], "depends": ["cli>=1.0", "fmt>=1.1"]},
    "archive":     {"versions": ["1.0.0"], "depends": ["json>=2.0"],
                    "optional_depends": ["archive-sse"]},
    "archive-sse": {"versions": ["0.2.0"], "depends": ["archive>=1.0"]},
}


def names(order):
    return [item.split("@")[0] for item in order]


class TestCircularDependency(unittest.TestCase):
    """现象 1：包把自己写进依赖列表必须报循环依赖。"""

    def test_self_dependency_raises(self):
        manifest = {"a": {"versions": ["1.0.0"], "depends": ["a"]}}
        with self.assertRaises(CircularDependencyError) as ctx:
            resolve(manifest, ["a"])
        self.assertIn("a", str(ctx.exception))

    def test_self_dependency_with_constraint_raises(self):
        manifest = {"a": {"versions": ["1.0.0"], "depends": ["a>=1.0"]}}
        with self.assertRaises(CircularDependencyError):
            resolve(manifest, ["a"])

    def test_indirect_cycle_raises(self):
        manifest = {
            "a": {"versions": ["1.0.0"], "depends": ["b"]},
            "b": {"versions": ["1.0.0"], "depends": ["c"]},
            "c": {"versions": ["1.0.0"], "depends": ["a"]},
        }
        with self.assertRaises(CircularDependencyError):
            resolve(manifest, ["a"])


class TestDeterminism(unittest.TestCase):
    """现象 2：同一输入两次解析输出必须逐项一致。"""

    def test_repeated_resolve_identical(self):
        first = resolve(MANIFEST, ["report", "cli", "archive"])
        for _ in range(5):
            self.assertEqual(first, resolve(MANIFEST, ["report", "cli", "archive"]))

    def test_stable_across_hash_seeds(self):
        # set 迭代顺序受 PYTHONHASHSEED 影响，用子进程模拟多次 CI 运行
        code = (
            "import sys; sys.path.insert(0, '.');"
            "from tests.test_resolver import MANIFEST;"
            "from depsolve import resolve;"
            "print('|'.join(resolve(MANIFEST, ['report', 'cli', 'archive'])))"
        )
        outputs = set()
        for seed in ("0", "1", "42"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            out = subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, check=True, env=env,
                cwd=os.path.join(os.path.dirname(__file__), ".."),
            )
            outputs.add(out.stdout.strip())
        self.assertEqual(len(outputs), 1)

    def test_duplicate_requests_ignored(self):
        self.assertEqual(
            resolve(MANIFEST, ["cli", "cli"]),
            resolve(MANIFEST, ["cli"]),
        )


class TestOptionalDepends(unittest.TestCase):
    """现象 3：未启用的可选依赖组完全不参与解析。"""

    def test_optional_group_excluded_by_default(self):
        order = resolve(MANIFEST, ["archive"])
        self.assertNotIn("archive-sse", names(order))
        self.assertEqual(names(order), ["unicode", "json", "archive"])

    def test_optional_group_enabled(self):
        manifest = {
            "app":   {"versions": ["1.0.0"], "optional_depends": ["accel"]},
            "accel": {"versions": ["0.3.0"]},
        }
        order = resolve(manifest, ["app"], enabled={"accel"})
        self.assertEqual(names(order), ["accel", "app"])

    def test_optional_cycle_only_when_enabled(self):
        # archive-sse 反向依赖 archive，启用后构成环，应报循环依赖
        with self.assertRaises(CircularDependencyError):
            resolve(MANIFEST, ["archive"], enabled={"archive-sse"})


class TestVersionConflict(unittest.TestCase):
    """现象 4：版本约束互相打架必须报 ConflictError。"""

    def test_conflicting_constraints_raise(self):
        with self.assertRaises(ConflictError) as ctx:
            resolve(MANIFEST, ["gateway"])
        self.assertIn("json", str(ctx.exception))

    def test_intersection_selects_highest_satisfying(self):
        manifest = {
            "lib": {"versions": ["1.0.0", "1.5.0", "2.0.0", "2.1.0"]},
            "a":   {"versions": ["1.0.0"], "depends": ["lib>=1.2"]},
            "b":   {"versions": ["1.0.0"], "depends": ["lib<2.0"]},
        }
        order = resolve(manifest, ["a", "b"])
        self.assertIn("lib@1.5.0", order)

    def test_no_constraints_picks_highest(self):
        order = resolve(MANIFEST, ["json"])
        self.assertIn("json@2.1.0", order)


class TestExistingSemantics(unittest.TestCase):
    """既有语义：拓扑序、未知包、确定性输出。"""

    def test_topological_order(self):
        order = names(resolve(MANIFEST, ["report"]))
        self.assertLess(order.index("unicode"), order.index("fmt"))
        self.assertLess(order.index("fmt"), order.index("cli"))
        self.assertLess(order.index("cli"), order.index("report"))

    def test_unknown_package_raises(self):
        with self.assertRaises(UnknownPackageError):
            resolve(MANIFEST, ["nosuchpkg"])

    def test_unknown_dependency_raises(self):
        manifest = {"a": {"versions": ["1.0.0"], "depends": ["ghost"]}}
        with self.assertRaises(UnknownPackageError):
            resolve(manifest, ["a"])

    def test_demo_cases(self):
        self.assertEqual(
            resolve(MANIFEST, ["cli"]),
            ["unicode@1.0.0", "fmt@1.2.0", "json@2.1.0", "cli@1.0.0"],
        )


if __name__ == "__main__":
    unittest.main()
