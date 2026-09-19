"""Router 现有解析行为的锁定测试。"""

import unittest

from webpath.router import NotFound, Router


def h_health():
    return "ok"


def h_user():
    return "user"


def h_user_posts():
    return "posts"


class TestStaticRoutes(unittest.TestCase):
    def test_exact_match_returns_handler_and_empty_params(self):
        r = Router()
        r.add_route("GET", "/health", h_health)
        self.assertEqual(r.resolve("GET", "/health"), (h_health, {}))

    def test_static_mismatch_raises(self):
        r = Router()
        r.add_route("GET", "/health", h_health)
        with self.assertRaises(NotFound):
            r.resolve("GET", "/healthz")


class TestParamRoutes(unittest.TestCase):
    def test_param_extracted(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_user)
        self.assertEqual(r.resolve("GET", "/users/42"), (h_user, {"id": "42"}))

    def test_two_params(self):
        r = Router()
        r.add_route("GET", "/users/{id}/posts/{pid}", h_user_posts)
        self.assertEqual(
            r.resolve("GET", "/users/42/posts/7"),
            (h_user_posts, {"id": "42", "pid": "7"}),
        )

    def test_param_needs_exact_segment_count(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_user)
        with self.assertRaises(NotFound):
            r.resolve("GET", "/users/42/posts")

    def test_empty_segment_does_not_match_param(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_user)
        with self.assertRaises(NotFound):
            r.resolve("GET", "/users/")


class TestOrderingAndMethods(unittest.TestCase):
    def test_identical_path_first_registration_wins(self):
        r = Router()
        r.add_route("GET", "/a/b", h_health)
        r.add_route("GET", "/a/b", h_user)
        self.assertIs(r.resolve("GET", "/a/b")[0], h_health)

    def test_dynamic_falls_through_static_miss(self):
        # 静态段不匹配时继续尝试后面的路由
        r = Router()
        r.add_route("GET", "/a/static", h_health)
        r.add_route("GET", "/a/{x}", h_user)
        self.assertEqual(r.resolve("GET", "/a/other"), (h_user, {"x": "other"}))
        self.assertEqual(r.resolve("GET", "/a/static"), (h_health, {}))

    def test_methods_are_independent(self):
        r = Router()
        r.add_route("GET", "/thing", h_health)
        r.add_route("POST", "/thing", h_user)
        self.assertIs(r.resolve("GET", "/thing")[0], h_health)
        self.assertIs(r.resolve("POST", "/thing")[0], h_user)


class TestNotFound(unittest.TestCase):
    def test_unknown_path(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_user)
        with self.assertRaises(NotFound):
            r.resolve("GET", "/orders/5")

    def test_unknown_method_with_unknown_path(self):
        r = Router()
        r.add_route("GET", "/health", h_health)
        with self.assertRaises(NotFound):
            r.resolve("DELETE", "/nope")

    def test_trailing_slash_is_strict_by_default(self):
        r = Router()
        r.add_route("GET", "/foo", h_health)
        r.add_route("GET", "/bar/", h_user)
        with self.assertRaises(NotFound):
            r.resolve("GET", "/foo/")
        with self.assertRaises(NotFound):
            r.resolve("GET", "/bar")


if __name__ == "__main__":
    unittest.main()
