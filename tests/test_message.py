"""message 模块的基线测试。"""

import unittest

from mailnorm.errors import MailParseError
from mailnorm.message import Message, split_message

PLAIN = (
    "From: postmaster@example.com\n"
    "To: ops@example.com\n"
    "Subject: nightly report\n"
    "Content-Type: text/plain; charset=us-ascii\n"
    "\n"
    "job 1 ok\njob 2 ok\n"
)

MULTIPART = (
    "From: postmaster@example.com\n"
    "Subject: report attached\n"
    "Content-Type: multipart/mixed; boundary=sep\n"
    "\n"
    "--sep\n"
    "Content-Type: text/plain; charset=us-ascii\n"
    "\n"
    "see attachment\n"
    "--sep\n"
    "Content-Type: text/plain; charset=us-ascii\n"
    "\n"
    "log tail\n"
    "--sep--\n"
)


class SplitMessageTest(unittest.TestCase):
    def test_head_body_and_offset(self):
        head, body, offset = split_message(PLAIN)
        self.assertTrue(head.startswith("From: postmaster@example.com\n"))
        self.assertTrue(head.endswith("charset=us-ascii\n"))
        self.assertEqual(body, "job 1 ok\njob 2 ok\n")
        self.assertEqual(offset, PLAIN.index("job 1 ok"))
        self.assertEqual(PLAIN[offset:], body)

    def test_blank_line_at_start(self):
        head, body, offset = split_message("\nbody\n")
        self.assertEqual(head, "")
        self.assertEqual(body, "body\n")
        self.assertEqual(offset, 1)

    def test_body_keeps_trailing_newline(self):
        _, body, _ = split_message("A: 1\n\nline\n\n")
        self.assertEqual(body, "line\n\n")

    def test_missing_blank_line_reports_end(self):
        with self.assertRaises(MailParseError) as ctx:
            split_message("A: 1\nB: 2\n")
        self.assertEqual(ctx.exception.offset, len("A: 1\nB: 2\n"))
        self.assertEqual(ctx.exception.line, 3)


class MessageParseTest(unittest.TestCase):
    def test_plain_message(self):
        msg = Message.parse(PLAIN)
        self.assertEqual(msg.content_type, "text/plain")
        self.assertEqual(msg.params, {"charset": "us-ascii"})
        self.assertEqual(msg.get("Subject"), "nightly report")
        self.assertIn("From", msg.headers)
        self.assertFalse(msg.is_multipart())
        self.assertEqual(msg.text(), "job 1 ok\njob 2 ok\n")

    def test_body_offset_points_into_text(self):
        msg = Message.parse(PLAIN)
        self.assertEqual(PLAIN[msg.body_offset:], msg.body)

    def test_quoted_charset_param_is_unquoted(self):
        text = 'Content-Type: text/plain; charset="utf-8"\n\nhi\n'
        msg = Message.parse(text)
        self.assertEqual(msg.charset(), "utf-8")

    def test_default_content_type(self):
        msg = Message.parse("Subject: no type\n\nhi\n")
        self.assertEqual(msg.content_type, "text/plain")
        self.assertEqual(msg.params, {})

    def test_multipart_is_recognized(self):
        msg = Message.parse(MULTIPART)
        self.assertTrue(msg.is_multipart())
        self.assertEqual(msg.params.get("boundary"), "sep")
        self.assertEqual(msg.body, MULTIPART[MULTIPART.index("--sep\n"):])

    def test_get_with_default_and_item(self):
        msg = Message.parse(PLAIN)
        self.assertEqual(msg.get("Missing", "-"), "-")
        self.assertEqual(msg["Subject"], "nightly report")


if __name__ == "__main__":
    unittest.main()
