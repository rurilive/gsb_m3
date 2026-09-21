"""密钥派生与伪随机流的锁定测试。"""

import unittest

from vaultfile.keystream import (
    BadKeyError,
    derive,
    keystream,
    mac,
    normalize_key,
    random_nonce,
    verify_mac,
    xor_stream,
)

KEY = b"unit-test-key-0123456789"
OTHER_KEY = b"unit-test-key-9876543210"
NONCE = b"0123456789abcdef"


class TestNormalizeKey(unittest.TestCase):
    def test_bytes_pass_through(self):
        self.assertEqual(normalize_key(KEY), KEY)

    def test_bytearray_is_copied_to_bytes(self):
        self.assertEqual(normalize_key(bytearray(KEY)), KEY)

    def test_rejects_short_and_long_keys(self):
        for bad in (b"", b"x" * 15, b"x" * 65):
            with self.assertRaises(BadKeyError):
                normalize_key(bad)

    def test_rejects_non_bytes(self):
        for bad in ("text", 7, None, [1, 2]):
            with self.assertRaises(BadKeyError):
                normalize_key(bad)


class TestDerive(unittest.TestCase):
    def test_deterministic(self):
        self.assertEqual(derive(KEY, b"enc", b"salt"), derive(KEY, b"enc", b"salt"))

    def test_labels_separate_subkeys(self):
        self.assertNotEqual(derive(KEY, b"enc", b"salt"), derive(KEY, b"mac", b"salt"))

    def test_info_changes_result(self):
        self.assertNotEqual(derive(KEY, b"enc", b"a"), derive(KEY, b"enc", b"b"))

    def test_key_changes_result(self):
        self.assertNotEqual(derive(KEY, b"enc"), derive(OTHER_KEY, b"enc"))

    def test_output_is_digest_sized(self):
        self.assertEqual(len(derive(KEY, b"enc")), 32)

    def test_rejects_empty_label(self):
        with self.assertRaises(BadKeyError):
            derive(KEY, b"")


class TestKeystream(unittest.TestCase):
    def test_same_input_same_stream(self):
        self.assertEqual(keystream(KEY, NONCE, 100), keystream(KEY, NONCE, 100))

    def test_nonce_changes_stream(self):
        self.assertNotEqual(keystream(KEY, NONCE, 64), keystream(KEY, b"fedcba9876543210", 64))

    def test_key_changes_stream(self):
        self.assertNotEqual(keystream(KEY, NONCE, 64), keystream(OTHER_KEY, NONCE, 64))

    def test_length_is_exact(self):
        for size in (0, 1, 31, 32, 33, 1000):
            self.assertEqual(len(keystream(KEY, NONCE, size)), size)

    def test_longer_stream_extends_shorter_one(self):
        self.assertEqual(keystream(KEY, NONCE, 40), keystream(KEY, NONCE, 128)[:40])

    def test_blocks_do_not_repeat(self):
        stream = keystream(KEY, NONCE, 64)
        self.assertNotEqual(stream[:32], stream[32:])

    def test_rejects_empty_nonce(self):
        with self.assertRaises(BadKeyError):
            keystream(KEY, b"", 16)


class TestXorStream(unittest.TestCase):
    def test_round_trip(self):
        data = bytes(range(256)) * 5
        self.assertEqual(xor_stream(KEY, NONCE, xor_stream(KEY, NONCE, data)), data)

    def test_empty_payload(self):
        self.assertEqual(xor_stream(KEY, NONCE, b""), b"")

    def test_output_differs_from_input(self):
        data = b"\x00" * 64
        self.assertNotEqual(xor_stream(KEY, NONCE, data), data)

    def test_rejects_str(self):
        with self.assertRaises(TypeError):
            xor_stream(KEY, NONCE, "text")

    def test_different_nonce_gives_different_ciphertext(self):
        data = b"same plaintext" * 4
        self.assertNotEqual(xor_stream(KEY, NONCE, data), xor_stream(KEY, b"fedcba9876543210", data))


class TestMac(unittest.TestCase):
    def test_length(self):
        self.assertEqual(len(mac(KEY, b"payload")), 32)

    def test_verify_round_trip(self):
        self.assertTrue(verify_mac(KEY, b"payload", mac(KEY, b"payload")))

    def test_rejects_modified_message(self):
        self.assertFalse(verify_mac(KEY, b"payloae", mac(KEY, b"payload")))

    def test_rejects_wrong_key(self):
        self.assertFalse(verify_mac(OTHER_KEY, b"payload", mac(KEY, b"payload")))

    def test_rejects_wrong_length_tag(self):
        self.assertFalse(verify_mac(KEY, b"payload", b"short"))


class TestRandomNonce(unittest.TestCase):
    def test_length_and_freshness(self):
        first, second = random_nonce(16), random_nonce(16)
        self.assertEqual(len(first), 16)
        self.assertNotEqual(first, second)

    def test_rejects_non_positive(self):
        for bad in (0, -3):
            with self.assertRaises(ValueError):
                random_nonce(bad)


if __name__ == "__main__":
    unittest.main()
