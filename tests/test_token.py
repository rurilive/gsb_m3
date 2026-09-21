import unittest

from tokengate import InvalidSignature, KeyRing, MalformedToken, UnknownKey

import tokengate.token as token_mod
from tokengate.token import canonical_json, sign_payload, split_token, verify_token


def ring(**secrets):
    return KeyRing({kid: secret for kid, secret in secrets.items()})


class SignAndVerifyTests(unittest.TestCase):
    def setUp(self):
        self.ring = ring(k1="correct horse battery staple", k2="second secret")
        self.payload = {"sub": "u-17", "role": "admin"}

    def test_roundtrip_returns_equal_payload(self):
        tok = sign_payload(self.payload, self.ring)
        self.assertEqual(verify_token(tok, self.ring), self.payload)

    def test_key_order_does_not_change_token(self):
        a = sign_payload({"a": 1, "b": 2}, self.ring)
        b = sign_payload({"b": 2, "a": 1}, self.ring)
        self.assertEqual(a, b)

    def test_unicode_payload_roundtrip(self):
        payload = {"name": "张三", "tag": "会话"}
        tok = sign_payload(payload, self.ring)
        self.assertEqual(verify_token(tok, self.ring), payload)
        self.assertNotIn("\\u", tok)

    def test_empty_payload_roundtrip(self):
        tok = sign_payload({}, self.ring)
        self.assertEqual(verify_token(tok, self.ring), {})

    def test_returned_payload_is_a_copy(self):
        tok = sign_payload(self.payload, self.ring)
        out = verify_token(tok, self.ring)
        out["role"] = "root"
        self.assertEqual(verify_token(tok, self.ring), self.payload)

    def test_kid_selects_the_secret(self):
        tok = sign_payload(self.payload, self.ring, kid="k2")
        header, _, _ = split_token(tok)
        self.assertEqual(header["kid"], "k2")
        self.assertEqual(verify_token(tok, self.ring), self.payload)


class RejectionTests(unittest.TestCase):
    def setUp(self):
        self.ring = ring(k1="correct horse battery staple")
        self.tok = sign_payload({"sub": "u-1"}, self.ring)
        self.head, self.body, self.sig = self.tok.split(".")

    def test_flipped_signature_char(self):
        flipped = "A" if self.sig[0] != "A" else "B"
        tampered = ".".join([self.head, self.body, flipped + self.sig[1:]])
        with self.assertRaises(InvalidSignature):
            verify_token(tampered, self.ring)

    def test_edited_payload(self):
        other = token_mod.b64u_encode(canonical_json({"sub": "u-1", "role": "root"}))
        tampered = ".".join([self.head, other, self.sig])
        with self.assertRaises(InvalidSignature):
            verify_token(tampered, self.ring)

    def test_wrong_key(self):
        with self.assertRaises(InvalidSignature):
            verify_token(self.tok, ring(k1="a different secret"))

    def test_unknown_kid(self):
        other = sign_payload({"sub": "u-1"}, ring(k9="unrelated"), kid="k9")
        with self.assertRaises(UnknownKey):
            verify_token(other, self.ring)

    def test_dropped_kid(self):
        ring2 = ring(k1="one", k2="two")
        tok = sign_payload({"sub": "u-1"}, ring2, kid="k2")
        ring2.drop("k2")
        with self.assertRaises(UnknownKey):
            verify_token(tok, ring2)

    def test_two_segments(self):
        with self.assertRaises(MalformedToken):
            verify_token(self.head + "." + self.body, self.ring)

    def test_empty_segment(self):
        with self.assertRaises(MalformedToken):
            verify_token(self.head + ".." + self.sig, self.ring)

    def test_padding_is_canonical(self):
        tok = sign_payload({"sub": "u-1"}, self.ring)
        self.assertNotIn("=", tok)
        self.assertEqual(tok, tok.rstrip("="))

    def test_non_json_payload_segment(self):
        junk = token_mod.b64u_encode(b"not json at all")
        with self.assertRaises(MalformedToken):
            verify_token(".".join([self.head, junk, self.sig]), self.ring)

    def test_payload_must_be_an_object(self):
        junk = token_mod.b64u_encode(canonical_json(["a", "list"]))
        with self.assertRaises(MalformedToken):
            verify_token(".".join([self.head, junk, self.sig]), self.ring)

    def test_unsupported_alg_is_malformed(self):
        header = token_mod.b64u_encode(canonical_json({"alg": "none", "kid": "k1", "v": 1}))
        with self.assertRaises(MalformedToken):
            verify_token(".".join([header, self.body, self.sig]), self.ring)

    def test_unsupported_version_is_malformed(self):
        header = token_mod.b64u_encode(canonical_json({"alg": "HS256", "kid": "k1", "v": 99}))
        with self.assertRaises(MalformedToken):
            verify_token(".".join([header, self.body, self.sig]), self.ring)

    def test_verify_rejects_non_string(self):
        with self.assertRaises(MalformedToken):
            verify_token(12345, self.ring)

    def test_sign_rejects_non_dict(self):
        with self.assertRaises(TypeError):
            sign_payload(["sub"], self.ring)


class KeyRingTests(unittest.TestCase):
    def test_sorted_kids_and_membership(self):
        r = ring(b="2", a="1")
        self.assertEqual(r.kids(), ["a", "b"])
        self.assertIn("a", r)
        self.assertEqual(len(r), 2)

    def test_str_secret_encoded_as_utf8(self):
        r = KeyRing()
        r.add("k1", "sëcret")
        self.assertEqual(r.secret("k1"), "sëcret".encode("utf-8"))

    def test_missing_secret_raises(self):
        with self.assertRaises(UnknownKey):
            KeyRing().secret("k1")


if __name__ == "__main__":
    unittest.main()
