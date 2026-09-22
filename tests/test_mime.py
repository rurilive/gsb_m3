"""mime 模块的基线测试。"""

import unittest

from mailnorm.errors import MailParseError
from mailnorm.mime import decode_transfer, parse_content_type


class ParseContentTypeTest(unittest.TestCase):
    def test_empty_value_gives_plain_text(self):
        self.assertEqual(parse_content_type(""), ("text/plain", {}))
        self.assertEqual(parse_content_type(None), ("text/plain", {}))

    def test_media_type_is_lowercased(self):
        media, params = parse_content_type("TEXT/HTML")
        self.assertEqual(media, "text/html")
        self.assertEqual(params, {})

    def test_params_and_quotes(self):
        media, params = parse_content_type(
            'text/plain; charset="utf-8"; format=flowed'
        )
        self.assertEqual(media, "text/plain")
        self.assertEqual(params, {"charset": "utf-8", "format": "flowed"})

    def test_param_names_are_lowercased(self):
        _, params = parse_content_type("multipart/mixed; BOUNDARY=sep")
        self.assertEqual(params, {"boundary": "sep"})

    def test_media_without_slash_falls_back(self):
        media, _ = parse_content_type("garbage")
        self.assertEqual(media, "text/plain")


class DecodeTransferTest(unittest.TestCase):
    def test_identity_encodings(self):
        for encoding in (None, "", "7bit", "8bit", "binary", "BINARY"):
            self.assertEqual(decode_transfer("payload", encoding), "payload")

    def test_unknown_encoding_raises(self):
        with self.assertRaises(MailParseError) as ctx:
            decode_transfer("payload", "x-uuencode")
        self.assertIsNone(ctx.exception.offset)


if __name__ == "__main__":
    unittest.main()
