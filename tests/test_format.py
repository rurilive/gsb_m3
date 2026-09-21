"""容器结构层的锁定测试。"""

import unittest

from vaultfile.format import (
    HEADER_LEN,
    MAGIC_V1,
    NONCE_LEN,
    SALT_LEN,
    TAG_LEN,
    FormatError,
    looks_v1,
    pack_v1,
    parse_v1,
)

SALT = b"s" * SALT_LEN
NONCE = b"n" * NONCE_LEN


def container(ciphertext=b"", key_version=1, tag=b"t" * TAG_LEN):
    header = pack_v1(key_version, SALT, NONCE, len(ciphertext))
    return header + ciphertext + tag


class TestPack(unittest.TestCase):
    def test_header_length_and_layout(self):
        header = pack_v1(3, SALT, NONCE, 12)
        self.assertEqual(len(header), HEADER_LEN)
        self.assertEqual(header[:4], MAGIC_V1)
        self.assertEqual(header[4], 1)
        self.assertEqual(header[5], 3)
        self.assertEqual(header[6:22], SALT)
        self.assertEqual(header[22:38], NONCE)
        self.assertEqual(header[-8:], (12).to_bytes(8, "big"))

    def test_rejects_key_version_out_of_range(self):
        for bad in (-1, 256):
            with self.assertRaises(FormatError):
                pack_v1(bad, SALT, NONCE, 0)

    def test_rejects_wrong_salt_length(self):
        with self.assertRaises(FormatError):
            pack_v1(1, b"short", NONCE, 0)

    def test_rejects_wrong_nonce_length(self):
        with self.assertRaises(FormatError):
            pack_v1(1, SALT, b"short", 0)

    def test_rejects_negative_length(self):
        with self.assertRaises(FormatError):
            pack_v1(1, SALT, NONCE, -1)


class TestParse(unittest.TestCase):
    def test_round_trip(self):
        blob = container(b"abcdef")
        header, version, salt, nonce, ciphertext, tag = parse_v1(blob)
        self.assertEqual(version, 1)
        self.assertEqual(salt, SALT)
        self.assertEqual(nonce, NONCE)
        self.assertEqual(ciphertext, b"abcdef")
        self.assertEqual(tag, b"t" * TAG_LEN)
        self.assertEqual(header, pack_v1(1, SALT, NONCE, 6))

    def test_accepts_empty_payload(self):
        _, _, _, _, ciphertext, _ = parse_v1(container())
        self.assertEqual(ciphertext, b"")

    def test_rejects_bad_magic(self):
        with self.assertRaises(FormatError):
            parse_v1(b"XXXX" + container(b"abc")[4:])

    def test_rejects_short_blob(self):
        with self.assertRaises(FormatError):
            parse_v1(b"VLT1" + b"\x00" * 10)

    def test_rejects_truncated_ciphertext(self):
        blob = container(b"abcdef")
        with self.assertRaises(FormatError):
            parse_v1(blob[: HEADER_LEN + 3] + blob[-TAG_LEN:])

    def test_rejects_padded_ciphertext(self):
        blob = container(b"abcdef")
        with self.assertRaises(FormatError):
            parse_v1(blob[:-TAG_LEN] + b"x" + blob[-TAG_LEN:])

    def test_rejects_non_bytes(self):
        with self.assertRaises(FormatError):
            parse_v1("VLT1 not bytes")


class TestLooksV1(unittest.TestCase):
    def test_recognizes_container(self):
        self.assertTrue(looks_v1(container()))
        self.assertTrue(looks_v1(bytearray(container())))

    def test_rejects_other_bytes(self):
        self.assertFalse(looks_v1(b"nope"))
        self.assertFalse(looks_v1(b""))


if __name__ == "__main__":
    unittest.main()
