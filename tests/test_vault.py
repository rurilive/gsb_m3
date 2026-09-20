"""seal/unseal 的锁定测试。"""

import os
import tempfile
import unittest

from vaultfile import (
    AuthError,
    UnknownKeyError,
    seal,
    seal_file,
    unseal,
    unseal_file,
)
from vaultfile.format import HEADER_LEN

KEY = b"vault-unit-test-key-01"
OTHER_KEY = b"vault-unit-test-key-02"
MESSAGE = "期初余额 1204332.00 元".encode("utf-8")
BIG = bytes(range(256)) * 40


class TestSealUnseal(unittest.TestCase):
    def test_round_trip(self):
        self.assertEqual(unseal(seal(MESSAGE, KEY), KEY), MESSAGE)

    def test_empty_payload(self):
        self.assertEqual(unseal(seal(b"", KEY), KEY), b"")

    def test_binary_payload(self):
        self.assertEqual(unseal(seal(BIG, KEY), KEY), BIG)

    def test_salt_is_fresh_so_ciphertexts_differ(self):
        self.assertNotEqual(seal(MESSAGE, KEY), seal(MESSAGE, KEY))

    def test_accepts_bytearray_payload(self):
        self.assertEqual(unseal(seal(bytearray(MESSAGE), KEY), KEY), MESSAGE)

    def test_rejects_str_payload(self):
        with self.assertRaises(TypeError):
            seal("text", KEY)

    def test_wrong_key_fails(self):
        with self.assertRaises(AuthError):
            unseal(seal(MESSAGE, KEY), OTHER_KEY)

    def test_tampered_ciphertext_fails(self):
        blob = bytearray(seal(MESSAGE, KEY))
        blob[HEADER_LEN] ^= 0x01
        with self.assertRaises(AuthError):
            unseal(bytes(blob), KEY)

    def test_tampered_header_salt_fails(self):
        blob = bytearray(seal(MESSAGE, KEY))
        blob[6] ^= 0xFF
        with self.assertRaises(AuthError):
            unseal(bytes(blob), KEY)

    def test_tampered_key_version_fails(self):
        blob = bytearray(seal(MESSAGE, KEY))
        blob[5] ^= 0xFF
        with self.assertRaises(AuthError):
            unseal(bytes(blob), KEY)

    def test_truncated_blob_fails(self):
        blob = seal(MESSAGE, KEY)
        for cut in (1, 5, HEADER_LEN, len(blob) - 1):
            with self.assertRaises(AuthError):
                unseal(blob[:cut], KEY)

    def test_garbage_fails(self):
        for bad in (b"", b"not a container", os.urandom(64)):
            with self.assertRaises(AuthError):
                unseal(bad, KEY)


class TestKeyVersions(unittest.TestCase):
    def test_keyring_selects_by_version(self):
        keyring = {1: KEY, 7: OTHER_KEY}
        blob = seal(MESSAGE, keyring, key_version=7)
        self.assertEqual(unseal(blob, keyring), MESSAGE)

    def test_missing_version_raises(self):
        blob = seal(MESSAGE, {7: OTHER_KEY}, key_version=7)
        with self.assertRaises(UnknownKeyError):
            unseal(blob, {1: KEY})

    def test_wrong_key_for_version_fails(self):
        blob = seal(MESSAGE, {7: OTHER_KEY}, key_version=7)
        with self.assertRaises(AuthError):
            unseal(blob, {7: KEY})

    def test_seal_rejects_version_missing_from_keyring(self):
        with self.assertRaises(UnknownKeyError):
            seal(MESSAGE, {1: KEY}, key_version=9)

    def test_bare_key_ignores_version(self):
        self.assertEqual(unseal(seal(MESSAGE, KEY, key_version=42), KEY), MESSAGE)


class TestFileHelpers(unittest.TestCase):
    def test_round_trip_through_disk(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.vlt")
            written = seal_file(path, MESSAGE, KEY)
            self.assertEqual(written, os.path.getsize(path))
            self.assertEqual(unseal_file(path, KEY), MESSAGE)

    def test_file_with_wrong_key_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "report.vlt")
            seal_file(path, MESSAGE, KEY)
            with self.assertRaises(AuthError):
                unseal_file(path, OTHER_KEY)

    def test_missing_file_raises_oserror(self):
        with self.assertRaises(OSError):
            unseal_file("/nonexistent/dir/report.vlt", KEY)


if __name__ == "__main__":
    unittest.main()
