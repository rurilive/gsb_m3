"""cookiest 防回归测试：域名匹配、路径匹配、过期时区、序列化标记。"""

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

from cookiest import Cookie, CookieJar, parse_expires, parse_set_cookie


class DomainMatchTest(unittest.TestCase):
    """现象 1：evil-example.com 不应拿到 example.com 的 cookie。"""

    def setUp(self):
        self.jar = CookieJar()
        self.jar.add(parse_set_cookie(
            "sessionid=s-1; Domain=example.com; Path=/"))

    def names(self, url):
        return [c.name for c in self.jar.match_for(url)]

    def test_exact_host_matches(self):
        self.assertEqual(self.names("https://example.com/"), ["sessionid"])

    def test_subdomain_matches(self):
        self.assertEqual(self.names("https://www.example.com/"), ["sessionid"])

    def test_sibling_suffix_domain_rejected(self):
        self.assertEqual(self.names("https://evil-example.com/"), [])

    def test_unrelated_domain_rejected(self):
        self.assertEqual(self.names("https://notexample.com/"), [])
        self.assertEqual(self.names("https://example.com.evil.io/"), [])

    def test_leading_dot_domain_still_matches_subdomain(self):
        jar = CookieJar()
        jar.add(parse_set_cookie("k=v; Domain=.example.com; Path=/"))
        self.assertEqual(
            [c.name for c in jar.match_for("https://a.example.com/")], ["k"])
        self.assertEqual(jar.match_for("https://evil-example.com/"), [])


class PathMatchTest(unittest.TestCase):
    """现象 2：Path=/pay 的 cookie 不应发给 /paypal。"""

    def setUp(self):
        self.jar = CookieJar()
        self.jar.add(parse_set_cookie("csrf=t-1; Domain=example.com; Path=/pay"))
        self.jar.add(parse_set_cookie("theme=dark; Domain=example.com; Path=/"))

    def names(self, url):
        return [c.name for c in self.jar.match_for(url)]

    def test_exact_path_matches(self):
        self.assertIn("csrf", self.names("https://example.com/pay"))

    def test_sub_path_matches(self):
        self.assertIn("csrf", self.names("https://example.com/pay/confirm"))

    def test_sibling_prefix_path_rejected(self):
        self.assertNotIn("csrf", self.names("https://example.com/paypal/checkout"))

    def test_root_path_still_matches_everything(self):
        self.assertIn("theme", self.names("https://example.com/paypal/checkout"))

    def test_longer_path_sorted_first(self):
        self.assertEqual(
            self.names("https://example.com/pay/confirm"), ["csrf", "theme"])


class ExpiryTest(unittest.TestCase):
    """现象 3：GMT 的 Expires 不能按本地时区折算（凌晨集中掉登录）。"""

    def test_parse_expires_is_utc_aware(self):
        expires = parse_expires("Wed, 21 Oct 2015 07:28:00 GMT")
        self.assertIsNotNone(expires)
        self.assertEqual(expires.tzinfo, timezone.utc)
        self.assertEqual(expires, datetime(2015, 10, 21, 7, 28, 0,
                                           tzinfo=timezone.utc))

    def test_gmt_expiry_not_shifted_by_local_timezone(self):
        # 上游签发：Expires 为 GMT 08:00。按 UTC+8 误读会提前 8 小时、
        # 在北京时间凌晨 00:00 掉登录；修复后应活到北京时间 16:00。
        expires = parse_expires("Thu, 01 Jan 2032 08:00:00 GMT")
        cookie = Cookie("sessionid", "s-1", "example.com", expires=expires)
        before = datetime(2032, 1, 1, 7, 59, 59, tzinfo=timezone.utc)
        after = datetime(2032, 1, 1, 8, 0, 1, tzinfo=timezone.utc)
        self.assertFalse(cookie.is_expired(before))
        self.assertTrue(cookie.is_expired(after))

    def test_jar_filters_expired_with_injected_clock(self):
        now = datetime(2032, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        jar = CookieJar(clock=lambda: now)
        jar.set_cookie("live", "1", "example.com",
                       expires=now + timedelta(hours=1))
        jar.set_cookie("dead", "1", "example.com",
                       expires=now - timedelta(hours=1))
        self.assertEqual([c.name for c in jar.match_for("https://example.com/")],
                         ["live"])

    def test_session_cookie_without_expires_never_expires(self):
        now = datetime(2032, 1, 1, tzinfo=timezone.utc)
        jar = CookieJar(clock=lambda: now)
        jar.set_cookie("s", "1", "example.com")
        self.assertEqual(len(jar.match_for("https://example.com/")), 1)


class SerializationTest(unittest.TestCase):
    """现象 4：dump/load 必须保留 secure / http_only 标记。"""

    def test_flags_survive_round_trip(self):
        jar = CookieJar()
        jar.add(parse_set_cookie(
            "sessionid=s-1; Domain=example.com; Path=/; Secure; HttpOnly"))
        jar.add(parse_set_cookie("theme=dark; Domain=example.com; Path=/"))
        path = os.path.join(tempfile.mkdtemp(prefix="cookiest-test-"),
                            "cookies.json")
        jar.dump(path)

        jar2 = CookieJar()
        jar2.load(path)
        restored = {c.name: c for c in jar2.snapshot()}
        self.assertTrue(restored["sessionid"].secure)
        self.assertTrue(restored["sessionid"].http_only)
        self.assertFalse(restored["theme"].secure)
        self.assertFalse(restored["theme"].http_only)

    def test_expires_survives_round_trip(self):
        expires = datetime(2032, 1, 1, 8, 0, 0, tzinfo=timezone.utc)
        jar = CookieJar()
        jar.set_cookie("s", "1", "example.com", expires=expires, secure=True)
        path = os.path.join(tempfile.mkdtemp(prefix="cookiest-test-"),
                            "cookies.json")
        jar.dump(path)
        jar2 = CookieJar()
        jar2.load(path)
        self.assertEqual(jar2.snapshot()[0].expires, expires)

    def test_load_legacy_dump_without_flags(self):
        # 旧版本导出的 JSON 没有 secure/http_only 字段，应兼容加载。
        legacy = [{"name": "s", "value": "1", "domain": "example.com",
                   "path": "/", "expires": None}]
        path = os.path.join(tempfile.mkdtemp(prefix="cookiest-test-"),
                            "cookies.json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(legacy, fh)
        jar = CookieJar()
        jar.load(path)
        cookie = jar.snapshot()[0]
        self.assertFalse(cookie.secure)
        self.assertFalse(cookie.http_only)


class SecureSchemeTest(unittest.TestCase):

    def test_secure_cookie_not_sent_over_http(self):
        jar = CookieJar()
        jar.set_cookie("s", "1", "example.com", secure=True)
        self.assertEqual(jar.match_for("http://example.com/"), [])
        self.assertEqual(len(jar.match_for("https://example.com/")), 1)


if __name__ == "__main__":
    unittest.main()
