import unittest

from sealstore import SealError, canonical_bytes, record_digest


class CanonicalBytesTests(unittest.TestCase):
    def test_key_order_does_not_matter(self):
        one = canonical_bytes({"b": 1, "a": {"d": 2, "c": 3}})
        two = canonical_bytes({"a": {"c": 3, "d": 2}, "b": 1})
        self.assertEqual(one, two)

    def test_output_is_compact_utf8(self):
        data = canonical_bytes({"name": "北京", "n": 1})
        self.assertEqual(data, '{"n":1,"name":"北京"}'.encode("utf-8"))
        self.assertNotIn(b" ", data)

    def test_int_and_float_are_distinct(self):
        self.assertNotEqual(canonical_bytes({"v": 1}), canonical_bytes({"v": 1.0}))

    def test_bool_and_int_are_distinct(self):
        self.assertNotEqual(canonical_bytes({"v": True}), canonical_bytes({"v": 1}))

    def test_tuple_normalises_to_list(self):
        self.assertEqual(canonical_bytes({"a": (1, 2)}), canonical_bytes({"a": [1, 2]}))

    def test_non_string_key_is_rejected(self):
        with self.assertRaises(SealError):
            canonical_bytes({1: "x"})

    def test_non_string_key_is_rejected_when_nested(self):
        with self.assertRaises(SealError):
            canonical_bytes({"rows": [{"ok": 1}, {2: "x"}]})

    def test_non_finite_float_is_rejected(self):
        with self.assertRaises(SealError):
            canonical_bytes({"v": float("nan")})
        with self.assertRaises(SealError):
            canonical_bytes({"v": float("inf")})

    def test_record_digest_is_stable_hex(self):
        record = {"id": 7, "tags": ["a", "b"], "meta": {"ok": True}}
        digest = record_digest(record)
        self.assertEqual(len(digest), 64)
        self.assertEqual(digest, record_digest(dict(record)))
        self.assertNotEqual(digest, record_digest({"id": 8, "tags": ["a", "b"], "meta": {"ok": True}}))

    def test_record_digest_sees_key_order_only_once(self):
        self.assertEqual(
            record_digest({"x": 1, "y": 2}), record_digest({"y": 2, "x": 1})
        )


if __name__ == "__main__":
    unittest.main()
