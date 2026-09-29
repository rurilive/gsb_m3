"""Baseline tests for routex.router.LinearRoute.

These tests lock down the current naive linear-matching behaviour.  They must
stay green and must not be modified by later feature work.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routex.router import (
    DuplicateRouteError,
    InvalidPathError,
    LinearRoute,
    MissingRouteError,
    split_path,
)


class SplitPathTest(unittest.TestCase):
    def test_root_splits_to_empty(self):
        self.assertEqual(split_path("/"), [])

    def test_plain_path_splits_by_slash(self):
        self.assertEqual(split_path("/a/b/c"), ["a", "b", "c"])

    def test_missing_leading_slash_rejected(self):
        with self.assertRaises(InvalidPathError):
            split_path("a/b")

    def test_empty_string_rejected(self):
        with self.assertRaises(InvalidPathError):
            split_path("")

    def test_trailing_slash_rejected(self):
        with self.assertRaises(InvalidPathError):
            split_path("/a/b/")

    def test_double_slash_rejected(self):
        with self.assertRaises(InvalidPathError):
            split_path("/a//b")

    def test_non_string_rejected(self):
        with self.assertRaises(InvalidPathError):
            split_path(123)


class LinearRouteTest(unittest.TestCase):
    def test_static_match_returns_handler(self):
        route = LinearRoute()
        route.add("/users", lambda: "users")
        m = route.match("/users")
        self.assertIsNotNone(m)
        self.assertEqual(m.handler(), "users")

    def test_params_always_empty(self):
        route = LinearRoute()
        route.add("/users", lambda: "users")
        m = route.match("/users")
        self.assertEqual(m.params, {})

    def test_no_match_returns_none(self):
        route = LinearRoute()
        route.add("/users", lambda: "users")
        self.assertIsNone(route.match("/users/list"))

    def test_match_is_exact_not_prefix(self):
        route = LinearRoute()
        route.add("/users", lambda: "users")
        self.assertIsNone(route.match("/users/42"))

    def test_colon_segment_is_literal(self):
        route = LinearRoute()
        route.add("/users/:id", lambda: "detail")
        self.assertIsNotNone(route.match("/users/:id"))
        self.assertIsNone(route.match("/users/42"))

    def test_star_segment_is_literal(self):
        route = LinearRoute()
        route.add("/static/*rest", lambda: "static")
        self.assertIsNotNone(route.match("/static/*rest"))
        self.assertIsNone(route.match("/static/css/app.css"))

    def test_root_path_matches(self):
        route = LinearRoute()
        route.add("/", lambda: "root")
        self.assertEqual(route.match("/").handler(), "root")

    def test_routes_preserve_registration_order(self):
        route = LinearRoute()
        route.add("/b", lambda: "b")
        route.add("/a", lambda: "a")
        self.assertEqual(route.routes(), ["/b", "/a"])

    def test_first_registered_wins_on_same_spelling(self):
        # 线性实现按注册顺序扫描，重复注册会被拒绝，
        # 因此这里注册两条不同路径，确认顺序扫描命中第一条。
        route = LinearRoute()
        route.add("/a", lambda: "first")
        route.add("/b", lambda: "second")
        self.assertEqual(route.match("/a").handler(), "first")
        self.assertEqual(route.match("/b").handler(), "second")

    def test_duplicate_registration_rejected(self):
        route = LinearRoute()
        route.add("/users", lambda: "users")
        with self.assertRaises(DuplicateRouteError):
            route.add("/users", lambda: "other")

    def test_remove_then_miss(self):
        route = LinearRoute()
        route.add("/users", lambda: "users")
        route.remove("/users")
        self.assertIsNone(route.match("/users"))
        self.assertEqual(route.routes(), [])

    def test_remove_unknown_rejected(self):
        route = LinearRoute()
        with self.assertRaises(MissingRouteError):
            route.remove("/nope")

    def test_invalid_path_rejected_on_add(self):
        route = LinearRoute()
        with self.assertRaises(InvalidPathError):
            route.add("users", lambda: "users")

    def test_invalid_path_rejected_on_match(self):
        route = LinearRoute()
        route.add("/users", lambda: "users")
        with self.assertRaises(InvalidPathError):
            route.match("users")


if __name__ == "__main__":
    unittest.main()
