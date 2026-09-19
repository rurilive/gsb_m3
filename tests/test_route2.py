"""路由升级行为的测试：优先级、尾斜杠策略、Http405。"""

import unittest

from webpath.router import Http405, NotFound, Router


def h_static():
    return "static"


def h_dynamic():
    return "dynamic"


def h_other():
    return "other"


class TestPriority(unittest.TestCase):
    def test_static_beats_dynamic_regardless_of_registration_order(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_dynamic)
        r.add_route("GET", "/users/new", h_static)
        self.assertIs(r.resolve("GET", "/users/new")[0], h_static)
        self.assertEqual(r.resolve("GET", "/users/42"), (h_dynamic, {"id": "42"}))

    def test_more_static_segments_wins(self):
        r = Router()
        r.add_route("GET", "/a/{x}/{y}", h_dynamic)
        r.add_route("GET", "/a/{x}/c", h_static)
        self.assertIs(r.resolve("GET", "/a/b/c")[0], h_static)
        self.assertEqual(r.resolve("GET", "/a/b/d"), (h_dynamic, {"x": "b", "y": "d"}))

    def test_tie_falls_back_to_registration_order(self):
        r = Router()
        r.add_route("GET", "/a/{x}", h_dynamic)
        r.add_route("GET", "/a/{y}", h_other)
        self.assertIs(r.resolve("GET", "/a/1")[0], h_dynamic)

    def test_priority_is_per_method(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_dynamic)
        r.add_route("POST", "/users/new", h_static)
        self.assertEqual(r.resolve("GET", "/users/new"), (h_dynamic, {"id": "new"}))
        self.assertIs(r.resolve("POST", "/users/new")[0], h_static)


class TestTrailingStrict(unittest.TestCase):
    def test_default_is_strict(self):
        r = Router()
        r.add_route("GET", "/foo", h_static)
        with self.assertRaises(NotFound):
            r.resolve("GET", "/foo/")

    def test_explicit_strict(self):
        r = Router(trailing="strict")
        r.add_route("GET", "/foo/", h_static)
        with self.assertRaises(NotFound):
            r.resolve("GET", "/foo")

    def test_unknown_policy_rejected(self):
        with self.assertRaises(ValueError):
            Router(trailing="loose")


class TestTrailingRedirect(unittest.TestCase):
    def test_exact_match_needs_no_redirect(self):
        r = Router(trailing="redirect")
        r.add_route("GET", "/foo", h_static)
        self.assertEqual(r.resolve("GET", "/foo"), (h_static, {}, False))

    def test_extra_slash_redirects(self):
        r = Router(trailing="redirect")
        r.add_route("GET", "/foo", h_static)
        self.assertEqual(r.resolve("GET", "/foo/"), (h_static, {}, True))

    def test_missing_slash_redirects(self):
        r = Router(trailing="redirect")
        r.add_route("GET", "/bar/", h_static)
        self.assertEqual(r.resolve("GET", "/bar"), (h_static, {}, True))

    def test_redirect_keeps_params(self):
        r = Router(trailing="redirect")
        r.add_route("GET", "/users/{id}", h_dynamic)
        self.assertEqual(r.resolve("GET", "/users/42/"), (h_dynamic, {"id": "42"}, True))

    def test_no_match_either_way_raises_not_found(self):
        r = Router(trailing="redirect")
        r.add_route("GET", "/foo", h_static)
        with self.assertRaises(NotFound):
            r.resolve("GET", "/nope")


class TestHttp405(unittest.TestCase):
    def test_wrong_method_known_path_raises_405(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_dynamic)
        with self.assertRaises(Http405) as ctx:
            r.resolve("POST", "/users/42")
        self.assertEqual(ctx.exception.allow, ["GET"])

    def test_allow_dedupes_in_registration_order(self):
        r = Router()
        r.add_route("POST", "/thing", h_static)
        r.add_route("GET", "/thing", h_dynamic)
        r.add_route("POST", "/thing", h_other)
        with self.assertRaises(Http405) as ctx:
            r.resolve("DELETE", "/thing")
        self.assertEqual(ctx.exception.allow, ["POST", "GET"])

    def test_shape_ignores_param_values(self):
        r = Router()
        r.add_route("GET", "/users/{id}/posts/{pid}", h_dynamic)
        with self.assertRaises(Http405) as ctx:
            r.resolve("PUT", "/users/7/posts/9")
        self.assertEqual(ctx.exception.allow, ["GET"])

    def test_different_shape_is_not_405(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_dynamic)
        with self.assertRaises(NotFound) as ctx:
            r.resolve("POST", "/users/42/posts")
        self.assertNotIsInstance(ctx.exception, Http405)

    def test_unknown_path_is_not_405(self):
        r = Router()
        r.add_route("GET", "/users/{id}", h_dynamic)
        with self.assertRaises(NotFound) as ctx:
            r.resolve("POST", "/orders/42")
        self.assertNotIsInstance(ctx.exception, Http405)

    def test_http405_is_a_not_found(self):
        self.assertTrue(issubclass(Http405, NotFound))


if __name__ == "__main__":
    unittest.main()
