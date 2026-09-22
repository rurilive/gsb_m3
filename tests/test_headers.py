"""headers 模块的基线测试。"""

import unittest

from mailnorm.errors import MailParseError
from mailnorm.headers import Headers, parse_headers, split_addresses, split_header_lines


class SplitHeaderLinesTest(unittest.TestCase):
    def test_simple_block(self):
        block = "From: a@example.com\nSubject: hi\n"
        self.assertEqual(
            split_header_lines(block),
            [("From", "a@example.com"), ("Subject", "hi")],
        )

    def test_value_whitespace_is_trimmed(self):
        block = "Subject:   spaced out   \n"
        self.assertEqual(split_header_lines(block), [("Subject", "spaced out")])

    def test_empty_and_blank_lines(self):
        self.assertEqual(split_header_lines(""), [])
        self.assertEqual(split_header_lines("\n\n"), [])
        block = "A: 1\n\nB: 2\n"
        self.assertEqual(split_header_lines(block), [("A", "1"), ("B", "2")])

    def test_crlf_endings(self):
        block = "From: a@example.com\r\nSubject: hi\r\n"
        self.assertEqual(
            split_header_lines(block),
            [("From", "a@example.com"), ("Subject", "hi")],
        )

    def test_line_without_colon_reports_position(self):
        block = "From: a@example.com\nthis line has no colon\n"
        with self.assertRaises(MailParseError) as ctx:
            split_header_lines(block)
        self.assertEqual(ctx.exception.offset, len("From: a@example.com\n"))
        self.assertEqual(ctx.exception.line, 2)

    def test_bad_field_name_reports_position(self):
        with self.assertRaises(MailParseError) as ctx:
            split_header_lines("Bad Name: x\n")
        self.assertEqual(ctx.exception.offset, 0)
        self.assertEqual(ctx.exception.line, 1)


class HeadersTest(unittest.TestCase):
    def setUp(self):
        self.headers = parse_headers(
            "Received: one\nSubject: hi\nReceived: two\n"
        )

    def test_lookup_is_case_insensitive(self):
        self.assertEqual(self.headers.get("subject"), "hi")
        self.assertEqual(self.headers.get("SUBJECT"), "hi")
        self.assertIn("Received", self.headers)

    def test_get_all_keeps_order(self):
        self.assertEqual(self.headers.get_all("received"), ["one", "two"])
        self.assertEqual(self.headers.get_all("missing"), [])

    def test_default_and_key_error(self):
        self.assertIsNone(self.headers.get("Missing"))
        self.assertEqual(self.headers.get("Missing", "-"), "-")
        with self.assertRaises(KeyError):
            self.headers["Missing"]

    def test_names_keep_original_case_without_duplicates(self):
        self.assertEqual(self.headers.names(), ["Received", "Subject"])

    def test_len_and_items(self):
        self.assertEqual(len(self.headers), 3)
        self.assertEqual(
            self.headers.items(),
            [("Received", "one"), ("Subject", "hi"), ("Received", "two")],
        )


class SplitAddressesTest(unittest.TestCase):
    def test_simple_list(self):
        self.assertEqual(
            split_addresses("a@x.com, b@y.com ,c@z.com"),
            ["a@x.com", "b@y.com", "c@z.com"],
        )

    def test_empty_value(self):
        self.assertEqual(split_addresses(""), [])
        self.assertEqual(split_addresses("  ,  "), [])


if __name__ == "__main__":
    unittest.main()
