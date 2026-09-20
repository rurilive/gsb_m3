"""depsolve 回归测试：自依赖、确定性、可选组、版本冲突等。"""

import os
import subprocess
import sys
import unittest

from depsolve import (
    CircularDependencyError,
    ConflictError,
    Resolver,
    UnknownPackageError,
    resolve,
)

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_manifest():
    return {
        "unicode":     {"versions": ["1.0.0"]},
        "fmt":         {"versions": ["1.1.0", "1.2.0"],
                        "depends": ["unicode>=0.9"]},
        "json":        {"versions": ["1.1.0", "2.0.1", "2.1.0"],
                        "depends": ["unicode>=0.5"]},
        "cli":         {"versions": ["1.0.0"],
                        "depends": ["fmt>=1.0", "json>=2.0"]},
        "gateway":     {"versions": ["1.0.0"],
                        "depends": ["json>=2.0", "oldcache"]},
        "oldcache":    {"versions": ["0.9.0"], "depends": ["json<2.0"]},
        "report":      {"versions": ["2.0.0"],
                        "depends": ["cli>=1.0", "fmt>=1.1"]},
        "archive":     {"versions": ["1.0.0"],
                        "depends": ["json>=2.0"],
                        "optional_depends": ["archive-sse"]},
        "archive-sse": {"versions": ["0.2.0"], "depends": ["archive>=1.0"]},
    }


class CircularDependencyTests(unittest.TestCase):

    def test_self_dependency_is_a_cycle(self):
        # 现象 1：包把自己写进依赖列表，必须报循环依赖。
        manifest = {"loop": {"versions": ["1.0.0"], "depends": ["loop"]}}
        with self.assertRaises(CircularDependencyError) as ctx:
            resolve(manifest, ["loop"])
        self.assertEqual(ctx.exception.chain, ["loop", "loop"])

    def test_self_dependency_with_version_constraint(self):
        manifest = {"loop": {"versions": ["1.0.0"], "depends": ["loop>=1.0"]}}
        with self.assertRaises(CircularDependencyError):
            resolve(manifest, ["loop"])

    def test_indirect_cycle_reports_chain(self):
        manifest = {
            "a": {"versions": ["1.0.0"], "depends": ["b"]},
            "b": {"versions": ["1.0.0"], "depends": ["c"]},
            "c": {"versions": ["1.0.0"], "depends": ["a"]},
        }
        with self.assertRaises(CircularDependencyError) as ctx:
            resolve(manifest, ["a"])
        self.assertEqual(ctx.exception.chain, ["a", "b", "c", "a"])


class DeterminismTests(unittest.TestCase):

    def test_repeated_resolve_in_one_process(self):
        # 现象 2：同一份清单重复解析，结果必须逐项一致。
        manifest = make_manifest()
        requests = ["report", "cli", "archive"]
        first = resolve(manifest, requests)
        for _ in range(20):
            self.assertEqual(resolve(manifest, requests), first)

    def test_resolve_independent_of_python_hash_seed(self):
        # set 迭代顺序受 PYTHONHASHSEED 影响，用子进程在不同种子下复算。
        script = (
            "from depsolve import resolve;"
            "import json, tests.test_regressions as t;"
            "print(json.dumps(resolve(t.make_manifest(), "
            "['report', 'cli', 'archive', 'fmt', 'json'])))"
        )
        outputs = set()
        for seed in ("0", "1", "42", "12345"):
            proc = subprocess.run(
                [sys.executable, "-c", script],
                cwd=REPO_ROOT,
                env={**os.environ, "PYTHONHASHSEED": seed},
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            outputs.add(proc.stdout.strip())
        self.assertEqual(len(outputs), 1, f"不同 hash 种子下输出不一致: {outputs}")

    def test_duplicate_requests_do_not_change_output(self):
        manifest = make_manifest()
        self.assertEqual(
            resolve(manifest, ["cli", "cli", "cli"]),
            resolve(manifest, ["cli"]),
        )


class OptionalDependencyTests(unittest.TestCase):

    def test_disabled_optional_group_is_ignored(self):
        # 现象 3：未启用的可选组（与主包成环）不应参与解析。
        order = resolve(make_manifest(), ["archive"])
        names = [item.split("@")[0] for item in order]
        self.assertNotIn("archive-sse", names)
        self.assertEqual(names[-1], "archive")

    def test_enabled_optional_group_enters_graph(self):
        manifest = {
            "archive": {"versions": ["1.0.0"], "optional_depends": ["sse"]},
            "sse": {"versions": ["0.2.0"], "depends": ["helper"]},
            "helper": {"versions": ["1.0.0"]},
        }
        order = resolve(manifest, ["archive"], enabled={"sse"})
        names = [item.split("@")[0] for item in order]
        self.assertIn("sse", names)
        self.assertIn("helper", names)
        self.assertEqual(names[-1], "archive")

    def test_enabled_optional_cycle_still_detected(self):
        with self.assertRaises(CircularDependencyError) as ctx:
            resolve(make_manifest(), ["archive"], enabled={"archive-sse"})
        self.assertEqual(ctx.exception.chain,
                         ["archive", "archive-sse", "archive"])


class VersionConflictTests(unittest.TestCase):

    def test_incompatible_constraints_raise_conflict(self):
        # 现象 4：json>=2.0 与 json<2.0 互斥，必须报冲突而不是静默锁版本。
        with self.assertRaises(ConflictError) as ctx:
            resolve(make_manifest(), ["gateway"])
        message = str(ctx.exception)
        self.assertIn("json", message)
        self.assertIn(">=2.0", message)
        self.assertIn("<2.0", message)

    def test_multi_entry_conflict_raise_conflict(self):
        with self.assertRaises(ConflictError):
            resolve(make_manifest(), ["gateway", "cli"])

    def test_compatible_constraints_select_highest(self):
        manifest = {
            "x": {"versions": ["1.0.0", "1.2.0", "2.0.0"]},
            "a": {"versions": ["1.0.0"], "depends": ["x>=1.0"]},
            "b": {"versions": ["1.0.0"], "depends": ["x<2.0"]},
        }
        order = resolve(manifest, ["a", "b"])
        self.assertIn("x@1.2.0", order)

    def test_unconstrained_selects_highest(self):
        manifest = {
            "x": {"versions": ["1.0.0", "2.0.0"]},
            "a": {"versions": ["1.0.0"], "depends": ["x"]},
        }
        self.assertEqual(resolve(manifest, ["a"]), ["x@2.0.0", "a@1.0.0"])


class GeneralSemanticsTests(unittest.TestCase):

    def test_topological_order_dependees_first(self):
        order = resolve(make_manifest(), ["cli"])
        names = [item.split("@")[0] for item in order]
        self.assertEqual(names.index("unicode"), 0)
        self.assertLess(names.index("fmt"), names.index("cli"))
        self.assertLess(names.index("json"), names.index("cli"))
        self.assertEqual(names[-1], "cli")

    def test_resolver_class_api_unchanged(self):
        order = Resolver(make_manifest()).resolve(["cli"])
        self.assertEqual(order[-1], "cli@1.0.0")

    def test_unknown_dependency_raises(self):
        manifest = {"a": {"versions": ["1.0.0"], "depends": ["ghost"]}}
        with self.assertRaises(UnknownPackageError):
            resolve(manifest, ["a"])

    def test_unknown_entry_raises(self):
        with self.assertRaises(UnknownPackageError):
            resolve({"a": {"versions": ["1.0.0"]}}, ["ghost"])


if __name__ == "__main__":
    unittest.main()
