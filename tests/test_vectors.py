"""tests/vectors.py 参考向量的逐字节对拍。

编码方向比字节，解码方向比值（NaN 单独按位宽比），再编码必须
回到同一份字节，保证规范形稳定。
"""

import math
import unittest

from packwire import decode, encode

from vectors import VECTORS


class EncodeVectorTests(unittest.TestCase):
    def test_encode_matches_reference_bytes(self):
        for value, hex_text in VECTORS:
            with self.subTest(value=value):
                self.assertEqual(encode(value).hex(), hex_text)


class DecodeVectorTests(unittest.TestCase):
    def test_decode_matches_reference_values(self):
        for value, hex_text in VECTORS:
            data = bytes.fromhex(hex_text)
            with self.subTest(value=value):
                got = decode(data)
                if isinstance(value, float) and math.isnan(value):
                    self.assertIsInstance(got, float)
                    self.assertTrue(math.isnan(got))
                else:
                    self.assertEqual(got, value)

    def test_decoded_values_reencode_to_same_bytes(self):
        for value, hex_text in VECTORS:
            with self.subTest(value=value):
                again = encode(decode(bytes.fromhex(hex_text)))
                self.assertEqual(again.hex(), hex_text)


if __name__ == "__main__":
    unittest.main()
