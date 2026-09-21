"""异常体系与偏移约定的锁定测试。"""

import unittest

from packwire import decode, encode
from packwire.errors import DecodeError, EncodeError, PackError


class ExceptionHierarchyTests(unittest.TestCase):
    def test_errors_share_base_class(self):
        self.assertTrue(issubclass(DecodeError, PackError))
        self.assertTrue(issubclass(EncodeError, PackError))
        self.assertTrue(issubclass(PackError, Exception))

    def test_encode_error_is_not_a_decode_error(self):
        self.assertFalse(issubclass(EncodeError, DecodeError))


class OffsetConventionTests(unittest.TestCase):
    def test_offset_is_an_integer(self):
        with self.assertRaises(DecodeError) as ctx:
            decode(b"")
        self.assertIsInstance(ctx.exception.offset, int)

    def test_truncation_offset_points_at_input_end(self):
        data = encode([[1, [2, [3]]]])
        for cut in range(1, len(data)):
            with self.subTest(cut=cut):
                with self.assertRaises(DecodeError) as ctx:
                    decode(data[:cut])
                self.assertEqual(ctx.exception.offset, cut)

    def test_trailing_offset_points_at_first_leftover_byte(self):
        data = encode("payload")
        with self.assertRaises(DecodeError) as ctx:
            decode(data + b"\x00\x00")
        self.assertEqual(ctx.exception.offset, len(data))


if __name__ == "__main__":
    unittest.main()
